# -*- coding: utf-8 -*-
# Last modified: 13/10/2025 - popking (odem2014)
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
    return 'https://arablionztv.online/'  # main url of host


class ArabLionzTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'arablionztv', 'cookie': 'arablionztv.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + 'search'
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/arablionz.png"
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
                printDBG('ArabLionzTV.getPage retry %d failed: %s' % (attempt + 1, str(e)))

            # Cloudflare timing window delay
            time.sleep(1.5)

        printDBG(f"[ArabLionzTV] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ''


###################################################
# MAIN MENU
###################################################

    def listMainMenu(self, cItem):
        printDBG('ArabLionzTV.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'movies_categories', 'title': _('Movies')},
            {'category': 'series_categories', 'title': _('TV series')},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_movies', 'title': _('English movies'), 'url': self.getFullUrl('/category/movies/english-movies/')},
            {'category': 'list_movies', 'title': _('Asian movies'), 'url': self.getFullUrl('/category/movies/asian-movies/')},
            {'category': 'list_movies', 'title': _('Indian movies'), 'url': self.getFullUrl('/category/movies/indian-movies/')},
            {'category': 'list_movies', 'title': _('Anime movies'), 'url': self.getFullUrl('/category/movies/cartoon/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': _('English TV series'), 'url': self.getFullUrl('/category/series/english-series/')},
            {'category': 'list_series', 'title': _('Asian TV series'), 'url': self.getFullUrl('/category/series/asian-series/')},
            {'category': 'list_series', 'title': _('Korean TV series'), 'url': self.getFullUrl('/category/series/korean-series/')},
            {'category': 'list_series', 'title': _('Turkish TV series'), 'url': self.getFullUrl('/category/series/turkish-series/')},
            {'category': 'list_series', 'title': _('Anime TV series'), 'url': self.getFullUrl('/category/series/anime/')},
            {'category': 'list_series', 'title': _('Indian TV series'), 'url': self.getFullUrl('/category/series/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')}
        ]

    def listMoviesCategories(self, cItem):
        printDBG('ArabLionzTV.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG('ArabLionzTV.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

###################################################
# LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
###################################################
    def listUnits(self, cItem):
        printDBG('ArabLionzTV.listUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listUnits: failed to load page')
            return

###################################################
# MAIN MOVIE BLOCK
###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<boxed--is-box>', '</boxed--is-box>', False)[1]
        if not main_block:
            printDBG('listUnits: No BlocksHolder/MainFiltar found')
            return

###################################################
# MOVIE BOXES
###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="Posts--Single--Box', '</inner--title>')
        printDBG('listUnits: Found %d items' % len(items))

        for item in items:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            icon = self.cm.ph.getSearchGroups(item, r'data-image="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]

            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2>', '</h2>', False)[1])

            # Exclude unwanted titles
            if any(excluded.lower() in title.lower() for excluded in ['IPTV', 'Shof TV']):
                printDBG('listUnits: Skipped excluded title -> %s' % title)
                continue

            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span>', '</span>', False)[1])

###################################################
# COLORIZE TITLE (movie name + year)
###################################################
            raw_title = title.replace("مترجم اون لاين", "").replace("مشاهدة فيلم", "").strip()
            match = re.search(r'(.*?)(\d{4})$', raw_title)
            if match:
                movie_title = match.group(1).strip()
                movie_year = match.group(2)
                colored_title = f"{E2ColoR('yellow')}{movie_title} {E2ColoR('cyan')}{movie_year}{E2ColoR('white')}"
            else:
                colored_title = f"{E2ColoR('yellow')}{raw_title}{E2ColoR('white')}"

###################################################
# COLORIZE QUALITY
###################################################
            q_color = 'white'
            if re.search(r'4K|1080|HD|BluRay', quality, re.I):
                q_color = 'green'
            elif re.search(r'720|HDRip|WEB', quality, re.I):
                q_color = 'yellow'
            elif re.search(r'CAM|TS|HDCAM', quality, re.I):
                q_color = 'red'

            colored_quality = f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}"

            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': '%s | %s' % (colored_quality, desc),
                'category': 'explore_items'
            })
            self.addDir(params)


###################################################
# PAGINATION
###################################################
        paginate_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<ul class="page-numbers">', '</ul>', False
        )[1]
        printDBG('paginate_block.listUnits >>> %s' % paginate_block)

        if paginate_block:
            # Extract all links inside pagination
            page_links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', paginate_block)
            printDBG('listUnits: Found %d pagination links' % len(page_links))

            next_url = ''
            prev_url = ''

            for href, label in page_links:
                label = self.cleanHtmlStr(label)
                if label in ['»', '&raquo;']:
                    next_url = href
                elif label in ['«', '&laquo;']:
                    prev_url = href

            if prev_url:
                params = dict(cItem)
                params.update({
                    'title': '<<< ' + _('Previous'),
                    'url': self.getFullUrl(prev_url),
                    'category': cItem.get('category', 'list_movies')
                })
                self.addDir(params)
                printDBG('listUnits: Found previous page %s' % prev_url)

            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('Next') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': cItem.get('category', 'list_movies')
                })
                self.addDir(params)
                printDBG('listUnits: Found next page %s' % next_url)

###################################################
# EXPLORE ITEM (fetch all servers and final iframe links)
###################################################
    def exploreItems(self, cItem):
        printDBG('ArabLionzTV.exploreItems >>> %s' % cItem)
        url = cItem.get('url', '')
        if not url:
            return

        # Step 1: Load main page to get data-id
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG('exploreItems: failed to load item page')
            return

        data_id = self.cm.ph.getSearchGroups(data, r'data-id="([0-9]+)"')[0]
        printDBG('exploreItems: data_id = %s' % data_id)
        if not data_id:
            printDBG('exploreItems: no data-id found in HTML')
            return

        # Step 2: POST to get list of servers (must be POST with header)
        servers_url = urljoin(self.MAIN_URL, 'PostServersWatch/%s' % data_id)
        printDBG('exploreItems: servers_url = %s' % servers_url)

        post_headers = dict(self.HEADER)
        post_headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': url,
            'Origin': self.MAIN_URL
        })

        params = dict(self.defaultParams)
        params.update({'header': post_headers})

        sts, servers_data = self.getPage(servers_url, addParams=params, post_data={})
        if not sts or '<servers--selected>' not in servers_data:
            printDBG('exploreItems: failed to load servers list or no servers found')
            return

        printDBG('exploreItems: servers_data length = %d' % len(servers_data))

        servers_block = self.cm.ph.getDataBeetwenMarkers(
            servers_data, '<servers--selected>', '</servers--selected>', False
        )[1]
        li_list = self.cm.ph.getAllItemsBeetwenMarkers(servers_block, '<li', '</li>')
        printDBG('exploreItems: found %d server(s)' % len(li_list))

        # Step 3: For each server, POST again to get iframe link
        for li in li_list:
            sid = self.cm.ph.getSearchGroups(li, r'data-id="([^"]+)"')[0]
            sindex = self.cm.ph.getSearchGroups(li, r'data-i="([^"]+)"')[0]
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(li, '<em>', '</em>', False)[1])
            if not name:
                name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(li, '<span>', '</span>', False)[1])

            if not sid or not sindex:
                continue

            embed_url = urljoin(self.MAIN_URL, 'Embedder/%s/%s' % (sid, sindex))
            printDBG('exploreItems: embed_url = %s' % embed_url)

            # same POST header trick for Embedder
            embed_headers = dict(post_headers)
            embed_headers['Referer'] = servers_url

            embed_params = dict(self.defaultParams)
            embed_params.update({'header': embed_headers})

            sts, embed_data = self.getPage(embed_url, addParams=embed_params, post_data={})
            if not sts or '<iframe' not in embed_data:
                printDBG('exploreItems: failed to load embed page for %s' % name)
                continue

            iframe_src = self.cm.ph.getSearchGroups(embed_data, r'<iframe[^>]+src="([^"]+)"')[0]
            if not iframe_src:
                continue

            iframe_src = self.getFullUrl(iframe_src)
            printDBG('exploreItems: iframe_src = %s' % iframe_src)

            # Step 4: Add ready-to-play video entry
            params = dict(cItem)
            params.update({
                'title': name if name else ('Server %s' % sindex),
                'url': iframe_src,
                'category': 'video',
                'type': 'video'
            })
            self.addVideo(params)

        if len(self.currList) == 0:
            printDBG('exploreItems: no valid servers found')

###################################################
# GET LINKS FOR VIDEO
###################################################
    def getLinksForVideo(self, cItem):
        printDBG('ArabLionzTV.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'ArabLionzTV - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("ArabLionzTV.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

###################################################
# SEARCH
###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabLionzTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['search_pattern'] = searchPattern
        cItem['category'] = 'list_search_units'
        self.listSearchUnits(cItem)

    def listSearchUnits(self, cItem):
        printDBG('ArabLionzTV.listSearchUnits >>> %s' % cItem)

        searchPattern = cItem.get('search_pattern', '')
        if not searchPattern:
            printDBG('listSearchUnits: No search pattern provided')
            return

        # Build search URL - note the POST endpoint format
        search_url = self.getFullUrl('/SearchEngine/') + urllib_quote_plus(searchPattern)
        printDBG('listSearchUnits: search_url = %s' % search_url)

        # Prepare POST headers (similar to browser example)
        post_headers = dict(self.HEADER)
        post_headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.MAIN_URL + 'tv/',  # As per browser example
            'Origin': self.MAIN_URL,
            'Content-Length': '0'  # No payload as shown in example
        })

        params = dict(self.defaultParams)
        params.update({'header': post_headers})

        # Make POST request (empty post_data as per example)
        sts, data = self.getPage(search_url, addParams=params, post_data={})
        if not sts or not data:
            printDBG('listSearchUnits: failed to load search results')
            return

        printDBG('listSearchUnits: search data length = %d' % len(data))

###################################################
# PARSE SEARCH RESULTS
###################################################

        # Extract the grid containing search results
        grid_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="Grid--ArabLionz">', '</postsscrollloader>', False)[1]
        printDBG('listSearchUnits: grid_block length = %d' % len(grid_block))

        # Extract individual items
        items = self.cm.ph.getAllItemsBeetwenMarkers(grid_block, '<div class="Posts--Single--Box">', '</inner--title>')
        printDBG('listSearchUnits: Found %d search items' % len(items))

        for item in items:
            # Get URL from the <a> tag
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            # Get icon - try data-image first, then src
            icon = self.cm.ph.getSearchGroups(item, r'data-image="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]

            # Get title - try title attribute first, then h2 content
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not title:
                title_data = self.cm.ph.getDataBeetwenMarkers(item, '<h2>', '</h2>', False)[1]
                title = self.cleanHtmlStr(title_data)

            # Exclude unwanted titles
            if not title or any(excluded.lower() in title.lower() for excluded in ['IPTV', 'Shof TV']):
                printDBG('listSearchUnits: Skipped excluded title -> %s' % title)
                continue

            # Get genre/category
            genre_data = self.cm.ph.getDataBeetwenMarkers(item, '<div class="category">', '</div>', False)
            genre = self.cleanHtmlStr(genre_data[1]) if genre_data[0] else ''

            # Clean title
            title = title.replace("مترجمة اون لاين", "").replace("مترجم اون لاين", "").replace("فيلم", "").replace("مسلسل", "").replace("مترجمة", "").replace("مترجم", "").replace("مشاهدة", "").replace("اون لاين", "").strip()
            printDBG('title.listSearchUnits >>> %s' % title)

            # Get description
            desc_data = self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)
            desc = self.cleanHtmlStr(desc_data[1]) if desc_data[0] else ''

            # Get quality from span
            quality_data = self.cm.ph.getDataBeetwenMarkers(item, '<span>', '</span>', False)
            quality = self.cleanHtmlStr(quality_data[1]) if quality_data[0] else ''

###################################################
# COLORIZE TITLE WITH YEAR ANYWHERE
###################################################
            # Find year anywhere in the title
            year_match = re.search(r'(\d{4})', title)
            if year_match:
                year = year_match.group(1)
                # Split title around the year
                parts = re.split(r'(\d{4})', title, 1)
                if len(parts) == 3:
                    before_year = parts[0].strip()
                    after_year = parts[2].strip()

                    if before_year and after_year:
                        colored_title = f"{E2ColoR('yellow')}{before_year} {E2ColoR('cyan')}{year}{E2ColoR('yellow')} {after_year}{E2ColoR('white')}"
                    elif before_year:
                        colored_title = f"{E2ColoR('yellow')}{before_year} {E2ColoR('cyan')}{year}{E2ColoR('white')}"
                    else:
                        colored_title = f"{E2ColoR('cyan')}{year} {E2ColoR('yellow')}{after_year}{E2ColoR('white')}"
                else:
                    colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"
            else:
                colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

###################################################
# COLORIZE QUALITY AND GENRE
###################################################
            desc_parts = []

            # Colorize quality
            if quality:
                q_color = 'white'
                if re.search(r'4K|1080|HD|BluRay', quality, re.I):
                    q_color = 'green'
                elif re.search(r'720|HDRip|WEB', quality, re.I):
                    q_color = 'yellow'
                elif re.search(r'CAM|TS|HDCAM', quality, re.I):
                    q_color = 'red'
                colored_quality = f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}"
                desc_parts.append(colored_quality)

            # Colorize genre
            if genre:
                colored_genre = f"{E2ColoR('lightblue')}{genre}{E2ColoR('white')}"
                desc_parts.append(colored_genre)

            # Add description if available
            if desc:
                desc_parts.append(desc)

            desc_text = ' | '.join(desc_parts) if desc_parts else ''

            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': desc_text,
                'category': 'explore_items'
            })
            self.addDir(params)

###################################################
# HANDLE "LOAD MORE" FOR SEARCH RESULTS
###################################################
        load_more_block = self.cm.ph.getDataBeetwenMarkers(data, '<postsscrollloader', '</postsscrollloader>', False)[1]
        if load_more_block:
            load_more_url = self.cm.ph.getSearchGroups(load_more_block, r'href="([^"]+)"')[0]
            if load_more_url:
                params = dict(cItem)
                params.update({
                    'title': _('More results') + ' >>>',
                    'url': self.getFullUrl(load_more_url),
                    'category': 'list_units'
                })
                self.addDir(params)
                printDBG('listSearchUnits: Found load more URL %s' % load_more_url)

        if len(self.currList) == 0:
            printDBG('listSearchUnits: No search results found')
            self.addDir({
                'title': _('No results found for: %s') % searchPattern,
                'category': None
            })

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArabLionzTV.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_items':
            self.exploreItems(self.currItem)
        elif category == 'movies_categories':
            self.listMoviesCategories(self.currItem)
        elif category == 'series_categories':
            self.listSeriesCategories(self.currItem)
        elif category == 'list_movies':
            self.listUnits(self.currItem)
        elif category == 'list_series':
            self.listUnits(self.currItem)
        elif category == 'list_search_units':
            self.listSearchUnits(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ArabLionzTV(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
