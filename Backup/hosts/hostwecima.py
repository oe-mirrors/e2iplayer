# -*- coding: utf-8 -*-
# Last modified: 17/10/2025 - popking (odem2014)
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
    return 'https://cima.wecima.show/'  # main url of host


class WeCima(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wecima', 'cookie': 'wecima.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + 'search/'
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/wecima.png"
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
                printDBG('WeCima.getPage retry %d failed: %s' % (attempt + 1, str(e)))

            # Cloudflare timing window delay
            time.sleep(1.5)

        printDBG(f"[WeCima] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################

    def listMainMenu(self, cItem):
        printDBG('WeCima.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'movies_categories', 'title': 'الافلام'},
            {'category': 'series_categories', 'title': 'المسلسلات'},
            {'category': 'anime_categories', 'title': 'الكارتون'},
            {'category': 'production_categories', 'title': 'شركات الانتاج'},
            {'category': 'other_categories', 'title': _('Others')}
        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_movies', 'title': 'افلام اجنبية', 'url': self.getFullUrl('/category/%d8%a3%d9%81%d9%84%d8%a7%d9%85/10-movies-english-%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_movies', 'title': 'افلام تركية', 'url': self.getFullUrl('/category/%d8%a3%d9%81%d9%84%d8%a7%d9%85/1-%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%89-turkish-films/')},
            {'category': 'list_movies', 'title': 'افلام عربية', 'url': self.getFullUrl('/category/%d8%a3%d9%81%d9%84%d8%a7%d9%85/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a-arabic-movies/')},
            {'category': 'list_movies', 'title': 'افلام هندية', 'url': self.getFullUrl('/category/%d8%a3%d9%81%d9%84%d8%a7%d9%85/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a-indian-movies/')},
            {'category': 'list_movies', 'title': 'افلام وثائقية', 'url': self.getFullUrl('/category/%d8%a3%d9%81%d9%84%d8%a7%d9%85/2-%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%88%d8%ab%d8%a7%d8%a6%d9%82%d9%8a%d8%a9-documentary-films/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': 'مسلسلات اجنبية', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa/7-series-english-%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_series', 'title': 'مسلسلات عربية', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa/19-%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a%d9%87-arabic-series/')},
            {'category': 'list_series', 'title': 'مسلسلات هندية', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa/10-series-indian-%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': 'مسلسلات اسيوية', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa/1-%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': 'مسلسلات تركية', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa/12-%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9-turkish-series/')},
            {'category': 'list_series', 'title': 'مسلسلات وثائقية', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa/1-%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%88%d8%ab%d8%a7%d8%a6%d9%82%d9%8a%d8%a9-documentary-series/')}
        ]

        self.ANIME_CAT_TAB = [
            {'category': 'list_anime', 'title': 'افلام كارتون', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d8%b1%d8%aa%d9%88%d9%86/')},
            {'category': 'list_anime', 'title': 'مسلسلات كارتون', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d8%b1%d8%aa%d9%88%d9%86/')}
        ]

        self.PRODUCTION_CAT_TAB = [
            {'category': 'list_production', 'title': _('Walt Disney'), 'url': self.getFullUrl('/production/walt-disney-pictures/')},
            {'category': 'list_production', 'title': _('Netflix'), 'url': self.getFullUrl('/production/netflix/')},
            {'category': 'list_production', 'title': _('Warner Bros'), 'url': self.getFullUrl('/production/warner-bros/')},
            {'category': 'list_production', 'title': _('Lionsgate'), 'url': self.getFullUrl('/production/lionsgate/')},
            {'category': 'list_production', 'title': _('Columbia'), 'url': self.getFullUrl('/production/columbia-pictures/')},
            {'category': 'list_production', 'title': _('Universal'), 'url': self.getFullUrl('/production/universal-pictures/')}
        ]

        self.OTHER_CAT_TAB = [
            {'category': 'list_other', 'title': _('Trend'), 'url': self.getFullUrl('/trends/')},
            {'category': 'list_other', 'title': 'مصارعة', 'url': self.getFullUrl('/category/%D9%85%D8%B5%D8%A7%D8%B1%D8%B9%D8%A9-%D8%AD%D8%B1%D8%A9/')},
            {'category': 'list_other', 'title': 'برامج تليفزيونية', 'url': self.getFullUrl('/category/%D8%A8%D8%B1%D8%A7%D9%85%D8%AC-%D8%AA%D9%84%D9%8A%D9%81%D8%B2%D9%8A%D9%88%D9%86%D9%8A%D8%A9/')}
        ]

    def listMoviesCategories(self, cItem):
        printDBG('WeCima.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG('WeCima.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listAnimeCategories(self, cItem):
        printDBG('WeCima.listAnimeCategories')
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listProductionCategories(self, cItem):
        printDBG('WeCima.listProductionCategories')
        self.listsTab(self.PRODUCTION_CAT_TAB, cItem)

    def listOtherCategories(self, cItem):
        printDBG('WeCima.listOtherCategories')
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    ###################################################
    # LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
    ###################################################
    def listUnits(self, cItem):
        printDBG('WeCima.listUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listUnits: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<section class="cine-home">', '<script type="speculationrules">', False)[1]
        if not main_block:
            printDBG('listUnits: No main_block found')
            return

        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="media-card"', '<ul class="PostItemStats">')
        printDBG('listUnits: Found %d items' % len(items))

        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            # --- Icon ---
            icon = self.cm.ph.getSearchGroups(item, r'data-lazy-style="[^"]*url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'(?:data-src|src)="([^"]+)"')[0]

            # --- Clean & normalize title ---
            title = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>', False)[1]
                )

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
            printDBG('title.listUnits >>> %s' % title)

            # --- Description & Quality ---
            desc = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'<meta itemprop="description" content="([^"]+)"')[0]
            )
            if not desc:
                desc = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(item, '<p class="media-card__description"', '</p>', False)[1]
                )

            desc = desc.replace("مشاهدة وتحميل فيلم", "").replace("على موقع ماي سيما mycima وى سيما wecima", "")
            quality = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<em class="ribbon">', '</em>', False)[1]
            )
            printDBG('quality.listUnits >>> %s' % quality)

            ###################################################
            # COLORIZE TITLE (movie name + year)
            ###################################################
            match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', title)
            if match:
                movie_title = match.group(1).strip()
                movie_year = match.group(2).strip()
                colored_title = (
                    f"{E2ColoR('yellow')}{movie_title} "
                    f"{E2ColoR('cyan')}{movie_year}"
                    f"{E2ColoR('white')}"
                )
            else:
                colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            ###################################################
            # COLORIZE QUALITY
            ###################################################
            q_color = 'white'
            if re.search(r'4K|1080|BluRay', quality, re.I):
                q_color = 'green'
            elif re.search(r'720|HDRip|WEB', quality, re.I):
                q_color = 'yellow'
            elif re.search(r'CAM|TS|HDCAM', quality, re.I):
                q_color = 'red'

            colored_quality = (
                f"{E2ColoR(q_color)}{quality if quality else 'N/A'}{E2ColoR('white')}"
            )

            ###################################################
            # FINAL ITEM
            ###################################################
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': f"{colored_quality} | {desc}",
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
                    'category': 'list_movies'
                })
                self.addDir(params)
                printDBG('listUnits: Found previous page %s' % prev_url)

            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('Next') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': 'list_movies'
                })
                self.addDir(params)
                printDBG('listUnits: Found next page %s' % next_url)

    ###################################################
    # EXPLORE ITEM (get list of servers)
    ###################################################
    def exploreItems(self, cItem):
        printDBG('WeCima.exploreItems >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.exploreItems >>> %s' % url)

        sts, data = self.getPage(url)
        # printDBG('data.exploreItems >>> %s' % data)
        if not sts:
            return

        # Extract the main <ul id="watch"> section
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="watch__server-list" id="watch">', '</ul>', False)[1]
        printDBG('watch_list.exploreItems >>> %s' % watch_list)

        if not watch_list:
            printDBG('No watch list found')
            return

        # Get all <li> blocks
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, '<li', '</li>')
        printDBG('li_items.exploreItems >>> %s' % li_items)
        printDBG('Found %d servers' % len(li_items))

        # Skip the first server (index 0)
        li_items = li_items[1:]
        printDBG('After excluding first server, remaining: %d' % len(li_items))

        for item in li_items:
            # Extract the base64 URL
            encoded_url = self.cm.ph.getSearchGroups(item, r'data-url="([^"]+)"')[0]
            printDBG('encoded_url.exploreItems >>> %s' % encoded_url)
            if not encoded_url:
                continue

            # Decode Base64 safely
            try:
                decoded_bytes = base64.b64decode(encoded_url)
                url = decoded_bytes.decode('utf-8', errors='ignore')
            except Exception as e:
                printDBG('Base64 decode error: %s' % e)
                continue

            printDBG('decoded_url.exploreItems >>> %s' % url)

            # Extract the server title (from <strong> tag)
            title = self.cm.ph.getSearchGroups(item, r'<strong>([^<]+)</strong>')[0].strip()
            if not title:
                title = self.cm.ph.getSearchGroups(item, r'>([^<]+)</span>')[0].strip()
            title = self.cleanHtmlStr(title)
            printDBG('title.exploreItems >>> %s' % title)

            # Add video entry
            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'category': 'video',
                'type': 'video',
            })
            self.addVideo(params)

        if len(li_items) == 0:
            printDBG('No <li> items found in server-list')

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('WeCima.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'WeCima - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("WeCima.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WeCima.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('WeCima.handleService start')

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
        elif category == 'production_categories':
            self.listProductionCategories(self.currItem)
        elif category == 'other_categories':
            self.listOtherCategories(self.currItem)
        elif category == 'list_movies':
            self.listUnits(self.currItem)
        elif category == 'list_series':
            self.listUnits(self.currItem)
        elif category == 'list_anime':
            self.listUnits(self.currItem)
        elif category == 'list_production':
            self.listUnits(self.currItem)
        elif category == 'list_other':
            self.listUnits(self.currItem)

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
        CHostBase.__init__(self, WeCima(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
