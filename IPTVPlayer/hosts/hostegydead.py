# -*- coding: utf-8 -*-
# Last modified: 24/10/2025 - popking (odem2014)
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
    return 'https://a.egydead.space/'  # main url of host


class EgyDead(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'egydead', 'cookie': 'egydead.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + '?s='
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/egydead.png"
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
                printDBG('EgyDead.getPage retry %d failed: %s' % (attempt + 1, str(e)))

            # Cloudflare timing window delay
            time.sleep(1.5)

        printDBG(f"[EgyDead] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################

    def listMainMenu(self, cItem):
        printDBG('EgyDead.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'movies_categories', 'title': 'Movies'},
            {'category': 'series_categories', 'title': 'Series'},
            {'category': 'anime_categories', 'title': 'Anime'},
            {'category': 'other_categories', 'title': 'Others'},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_units', 'title': 'English Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a-%d8%a7%d9%88%d9%86%d9%84%d8%a7%d9%8a%d9%86/')},
            {'category': 'list_units', 'title': 'Asian Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'Turkish Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'Indian Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'Cartoon Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d8%b1%d8%aa%d9%88%d9%86/')},
            {'category': 'list_units', 'title': 'Cartoon Movies Egyptian Voice', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d8%b1%d8%aa%d9%88%d9%86/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d8%b1%d8%aa%d9%88%d9%86-%d8%af%d9%8a%d8%b2%d9%86%d9%8a-%d8%a8%d8%a7%d9%84%d9%84%d9%87%d8%ac%d8%a9-%d8%a7%d9%84%d9%85%d8%b5%d8%b1%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'Eslam Elgizawy Subbed Movies', 'url': self.getFullUrl('/category/%d8%aa%d8%b1%d8%ac%d9%85%d8%a7%d8%aa-%d8%a7%d8%b3%d9%84%d8%a7%d9%85-%d8%a7%d9%84%d8%ac%d9%8a%d8%b2%d8%a7%d9%88%d9%8a/')},
            {'category': 'list_units', 'title': 'Dubbed Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'list_units', 'title': 'Documentary Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%88%d8%ab%d8%a7%d8%a6%d9%82%d9%8a%d8%a9/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_units', 'title': 'English Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a-1/')},
            {'category': 'list_units', 'title': 'Arabic Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_units', 'title': 'Latin Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%84%d8%a7%d8%aa%d9%8a%d9%86%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'Asian Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'Turkish Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9-%d8%a7/')},
            {'category': 'list_units', 'title': 'Cartoon Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d8%b1%d8%aa%d9%88%d9%86/')},
            {'category': 'list_units', 'title': 'Documentary Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%88%d8%ab%d8%a7%d8%a6%d9%82%d9%8a%d8%a9/')},
            {'category': 'list_units', 'title': 'English Dubbed Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'list_units', 'title': 'Turkish Dubbed Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'list_series', 'title': 'Full Series', 'url': self.getFullUrl('/serie/')}
        ]

        self.ANIME_CAT_TAB = [
            {'category': 'list_anime', 'title': 'Anime Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'list_anime', 'title': 'Anime Dubbed Movies', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d8%b1%d8%aa%d9%88%d9%86/')},
            {'category': 'list_anime', 'title': 'Anime Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'list_anime', 'title': 'Anime Dubbed Series', 'url': self.getFullUrl('/series-category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d8%b1%d8%aa%d9%88%d9%86-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')}
        ]

        self.OTHER_CAT_TAB = [
            {'category': 'list_other', 'title': 'Stand UP Shows', 'url': self.getFullUrl('/category/%d8%b9%d8%b1%d9%88%d8%b6-%d9%88%d8%ad%d9%81%d9%84%d8%a7%d8%aa/')},
            {'category': 'list_other', 'title': 'Sport', 'url': self.getFullUrl('/category/%d8%b1%d9%8a%d8%a7%d8%b6%d8%a9/')},
            {'category': 'list_other', 'title': 'TV Shows', 'url': self.getFullUrl('/series-category/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9-1/')}
        ]

    def listMoviesCategories(self, cItem):
        printDBG('EgyDead.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG('EgyDead.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listAnimeCategories(self, cItem):
        printDBG('EgyDead.listAnimeCategories')
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherCategories(self, cItem):
        printDBG('EgyDead.listOtherCategories')
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    ###################################################
    # LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
    ###################################################
    def listUnits(self, cItem):
        printDBG('EgyDead.listUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        # printDBG('data.listUnits >>> %s' % data)
        if not sts or not data:
            printDBG('listUnits: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="catHolder">', '<div class="pagination">', False)[1]
        # printDBG('main_block.listUnits >>> %s' % main_block)
        if not main_block:
            printDBG('listUnits: No main_block found')
            return
        allblocks = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<ul class="posts-list">', '</ul>')[1]
        printDBG('allblocks.listUnits >>> %s' % allblocks)
        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(allblocks, '<li', '</li>')
        items1 = self.cm.ph.getAllItemsBeetwenMarkers(allblocks, '<li', '</li>')[0]
        printDBG('item1.listUnits >>> %s' % items1)
        printDBG('listUnits: Found %d items' % len(items))

        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            # --- ICON ---
            icon = self.cm.ph.getSearchGroups(item, r'data-lazy-style="[^"]*url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'(?:data-src|src)="([^"]+)"')[0]

            if icon:
                try:
                    icon = urllib_quote_plus(icon, safe=':/?&=#%')
                except Exception as e:
                    printDBG('icon.listUnits encode error: %s' % e)

            # --- TITLE ---
            title = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h1', '</h1>', False)[1]
                )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>', False)[1]
                )

            # --- CATEGORY ---
            category = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<span class="cat_name">', '</span>', False)[1]
            )

            # --- DESCRIPTION (if any) ---
            desc = f"{category}"

            # --- CLEANUP TITLE ---
            title = (
                title.replace("مشاهدة فيلم", "")
                .replace("مشاهدة", "")
                .replace("فيلم", "")
                .replace("مسلسل", "")
                .replace("مترجمة اون لاين", "")
                .replace("مترجم اون لاين", "")
                .replace("مترجمة", "")
                .replace("مترجم", "")
                .replace("اون لاين", "")
                .replace("مدبلجة", "")
                .replace("مدبلج", "")
                .strip()
            )

            printDBG(f"title >>> {title}")
            printDBG(f"url >>> {url}")
            printDBG(f"icon >>> {icon}")
            printDBG(f"category >>> {category}")

            # --- COLORIZE TITLE (movie name + year) ---
            match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', title)
            if match:
                movie_title = match.group(1).strip()
                movie_year = match.group(2).strip()
                colored_title = (
                    f"{E2ColoR('yellow')}{movie_title} "
                    f"{E2ColoR('cyan')}{movie_year}{E2ColoR('white')}"
                )
            else:
                colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- FINAL ITEM ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': f"{category}",
                'category': 'explore_items'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listUnits: No media-card items found')

        ###################################################
        # PAGINATION
        ###################################################
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', False)[1]
        if pagination_block:
            next_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
            prev_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]

            if prev_url:
                params = dict(cItem)
                params.update({
                    'title': '<<< ' + _('Previous'),
                    'url': self.getFullUrl(prev_url),
                    'category': 'list_units'
                })
                self.addDir(params)
                printDBG('listUnits: Found previous page %s' % prev_url)

            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('Next') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': 'list_units'
                })
                self.addDir(params)
                printDBG('listUnits: Found next page %s' % next_url)

    ###################################################
    # EXPLORE ITEM (get list of servers)
    ###################################################
    def exploreItems(self, cItem):
        printDBG('EgyDead.exploreItems >>> %s' % cItem)

        url = cItem.get('url', '')
        printDBG('url.exploreItems >>> %s' % url)

        # --- Load main page ---
        sts, data1 = self.getPage(url)
        if not sts or not data1:
            printDBG('exploreItems: failed to load item page')
            return
        printDBG('data1.exploreItems >>> %s' % data1)

        # --- Extract story part ---
        story_part = self.cm.ph.getDataBeetwenMarkers(data1, '<div class="extra-content">', '</div>', False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(story_part, '<p>', '</p>', False)[1])
        printDBG('story >>> %s' % story)

        # --- Extract info part ---
        info_part = self.cm.ph.getDataBeetwenMarkers(data1, '<div class="LeftBox">', '</div>', False)[1]
        info_items = re.findall(r'<li>.*?</li>', info_part, re.S)
        info_text = ''
        for item in info_items:
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span>', '</span>', False)[1])
            value = ', '.join(re.findall(r'>([^<]+)</a>', item))
            info_text += '%s %s | ' % (label, value)
        info_text = info_text.strip(' |')
        printDBG('info_text >>> %s' % info_text)

        # --- Combine story and info ---
        full_desc = '%s\n\n%s' % (story, info_text)
        printDBG('full_desc >>> %s' % full_desc)

        # --- Check if this is a season page ---
        if '<div class="EpsList">' in data1:
            printDBG('Season page detected — listing episodes...')
            return self.listEpisodes(cItem, data1)

        # --- Prepare POST parameters ---
        params = dict(self.defaultParams)
        params.update({
            'header': {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': url,
            },
        })

        # --- POST payload ---
        post_data = {'View': '1'}

        # --- Send POST request ---
        sts, data = self.getPage(url, params, post_data)
        if not sts or not data:
            printDBG('exploreItems: POST request failed')
            return

        printDBG('data.exploreItems >>> %s' % data)

        # --- Extract servers list ---
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="serversList">', '</ul>', False)[1]
        printDBG('watch_list.exploreItems >>> %s' % watch_list)
        if not watch_list:
            printDBG('No watch list found')
            return

        # --- Parse <li> items ---
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, '<li', '</li>')
        printDBG('Found %d servers' % len(li_items))

        for item in li_items:
            video_url = self.cm.ph.getSearchGroups(item, r'data-link="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(item, r'<p>([^<]+)</p>')[0].strip()
            if not title:
                title = self.cm.ph.getSearchGroups(item, r'>([^<]+)</span>')[0].strip()
            title = self.cleanHtmlStr(title)

            params = dict(cItem)
            params.update({
                'title': title,
                'url': video_url,
                'category': 'video',
                'type': 'video',
                'desc': full_desc,
            })
            self.addVideo(params)

    def listEpisodes(self, cItem, data1):
        printDBG('EgyDead.listEpisodes >>> %s' % cItem)

        list_episode_part = self.cm.ph.getDataBeetwenMarkers(data1, '<div class="EpsList">', '</div>', False)[1]
        if not list_episode_part:
            printDBG('No episode list found')
            return

        episodes = self.cm.ph.getAllItemsBeetwenMarkers(list_episode_part, '<li', '</li>')
        episodes.reverse()
        for item in episodes:
            ep_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not ep_title:
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'>([^<]+)</a>')[0])

            params = dict(cItem)
            params.update({
                'title': ep_title,
                'url': ep_url,
                'category': 'explore_items',  # flow back to exploreItems()
            })
            self.addDir(params)

    def listSeries(self, cItem):
        printDBG('EgyDead.listSeasons >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        # printDBG('data.listSeasons >>> %s' % data)
        if not sts or not data:
            printDBG('listSeasons: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="catHolder">', '<div class="pagination">', False)[1]
        # printDBG('main_block.listSeasons >>> %s' % main_block)
        if not main_block:
            printDBG('listSeasons: No main_block found')
            return
        allblocks = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<ul class="posts-list">', '</ul>')[0]
        printDBG('allblocks.listSeasons >>> %s' % allblocks)
        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(allblocks, '<li', '</li>')
        items1 = self.cm.ph.getAllItemsBeetwenMarkers(allblocks, '<li', '</li>')[0]
        printDBG('item1.listSeasons >>> %s' % items1)
        printDBG('listSeasons: Found %d items' % len(items))
        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            # --- ICON ---
            icon = self.cm.ph.getSearchGroups(item, r'data-lazy-style="[^"]*url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'(?:data-src|src)="([^"]+)"')[0]

            if icon:
                try:
                    icon = urllib_quote_plus(icon, safe=':/?&=#%')
                except Exception as e:
                    printDBG('icon.listSeasons encode error: %s' % e)

            # --- TITLE ---
            title = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h1', '</h1>', False)[1]
                )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>', False)[1]
                )

            # --- CATEGORY ---
            category = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<span class="cat_name">', '</span>', False)[1]
            )

            # --- DESCRIPTION (if any) ---
            desc = f"{category}"

            printDBG(f"title >>> {title}")
            printDBG(f"url >>> {url}")
            printDBG(f"icon >>> {icon}")
            printDBG(f"category >>> {category}")

            # --- COLORIZE TITLE (movie name + year) ---
            match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', title)
            if match:
                movie_title = match.group(1).strip()
                movie_year = match.group(2).strip()
                colored_title = (
                    f"{E2ColoR('yellow')}{movie_title} "
                    f"{E2ColoR('cyan')}{movie_year}{E2ColoR('white')}"
                )
            else:
                colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- FINAL ITEM ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': f"{category}",
                'category': 'explore_seasons'
            })
            self.addDir(params)

        ###################################################
        # PAGINATION
        ###################################################
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', False)[1]
        if pagination_block:
            next_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
            prev_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]

            if prev_url:
                params = dict(cItem)
                params.update({
                    'title': '<<< ' + _('Previous'),
                    'url': self.getFullUrl(prev_url),
                    'category': 'list_series'
                })
                self.addDir(params)
                printDBG('listUnits: Found previous page %s' % prev_url)

            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('Next') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': 'list_series'
                })
                self.addDir(params)
                printDBG('listUnits: Found next page %s' % next_url)

    def exploreSeasons(self, cItem):
        printDBG('EgyDead.exploreItems >>> %s' % cItem)

        url = cItem.get('url', '')
        printDBG('url.exploreItems >>> %s' % url)

        # --- Load main page ---
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG('exploreSeasons: failed to load item page')
            return
        # printDBG('data.exploreSeasons >>> %s' % data)

        # --- Extract story part ---
        story_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="extra-content">', '</div>', False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(story_part, '<p>', '</p>', False)[1])
        printDBG('story >>> %s' % story)

        # --- Extract info part ---
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="LeftBox">', '</div>', False)[1]
        info_items = re.findall(r'<li>.*?</li>', info_part, re.S)
        info_text = ''
        for item in info_items:
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span>', '</span>', False)[1])
            value = ', '.join(re.findall(r'>([^<]+)</a>', item))
            info_text += '%s %s | ' % (label, value)
        info_text = info_text.strip(' |')
        printDBG('info_text >>> %s' % info_text)

        # --- Combine story and info ---
        full_desc = '%s\n\n%s' % (story, info_text)
        printDBG('full_desc >>> %s' % full_desc)

        # --- Check if this is a season page ---
        if 'seasons-list' in data:
            printDBG('Seasons page detected — listing seasons...')
        list_seasons_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasons-list">', '</div>', False)[1]
        if not list_seasons_part:
            printDBG('No seasons list found')
            return

        seasons = self.cm.ph.getAllItemsBeetwenMarkers(list_seasons_part, '<li', '</li>')
        seasons.reverse()
        for item in seasons:
            season_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            season_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not season_title:
                season_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'>([^<]+)</a>')[0])

            params = dict(cItem)
            params.update({
                'title': season_title,
                'url': season_url,
                'category': 'explore_items',  # flow back to exploreItems()
                'desc': full_desc,
            })
            self.addDir(params)

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('EgyDead.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'EgyDead - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("EgyDead.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EgyDead.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listSearchUnits(cItem)

    def listSearchUnits(self, cItem):
        printDBG('EgyDead.listSearchUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        # printDBG('data.listSearchUnits >>> %s' % data)
        if not sts or not data:
            printDBG('listSearchUnits: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="catHolder">', '</div>', False)[1]
        # printDBG('main_block.listSearchUnits >>> %s' % main_block)
        if not main_block:
            printDBG('listSearchUnits: No main_block found')
            return
        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<li', '</li>')
        items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<li', '</li>')[0]
        printDBG('item1.listSearchUnits >>> %s' % items1)
        printDBG('listSearchUnits: Found %d items' % len(items))

        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            # --- ICON ---
            icon = self.cm.ph.getSearchGroups(item, r'data-lazy-style="[^"]*url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'(?:data-src|src)="([^"]+)"')[0]

            if icon:
                try:
                    icon = urllib_quote_plus(icon, safe=':/?&=#%')
                except Exception as e:
                    printDBG('icon.listSearchUnits encode error: %s' % e)

            # --- TITLE ---
            title = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h1', '</h1>', False)[1]
                )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>', False)[1]
                )

            # --- CATEGORY ---
            category = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<span class="cat_name">', '</span>', False)[1]
            )

            # --- DESCRIPTION (if any) ---
            desc = f"{category}"

            # --- CLEANUP TITLE ---
            title = (
                title.replace("مشاهدة فيلم", "")
                .replace("مشاهدة", "")
                .replace("فيلم", "")
                .replace("مسلسل", "")
                .replace("مترجمة اون لاين", "")
                .replace("مترجم اون لاين", "")
                .replace("مترجمة", "")
                .replace("مترجم", "")
                .replace("اون لاين", "")
                .replace("مدبلجة", "")
                .replace("مدبلج", "")
                .strip()
            )

            printDBG(f"title >>> {title}")
            printDBG(f"url >>> {url}")
            printDBG(f"icon >>> {icon}")
            printDBG(f"category >>> {category}")

            # --- COLORIZE TITLE (movie name + year) ---
            match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', title)
            if match:
                movie_title = match.group(1).strip()
                movie_year = match.group(2).strip()
                colored_title = (
                    f"{E2ColoR('yellow')}{movie_title} "
                    f"{E2ColoR('cyan')}{movie_year}{E2ColoR('white')}"
                )
            else:
                colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- FINAL ITEM ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': f"{category}",
                'category': 'explore_items'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listUnits: No media-card items found')

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('EgyDead.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'explore_items':
            self.exploreItems(self.currItem)
        elif category == 'movies_categories':
            self.listMoviesCategories(self.currItem)
        elif category == 'series_categories':
            self.listSeriesCategories(self.currItem)
        elif category == 'anime_categories':
            self.listAnimeCategories(self.currItem)
        elif category == 'other_categories':
            self.listOtherCategories(self.currItem)
        elif category == 'list_units':
            self.listUnits(self.currItem)
        elif category == 'list_anime':
            self.listUnits(self.currItem)
        elif category == 'list_other':
            self.listUnits(self.currItem)
        elif category == 'list_series':
            self.listSeries(self.currItem)
        elif category == 'explore_seasons':
            self.exploreSeasons(self.currItem)
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
        CHostBase.__init__(self, EgyDead(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
