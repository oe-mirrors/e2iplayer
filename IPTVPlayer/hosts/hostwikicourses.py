# -*- coding: utf-8 -*-
# Last modified: 16/11/2025 - popking (odem2014)
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
    return 'https://www.wikicourses.net/'  # main url of host


class WikiCourses(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wikicourses', 'cookie': 'wikicourses.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + 'search?q='
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/wikicourses.png"
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
        Unified getPage() for WikiCourses
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
            printDBG('[WikiCourses] URL normalization failed: %s' % str(e))

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
                printDBG('[WikiCourses] getPage attempt %d failed: %s' % (attempt, str(e)))

            time.sleep(1.5)

        printDBG('[WikiCourses] getPage failed after %d retries: %s' % (max_retries, baseUrl))
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################

    def listMainMenu(self, cItem):
        printDBG('WikiCourses.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'main_categories', 'title': 'Courses'},
        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder

        self.SERIES_CAT_TAB = [
            {'category': 'list_course', 'title': 'Course Type', 'url': self.getFullUrl('categories/')},
        ]

    def listSeriesCategories(self, cItem):
        printDBG('WikiCourses.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listCourseType(self, cItem):
        printDBG('WikiCourses.listCourseType >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listCourseType: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK (DO NOT CHANGE)
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<div class="category-box">',
            '</section>',
            True
        )[1]

        if not main_block:
            printDBG('listCourseType: No main_block found')
            return

        ###################################################
        # PARSE ITEMS
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(
            main_block,
            '<div class="category-box">',
            '</a>'
        )

        printDBG('listCourseType: Found %d items' % len(items))

        for item in items:

            ##########################################
            # TITLE
            ##########################################
            title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>', False)[1]
            )

            ##########################################
            # DESCRIPTION  (YOUR REQUEST)
            ##########################################
            desc = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    item,
                    '<p class="light-text fs-6">',
                    '</p>',
                    False
                )[1]
            )

            ##########################################
            # IMAGE
            ##########################################
            icon = self.cm.ph.getSearchGroups(
                item,
                r'data-src="([^"]+)"'
            )[0]
            icon = self.getFullUrl(icon)

            ##########################################
            # URL  - last <a ...>
            ##########################################
            url = self.cm.ph.getSearchGroups(
                item,
                r'<a[^>]+href="([^"]+)"'
            )[0]
            url = self.getFullUrl(url)

            ##########################################
            # COLOR DESC
            ##########################################
            full_desc = f"{E2ColoR('yellow')}{desc}{E2ColoR('white')}"

            ##########################################
            # ADD
            ##########################################
            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': full_desc,
                'category': 'list_courseid'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listCourseType: No category-box items found')

    def listCourseId(self, cItem):
        printDBG('WikiCourses.listCourseId >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listCourseId: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK (DO NOT CHANGE)
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<div class="sub-category-box',
            '</section>',
            True
        )[1]

        if not main_block:
            printDBG('listCourseId: No main_block found')
            return

        ###################################################
        # PARSE ITEMS
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="sub-category-box', '</a>')
        items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="sub-category-box', '</a>')[0]
        printDBG('items1.listCourseId >>> %s' % items1)
        printDBG('listCourseId: Found %d items' % len(items))

        for item in items:
            title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<h3 class="fs-6 text-dark mt-2 fw-bold">', '</h3>', False)[1])

            ##########################################
            # DESCRIPTION -> <p class="mb-0 mt-2 light-text">
            ##########################################
            desc = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    item,
                    '<p class="mb-0 mt-2 light-text">',
                    '</p>',
                    False
                )[1]
            )

            ##########################################
            # COURSE COUNT  -> <span class="light-text d-block mt-2 text-dark">
            ##########################################
            course_count = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    item,
                    '<span class="light-text d-block mt-2 text-dark">',
                    '</span>',
                    False
                )[1]
            )

            ##########################################
            # IMAGE
            ##########################################
            icon = self.cm.ph.getSearchGroups(
                item,
                r'data-src="([^"]+)"'
            )[0]
            icon = self.getFullUrl(icon)

            ##########################################
            # URL  -> SECOND <a ... href="...">
            ##########################################
            url = self.cm.ph.getSearchGroups(
                item,
                r'<a[^>]+href="([^"]+)"'
            )[0]
            url = self.getFullUrl(url)

            ##########################################
            # COLOR DESC + COURSE COUNT
            ##########################################
            full_desc = (
                f"{E2ColoR('yellow')}{desc}{E2ColoR('white')}\n"
                f"{E2ColoR('green')}{course_count}{E2ColoR('white')}"
            )

            ##########################################
            # ADD DIRECTORY
            ##########################################
            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': full_desc,
                'category': 'list_series'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listCourseType: No category-box items found')

    def listSeriesUnits(self, cItem):
        printDBG('WikiCourses.listSeriesUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listSeriesUnits: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<section', '</section>', True)[1]
        if not main_block:
            printDBG('listSeriesUnits: No main_block found')
            return

        ###################################################
        # PARSE SERIES ITEMS
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="course-box', '<i class="fas fa-user')
        #items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="course-box', '<i class="fas fa-user')[0]
        #printDBG('items1.listSeriesUnits >>> %s' % items1)
        printDBG('listSeriesUnits: Found %d items' % len(items))

        for item in items:
            # --- URL ---
            # extract only the FIRST <a ...> block
            first_a = self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>', False)[1]

            # --- URL ---
            url = self.cm.ph.getSearchGroups(first_a, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            # --- TITLE ---
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(first_a, r'title="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(first_a, '<h3', '</h3>', False)[1])

            # --- IMAGE ---
            icon = self.cm.ph.getSearchGroups(first_a, r'data-src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)

            # --- DESCRIPTION ---
            desc = f"{E2ColoR('yellow')}Click to view episodes{E2ColoR('white')}"

            # --- ADD ITEM ---
            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'list_series_episodes'
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listSeriesUnits: No <article> items found')

    def listSeriesEpisodes(self, cItem):
        printDBG('WikiCourses.listSeriesEpisodes >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listSeriesEpisodes: failed to load page')
            return

        ###################################################
        # EPISODE LIST BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<div class="playlist-videos">',
            '</section>',
            True
        )[1]

        if not main_block:
            printDBG('listSeriesEpisodes: No main_block found')
            return

        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<a', '</a>')
        items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<a', '</a>')[0]
        printDBG('items1.listSeriesEpisodes >>> %s' % items1)
        printDBG('listSeriesEpisodes: Found %d episode items' % len(items))

        if not items:
            printDBG('listSeriesEpisodes: No episode items found')
            return

        ###################################################
        # PARSE EPISODES
        ###################################################
        for item in items:

            ##########################################
            # Episode URL
            ##########################################
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            ##########################################
            # Episode Number  <span class="primary-clr fw-bold">1</span>
            ##########################################
            ep_num_raw = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<span', '</span>', False)[1]
            )
            ep_num = ep_num_raw.replace('class="primary-clr fw-bold">', '')
            printDBG('ep_num.listSeriesEpisodes >>> %s' % ep_num)

            if not ep_num.isdigit():
                ep_num = ""   # safe fallback

            ##########################################
            # Episode Title  <p class="m-0"> … </p>
            ##########################################
            title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<p class="m-0">', '</p>', False)[1]
            )

            # Merge number + title
            if ep_num:
                title = f"{ep_num}. {title}"

            ##########################################
            # Duration  <i class="far fa-clock"></i><span>8:36</span>
            ##########################################
            duration = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<i class="far fa-clock"></i>', '</div>', False)[1]
            )
            printDBG('duration1.listSeriesEpisodes >>> %s' % duration)

            if not duration:
                duration = "غير متاح"

            ##########################################
            # Poster
            ##########################################
            icon = cItem.get('icon', '')

            ##########################################
            # Desc
            ##########################################
            desc = f"المدة: {duration}"

            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'explore_item'
            })
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG('WikiCourses.exploreItems >>> %s' % cItem)
        url = cItem['url']
        printDBG('url.exploreItems >>> %s' % url)

        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG('exploreItems: failed to load page')
            return

        # Extract main block (DO NOT CHANGE start/end markers)
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<div class="playlist-content',
            '<div class=" col-lg-4',
            True
        )[1]
        printDBG('main_block.exploreItems >>> %s' % main_block)

        if not main_block:
            printDBG('exploreItems: No main_block found')
            return


        ##############################################
        # EXTRACT VIDEO URL  (decode HTML entities!)
        ##############################################
        raw_video_url = self.cm.ph.getSearchGroups(
            main_block,
            r'<source[^>]+src="([^"]+)"'
        )[0]

        # Convert &amp; → &
        video_url = self.getFullUrl(raw_video_url.replace('&amp;', '&'))
        printDBG('video_url.exploreItems >>> %s' % video_url)

        ##############################################
        # EXTRACT VIDEO NAME/TITLE
        ##############################################
        name = self.cleanHtmlStr(
            self.cm.ph.getDataBeetwenMarkers(
                main_block,
                '<p class="my-2 fw-bold">',
                '</p>',
                False
            )[1]
        )
        printDBG('video_name.exploreItems >>> %s' % name)

        ##############################################
        # EXTRACT DURATION (المدة)
        ##############################################
        duration = self.cleanHtmlStr(
            self.cm.ph.getDataBeetwenMarkers(
                main_block,
                '<span>المدة:</span>',
                '</h5>',
                False
            )[1]
        )

        ##############################################
        # EXTRACT SIZE (الحجم)
        ##############################################
        size = self.cleanHtmlStr(
            self.cm.ph.getDataBeetwenMarkers(
                main_block,
                '<span>الحجم:</span>',
                '</h5>',
                False
            )[1]
        )

        ##############################################
        # BUILD DESC
        ##############################################
        desc = "المدة: %s | الحجم: %s" % (duration, size)

        ##############################################
        # ADD VIDEO ENTRY  (NO COLORS)
        ##############################################
        params = dict(cItem)
        params.update({
            'title': name,
            'url': video_url,
            'desc': desc,
            'category': 'video',
            'type': 'video',
        })
        self.addVideo(params)

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('WikiCourses.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'WikiCourses - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 0}]

    def getVideoLinks(self, url):
        printDBG("WikiCourses.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('WikiCourses.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'main_categories':
            self.listSeriesCategories(self.currItem)
        elif category == 'list_course':
            self.listCourseType(self.currItem)
        elif category == 'list_courseid':
            self.listCourseId(self.currItem)
        elif category == 'list_series':
            self.listSeriesUnits(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)
        elif category == 'list_series_episodes':
            self.listSeriesEpisodes(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WikiCourses(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
