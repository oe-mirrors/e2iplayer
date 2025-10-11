# -*- coding: utf-8 -*-
# Last modified: 11/10/2025 - popking (odem2014)
# typical import for a standard host
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
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re, time
import base64
###################################################

def gettytul():
    return 'https://ciimaclub.club/'  # main url of host

class CimaClub(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cimaclub', 'cookie': 'cimaclub.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + 'search'
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/popking159/softcam/refs/heads/master/tuktuk.png"
        self.AJAX_URL = self.MAIN_URL + '/wp-content/themes/CimaClub/ajaxCenter/Home/AdvFiltering.php'

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
                printDBG('CimaClub.getPage retry %d failed: %s' % (attempt + 1, str(e)))

            # Cloudflare timing window delay
            time.sleep(1.5)

        printDBG(f"[CimaClub] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ''


    ###################################################
    # MAIN MENU
    ###################################################
    def listMainMenu(self, cItem):
        printDBG('CimaClub.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'list_categories', 'title': _('الرئيسية'), 'url': self.MAIN_URL},
            {'category': 'movies_categories', 'title': _('الافلام')},
            {'category': 'series_categories', 'title': _('المسلسلات')},
            {'category': 'search', 'title': _('بحث'), 'search_item': True}
        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_movies', 'title': _('افلام اجنبية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_movies', 'title': _('افلام عربية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_movies', 'title': _('افلام اسيوية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_movies', 'title': _('افلام هندية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a/')},
            {'category': 'list_movies', 'title': _('افلام انيمى'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': _('مسلسلات اجنبية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_series', 'title': _('مسلسلات اسيوية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': _('مسلسلات عربية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_series', 'title': _('مسلسلات تركية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': _('مسلسلات انيمى'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'list_series', 'title': _('مسلسلات مدبلجة'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')}
        ]

    def listMoviesCategories(self, cItem):
        printDBG('CimaClub.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG('CimaClub.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    ###################################################
    # LIST CATEGORIES
    ###################################################
    def listCategories(self, cItem):
        printDBG('CimaClub.listCategories')

        sts, data = self.getPage(self.MAIN_URL)
        printDBG("data.listCategories [%s]" % data)
        if not sts:
            return

        # Get only the dropdown section
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="dropdown select-menu">', '</div>', False)[1]
        printDBG("tmp.listCategories [%s]" % tmp)
        if not tmp:
            printDBG('No dropdown menu found')
            return

        # Extract all category <li> blocks
        cat_blocks = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        printDBG('Found %d categories' % len(cat_blocks))

        for item in cat_blocks:
            cat_id = self.cm.ph.getSearchGroups(item, r'data-cat="([^"]+)"')[0]
            cat_name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span', '</span>')[1])
            if not cat_name or cat_name == '.':
                continue

            params = dict(cItem)
            params.update({
                'category': 'list_items',
                'title': cat_name,
                'cat_id': cat_id
            })
            self.addDir(params)

    ###################################################
    # LIST ITEMS FROM CATEGORY (AJAX POST)
    ###################################################
    def listItems(self, cItem):
        printDBG('CimaClub.listItems >>> %s' % cItem)
        cat_id = cItem.get('cat_id', '')
        if not cat_id:
            return

        post_data = {'category': cat_id}
        sts, data = self.getPage(self.AJAX_URL, post_data=post_data)
        if not sts:
            return

        # Extract each movie box cleanly
        blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="Small--Box">', '</div>')
        printDBG('Found %d items' % len(blocks))

        for block in blocks:
            url = self.cm.ph.getSearchGroups(block, r'href="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(block, r'src="([^"]+)"')[0]

            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'title="([^"]+)"')[0]).replace("مترجم اون لاين", "")
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, '<p>', '</p>', False)[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, '<span style=', '</span>', False)[1])

            params = dict(cItem)
            params.update({
                'title': title,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': '%s | %s' % (quality, desc),
                'category': 'explore_items'
            })
            self.addDir(params)

    ###################################################
    # LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
    ###################################################
    def listUnits(self, cItem):
        printDBG('CimaClub.listUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listUnits: failed to load page')
            return

        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="BlocksHolder"', '<div class="pagination">', False)[1]
        #printDBG('main_block.listUnits >>> %s' % main_block)
        if not main_block:
            main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div id="MainFiltar"', '</div>', False)[1]

        if not main_block:
            printDBG('listUnits: No BlocksHolder/MainFiltar found')
            return

        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="Small--Box', '</div>')
        #printDBG('items.listUnits >>> %s' % items)
        printDBG('listUnits: Found %d items' % len(items))

        for item in items:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue

            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]

            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2>', '</h2>', False)[1])

            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span style=', '</span>', False)[1])

            params = dict(cItem)
            params.update({
                'title': title.replace("مترجم اون لاين", "").strip(),
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'desc': '%s | %s' % (quality, desc),
                'category': 'explore_items'
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
                    'title': '<<< ' + _('السابق'),
                    'url': self.getFullUrl(prev_url),
                    'category': 'list_movies'
                })
                self.addDir(params)
                printDBG('listUnits: Found previous page %s' % prev_url)

            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('التالي') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': 'list_movies'
                })
                self.addDir(params)
                printDBG('listUnits: Found next page %s' % next_url)

    ###################################################
    # EXPLORE ITEM (get list of servers)
    ###################################################
    def exploreItems(self, cItem):
        printDBG('CiimaClub.exploreItems >>> %s' % cItem)

        url = cItem['url']
        # Add "watch/" to the movie page URL
        if not url.endswith('/'):
            url += '/'
        url += 'watch/'
        printDBG('url.exploreItems >>> %s' % url)

        sts, data = self.getPage(url)
        printDBG('data.exploreItems >>> %s' % data)
        if not sts:
            return

        # Extract the main <ul id="watch"> section
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch">', '</ul>', False)[1]
        printDBG('watch_list.exploreItems >>> %s' % watch_list)
        if not watch_list:
            printDBG('No watch list found')
            return

        # Get all <li> blocks between markers
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, '<li', '</li>')
        printDBG('li_items.exploreItems >>> %s' % li_items)
        printDBG('Found %d servers' % len(li_items))

        for item in li_items:
            # Extract server name and URL
            url = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0]
            printDBG('url.exploreItems >>> %s' % url)
            if not url:
                continue
            # Extract domain (remove https://, www., and path)
            title = url.replace('https://', '').replace('http://', '').split('/')[0]
            title = title.replace('www.', '').strip()
            title = self.cleanHtmlStr(title)
            printDBG('title.exploreItems >>> %s' % title)
            if not title:
                title = self.cm.ph.getSearchGroups(item, r'>([^<]+)</span>')[0].strip()

            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'category': 'video',
                'type': 'video',
            })
            self.addVideo(params)

        if len(li_items) == 0:
            printDBG('No <li> items found in <ul id="watch">')


    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('CimaClub.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'CimaClub - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("CimaClub.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaClub.listSearchResult searchPattern[%s] searchType[%s]" % (searchPattern, searchType))
        post_data = {'search': searchPattern}
        sts, data = self.getPage(self.SEARCH_URL, post_data=post_data)
        if not sts:
            return

        results = re.findall(r'<a href="([^"]+)" title="([^"]+)" class="recent--block".*?data-src="([^"]+)"', data, re.S)
        for (url, title, icon) in results:
            params = dict(cItem)
            params.update({
                'title': self.cleanHtmlStr(title),
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl(icon),
                'category': 'explore_items'
            })
            self.addDir(params)


    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('CimaClub.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem)
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
        elif category == 'search':
            self.listSearchResult(cItem, cItem.get('search_pattern', ''), cItem.get('search_type', ''))

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
        CHostBase.__init__(self, CimaClub(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
