# -*- coding: utf-8 -*-
# Last modified: 11/11/2025 - popking (odem2014)
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
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://ak.sv/'  # main url of host


class Akoam(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'akoam', 'cookie': 'akoam.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + 'search?q='
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/popking159/mye2iplayer/refs/heads/main/akoam.png"
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {
            'header': self.HEADER,
            'use_cookie': True,
            'load_cookie': True,
            'save_cookie': True,
            'cookiefile': self.COOKIE_FILE
        }

    def getPage(self, baseUrl, addParams=None, post_data=None):
        # Handle unicode URLs safely
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")

        if addParams is None:
            addParams = dict(self.defaultParams)

        # Always re-init CF parameters
        addParams["cloudflare_params"] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent")
        }

        # For GET requests: reload cookie each time
        if post_data is None:
            addParams["load_cookie"] = False   # don’t reuse
            addParams["save_cookie"] = True    # save new one

        max_retries = 3
        for attempt in range(max_retries):
            try:
                sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG('Akoam.getPage retry %d failed: %s' % (attempt + 1, str(e)))

            # Cloudflare timing window delay
            time.sleep(1.5)

        printDBG(f"[Akoam] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################

    def listMainMenu(self, cItem):
        printDBG('Akoam.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'movies_categories', 'title': 'Movies'},
            {'category': 'series_categories', 'title': 'Series'},
            {'category': 'show_categories', 'title': 'shows'},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_movies', 'title': 'All', 'url': self.getFullUrl('movies/')},
            {'category': 'list_movies', 'title': 'Arabic', 'url': self.getFullUrl('movies?section=29')},
            {'category': 'list_movies', 'title': 'English', 'url': self.getFullUrl('movies?section=30')},
            {'category': 'list_movies', 'title': 'India', 'url': self.getFullUrl('movies?section=31')},
            {'category': 'list_movies', 'title': 'Turkish', 'url': self.getFullUrl('movies?section=32')},
            {'category': 'list_movies', 'title': 'Asian', 'url': self.getFullUrl('movies?section=33')},
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': 'All', 'url': self.getFullUrl('series/')},
            {'category': 'list_series', 'title': 'Arabic', 'url': self.getFullUrl('series?section=29')},
            {'category': 'list_series', 'title': 'English', 'url': self.getFullUrl('series?section=30')},
            {'category': 'list_series', 'title': 'India', 'url': self.getFullUrl('series?section=31')},
            {'category': 'list_series', 'title': 'Turkish', 'url': self.getFullUrl('series?section=32')},
            {'category': 'list_series', 'title': 'Asian', 'url': self.getFullUrl('series?section=33')}
        ]

        self.SHOW_CAT_TAB = [
            {'category': 'list_series', 'title': 'TV Show', 'url': self.getFullUrl('shows?section=42')},
            {'category': 'list_series', 'title': 'Documentary', 'url': self.getFullUrl('shows?section=46')},
            {'category': 'list_movies', 'title': 'Masrahyat', 'url': self.getFullUrl('shows?section=45')},
            {'category': 'list_movies', 'title': 'WWE', 'url': self.getFullUrl('shows?section=43')},
        ]

    def listMoviesCategories(self, cItem):
        printDBG('Akoam.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG('Akoam.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listShowCategories(self, cItem):
        printDBG('Akoam.listShowCategories')
        self.listsTab(self.SHOW_CAT_TAB, cItem)

    ###################################################
    # LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
    ###################################################
    def listUnits(self, cItem):
        printDBG('Akoam.listUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        #printDBG('data.listUnits >>> %s' % data)
        if not sts or not data:
            printDBG('listUnits: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="widget-body row flex-wrap">', '<div class="d-none d-sm-block">', False)[1]
        if not main_block:
            printDBG('listUnits: No main_block found')
            return

        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="entry-box entry-box-1">', '<div class="col-lg')
        #items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="entry-box entry-box-1">', '<div class="col-lg')[0]
        #printDBG('items1.listUnits >>> %s' % items1)
        printDBG('listUnits: Found %d items' % len(items))

        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            # --- Poster ---
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)

            # --- Title ---
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3 class="entry-title font-size-14 m-0">', '</h3>', False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])

            # --- Rating ---
            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="label rating">', '</span>', False)[1])

            # --- Quality ---
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="label quality">', '</span>', False)[1])

            # --- Year ---
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="badge badge-pill badge-secondary ml-1">', '</span>', False)[1])

            # --- Genres ---
            genres_html = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span class="badge badge-pill badge-light ml-1">', '</span>')
            genres = ', '.join([self.cleanHtmlStr(g) for g in genres_html])

            # --- Description ---
            desc = f"{E2ColoR('green')}Rating:{E2ColoR('white')} {rating or 'N/A'} | " \
                   f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} {quality or 'N/A'} | " \
                   f"{E2ColoR('cyan')}Year:{E2ColoR('white')} {year or 'N/A'} | " \
                   f"{E2ColoR('magenta')}Genres:{E2ColoR('white')} {genres or 'N/A'}"

            # --- COLORIZE TITLE ---
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- Add item ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'list_qualities'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listUnits: No entry-box items found')

        ###################################################
        # === PAGINATION HANDLING (FINAL FIX) ===
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', '</ul>', True)[1]
        printDBG('pagination.listUnits >>> %s' % pagination)

        nextPage = self.cm.ph.getSearchGroups(pagination, r'href="([^"]+?)"[^>]*rel="next"')[0].replace("amp;", "")
        prevPage = self.cm.ph.getSearchGroups(pagination, r'href="([^"]+?)"[^>]*rel="prev"')[0].replace("amp;", "")

        if nextPage:
            printDBG('Next page found: %s' % nextPage)
            params = dict(cItem)
            params.update({'title': 'Next Page', 'url': nextPage})
            self.addDir(params)
        else:
            printDBG('No next page found in pagination')

        if prevPage:
            printDBG('Previous page found: %s' % prevPage)
            params = dict(cItem)
            params.update({'title': 'Previous Page', 'url': prevPage})
            self.addDir(params)
        else:
            printDBG('No previous page found in pagination')
    
    ###################################################
    # EXPLORE ITEM (get list of servers)
    ###################################################
    def listQualities(self, cItem):
        printDBG('Akoam.listQualities >>> %s' % cItem)

        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG('listQualities: failed to load page')
            return

        # Extract section that contains tab-content blocks
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<div class="bg-primary2', '<div class="widget-4 widget', False)[1]
        printDBG('watch_list.listQualities >>> %s' % watch_list)

        if not watch_list:
            printDBG('No watch list found')
            return

        # Extract all quality content blocks
        quality_blocks = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, '<div class="tab-content quality"', '</div>')
        printDBG('Found %d quality blocks' % len(quality_blocks))

        # Mapping of tab-id to readable quality names
        quality_map = {
            'tab-5': '1080p',
            'tab-4': '720p',
            'tab-3': '480p',
            'tab-2': '360p'
        }

        for block in quality_blocks:
            # Extract tab id
            tab_id = self.cm.ph.getSearchGroups(block, r'id="([^"]+)"')[0]
            if not tab_id:
                continue

            # Extract watch (مشاهدة) link
            watch_link = self.cm.ph.getSearchGroups(block, r'href="(http[^"]+)"[^>]*class="[^"]*link-show')[0]
            printDBG('tab_id: %s, watch_link: %s' % (tab_id, watch_link))

            if not watch_link:
                continue

            # Map ID to readable title (fallback to id)
            quality_name = quality_map.get(tab_id, tab_id)
            printDBG('Found quality: %s (%s)' % (quality_name, tab_id))

            # Build item
            params = dict(cItem)
            params.update({
                'title': quality_name,
                'url': watch_link,
                'category': 'temp_page',
            })
            self.addDir(params)

        if len(quality_blocks) == 0:
            printDBG('No tab-content quality blocks found')

    def exploreTempPage(self, cItem):
        printDBG('Akoam.exploreTempPage >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.exploreTempPage >>> %s' % url)

        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG('exploreTempPage: failed to load page')
            return

        # Extract segments containing the target links
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'APP_DOMAIN_ALTERNATIVE', '"download-link')
        printDBG('Found %d video links' % len(li_items))

        if not li_items:
            printDBG('No video links found')
            return

        # Take only the first match
        first_item = li_items[0]
        link = self.cm.ph.getSearchGroups(first_item, r'href="(https?://[^"]+)"')[0]
        if not link:
            printDBG('No valid href found in first APP_DOMAIN_ALTERNATIVE block')
            return

        printDBG('Found first video page link: %s' % link)

        # Fixed title
        title = 'Multi Quality Link'

        # Add entry to go to exploreItems()
        params = dict(cItem)
        params.update({
            'title': title,
            'url': link,
            'category': 'explore_item'
        })
        self.addDir(params)
        printDBG('Added first video page: %s' % title)

    def exploreItems(self, cItem):
        printDBG('Akoam.exploreItems >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.exploreItems >>> %s' % url)

        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG('exploreItems: failed to load page')
            return

        # Extract <video> block
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1]
        printDBG('watch_list.exploreItems >>> %s' % watch_list)

        if not watch_list:
            printDBG('No <video> block found')
            return

        # Extract all <source> tags inside the <video>
        sources = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, '<source', '/>')
        printDBG('Found %d video sources' % len(sources))

        for item in sources:
            # Extract URL
            video_url = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            # Extract resolution (size)
            size = self.cm.ph.getSearchGroups(item, r'size="([^"]+)"')[0]

            if not video_url:
                continue

            # Try to build a nice title from URL
            filename = video_url.split('/')[-1]
            filename = filename.replace('.mp4', '').strip()
            if not filename:
                filename = 'Video'

            # Append resolution if available
            title = filename
            if size:
                title = '%s (%sp)' % (filename, size)

            printDBG('Found video source: %s' % title)
            printDBG('video_url: %s' % video_url)

            # Add as playable video
            params = dict(cItem)
            params.update({
                'title': title,
                'url': video_url,
                'category': 'video',
                'type': 'video',
            })
            self.addVideo(params)

        if len(sources) == 0:
            printDBG('No <source> tags found inside <video>')

    def listSeriesUnits(self, cItem):
        printDBG('Akoam.listUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listUnits: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="widget-body row flex-wrap">', '<div class="d-none d-sm-block">', False)[1]
        if not main_block:
            printDBG('listUnits: No main_block found')
            return

        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="entry-box entry-box-1">', '<div class="col-lg')
        #items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="entry-box entry-box-1">', '<div class="col-lg')[0]
        #printDBG('items1.listUnits >>> %s' % items1)
        printDBG('listUnits: Found %d items' % len(items))

        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            # --- Poster ---
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)

            # --- Title ---
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3 class="entry-title font-size-14 m-0">', '</h3>', False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])

            # --- Rating ---
            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="label rating">', '</span>', False)[1])

            # --- Quality ---
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="label quality">', '</span>', False)[1])

            # --- Year ---
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="badge badge-pill badge-secondary ml-1">', '</span>', False)[1])

            # --- Genres ---
            genres_html = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span class="badge badge-pill badge-light ml-1">', '</span>')
            genres = ', '.join([self.cleanHtmlStr(g) for g in genres_html])

            # --- Description ---
            desc = f"{E2ColoR('green')}Rating:{E2ColoR('white')} {rating or 'N/A'} | " \
                   f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} {quality or 'N/A'} | " \
                   f"{E2ColoR('cyan')}Year:{E2ColoR('white')} {year or 'N/A'} | " \
                   f"{E2ColoR('magenta')}Genres:{E2ColoR('white')} {genres or 'N/A'}"

            # --- COLORIZE TITLE ---
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- Add item ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'list_series_episodes'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listUnits: No entry-box items found')    

        ###################################################
        # === PAGINATION HANDLING (FINAL FIX) ===
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', '</ul>', True)[1]
        printDBG('pagination.listUnits >>> %s' % pagination)

        nextPage = self.cm.ph.getSearchGroups(pagination, r'href="([^"]+?)"[^>]*rel="next"')[0].replace("amp;", "")
        prevPage = self.cm.ph.getSearchGroups(pagination, r'href="([^"]+?)"[^>]*rel="prev"')[0].replace("amp;", "")

        if nextPage:
            printDBG('Next page found: %s' % nextPage)
            params = dict(cItem)
            params.update({'title': 'Next Page', 'url': nextPage})
            self.addDir(params)
        else:
            printDBG('No next page found in pagination')

        if prevPage:
            printDBG('Previous page found: %s' % prevPage)
            params = dict(cItem)
            params.update({'title': 'Previous Page', 'url': prevPage})
            self.addDir(params)
        else:
            printDBG('No previous page found in pagination')

    def listSeriesEpisodes(self, cItem):
        printDBG('Akoam.listSeriesEpisodes >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listSeriesEpisodes: failed to load page')
            return

        ###################################################
        # MAIN EPISODE BLOCKS
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="bg-primary2', '<div class="widget-4', True)[1]
        printDBG('main_block.listSeriesEpisodes >>> %s' % main_block)
        if not main_block:
            printDBG('listSeriesEpisodes: No main_block found')
            return

        ###################################################
        # EACH EPISODE ENTRY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="bg-primary2', '</picture>')
        items.reverse()
        printDBG('listSeriesEpisodes: Found %d episode items' % len(items))
        if not items:
            printDBG('listSeriesEpisodes: No episode items found')
            return

        for item in items:
            # --- Extract episode URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            printDBG('Episode URL: %s' % url)

            # --- Extract thumbnail ---
            icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)
            printDBG('Episode icon: %s' % icon)

            # --- Extract title ---
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'>([^<]+)</a>')[0])
            printDBG('Episode title: %s' % title)

            # --- Optional: Add color ---
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- Add entry leading to qualities ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'category': 'list_qualities'
            })
            self.addDir(params)
            printDBG('Added episode: %s' % title)

        if len(items) == 0:
            printDBG('listSeriesEpisodes: No episodes parsed') 

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Akoam.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'Akoam - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 0}]

    def getVideoLinks(self, url):
        printDBG("Akoam.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Akoam.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Akoam.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_qualities':
            self.listQualities(self.currItem)
        elif category == 'movies_categories':
            self.listMoviesCategories(self.currItem)
        elif category == 'series_categories':
            self.listSeriesCategories(self.currItem)
        elif category == 'show_categories':
            self.listShowCategories(self.currItem)
        elif category == 'list_movies':
            self.listUnits(self.currItem)
        elif category == 'list_series':
            self.listSeriesUnits(self.currItem)
        elif category == 'temp_page':
            self.exploreTempPage(self.currItem)
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
        CHostBase.__init__(self, Akoam(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
