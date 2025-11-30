# -*- coding: utf-8 -*-
# Last modified: 30/11/2025 - popking (odem2014)
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
from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
###################################################
# FOREIGN import
###################################################
import re
import base64
###################################################
config.plugins.iptvplayer.topcinema_hosts = ConfigSelection(default="https://topcinema.surf/", choices=[("https://topcinema.surf/", "https://topcinema.surf/"), ("https://topcinema.buzz/", "https://topcinema.buzz/")])

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("host") + ":", config.plugins.iptvplayer.topcinema_hosts))
    return optionList


def gettytul():
    return config.plugins.iptvplayer.topcinema_hosts.value


class TopCinema(CBaseHostClass):

    def __init__(self):
        # init global variables for this class

        CBaseHostClass.__init__(self, {'history': 'topcinema', 'cookie': 'topcinema.cookie'})  # names for history and cookie files in cache
        self.ph = ph

        # vars default values

        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + '?s='

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

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG('TopCinema.listMainMenu')

        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {'category': 'movies_folder', 'title': 'الافلام'},
            {'category': 'series_folder', 'title': 'المسلسلات'},
        ] + self.searchItems()

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_items', 'title': 'English', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': 'Asian', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': 'Anime', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'list_items', 'title': 'Turkish', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': 'Arabic', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': 'Indian', 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a/')},
            {'category': 'list_items', 'title': 'WWE Shows', 'url': self.getFullUrl('/category/%d8%b9%d8%b1%d9%88%d8%b6-%d9%85%d8%b5%d8%a7%d8%b1%d8%b9%d8%a9/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'series', 'title': 'Arabic', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'series', 'title': 'English', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'series', 'title': 'Turkish', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'series', 'title': 'Asian', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'series', 'title': 'Indian', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')},
            {'category': 'series', 'title': 'Anime', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'series', 'title': 'Dubbed', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'series', 'title': 'Ramadan 2025', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2025/')},
            {'category': 'series', 'title': 'Ramadan 2024', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2024/')},
            {'category': 'series', 'title': 'Ramadan 2023', 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2023/')},
            {'category': 'series', 'title': 'TV Shows', 'url': self.getFullUrl('/category/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/')}
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

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<main class="site-inner', '</main>', True)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', True)

        for m in items:

            ##############################################################
            # URL
            ##############################################################
            url = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]

            if not url:
                continue

            ##############################################################
            # Title (clean Arabic & English)
            ##############################################################
            raw_title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            title = raw_title.replace('مترجم اون لاين', '').replace('مشاهدة', '').strip()

            ##############################################################
            # Poster (prefer data-src → fallback to src)
            ##############################################################
            poster = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not poster:
                poster = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            if not poster:
                poster = "https://topcinema.surf/wp-content/uploads/2025/10/cover.jpg"

            ##############################################################
            # Quality  <span style="">1080p WEB-DL</span>
            ##############################################################
            quality = self.cm.ph.getSearchGroups(m, r'<span[^>]*>([^<]+)</span>')[0]

            ##############################################################
            # Category  <li class="category">افلام اجنبي</li>
            ##############################################################
            category = self.cm.ph.getSearchGroups(m, r'<li class="category">([^<]+)</li>')[0]

            ##############################################################
            # Story inside <p> ... </p>
            ##############################################################
            story = self.cm.ph.getSearchGroups(m, r'<p>([^<]+)</p>')[0]

            ##############################################################
            # URL Fixing (Arabic encoding)
            ##############################################################
            # Encode only last filename part
            try:
                baseurl, filename = url.rsplit('/', 1)
                filename = urllib_quote_plus(filename)
                fixed_url = baseurl + '/' + filename
            except:
                fixed_url = url

            params = {
                'category': 'explore_item',
                "good_for_fav": True,
                'title': title,
                'url': fixed_url,
                'icon': poster,
                'quality': quality,
                'cat': category,
                'desc': story
            }

            printDBG("ITEM >>> " + str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', True)[1]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

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
        printDBG("TopCinema.listSeriesItems [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            return

        ############################################################
        # Extract series block (All episodes)
        ############################################################
        tmp = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<div class="BlocksHolder',
            '<script type="speculationrules',
            True
        )[1]

        data_items = self.cm.ph.getAllItemsBeetwenMarkers(
            tmp, '<div class="Small--Box', '</a>', True
        )

        if not data_items:
            # fallback if needed
            parts = tmp.split('<div class="Small--Box')
            data_items = ['<div class="Small--Box' + p for p in parts[1:]]

        for m in data_items:

            ############################################################
            # URL
            ############################################################
            url = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]

            if not url:
                continue

            ############################################################
            # Title
            ############################################################
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]

            ############################################################
            # Episode number
            ############################################################
            episode = self.cm.ph.getSearchGroups(m, r'<span>الحلقة</span>\s*<em>(\d+)</em>')[0]

            ############################################################
            # Story inside <p>
            ############################################################
            story = self.cm.ph.getDataBeetwenMarkers(m, '<p>', '</p>', False)[1].strip()

            ############################################################
            # Icon (data-src preferred)
            ############################################################
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]

            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            # Fallback icon
            if not pureicon:
                pureicon = "https://topcinema.surf/wp-content/uploads/2025/10/cover.jpg"

            icon = pureicon.strip()

            ############################################################
            # Category
            ############################################################
            category = self.cm.ph.getSearchGroups(m, r'<li class="category">([^<]+)</li>')[0]

            ############################################################
            # Build params
            ############################################################
            params = {
                'category': 'show_seasons',
                'title': title,
                "good_for_fav": True,
                'url': url,
                'icon': icon,
                'episode': episode,
                'desc': story,
                'category_name': category,
                'good_for_fav': True
            }

            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            params = dict(cItem)
            params.update({'title': 'Next Page ▶', 'url': next_page, 'category': 'series'})
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            params = dict(cItem)
            params.update({'title': '◀ Previous Page', 'url': prev_page, 'category': 'series'})
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("TopCinema.exploreItems [%s]" % cItem)
        raw_url = cItem['url']
        url = raw_url + 'watch/'

        sts, data = self.getPage(url)
        if not sts:
            return

        ##########################################################
        # Extract servers block
        ##########################################################
        server_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="ServersList"', '</ul>', False
        )[1]

        printDBG("server_block.exploreItems [%s]" % server_block)

        ##########################################################
        # Extract <li> items
        ##########################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(server_block, '<li', '</li>')

        for item in items:

            ##########################################################
            # Extract Base64 link from data-watch
            ##########################################################
            raw = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0]

            if not raw:
                continue

            ##########################################################
            # Extract ONLY base64 part
            ##########################################################
            base64_part = raw.rstrip('/').split('/')[-1]

            ##########################################################
            # Decode Base64
            ##########################################################
            try:
                import base64
                decoded_url = base64.b64decode(base64_part).decode('utf-8')
            except Exception as e:
                printDBG("Base64 decode error: %s" % e)
                continue

            ##########################################################
            # Extract title (server name)
            ##########################################################
            title = self.cleanHtmlStr(item)
            if not title:
                title = "Server"

            printDBG("Found server title: %s" % title)
            printDBG("Decoded stream link: %s" % decoded_url)

            ##########################################################
            # Add stream
            ##########################################################
            params = MergeDicts(cItem, {
                'title': title,
                'url': decoded_url,
                'type': 'video',
                'category': 'video',
                'need_resolve': 1
            })

            self.addVideo(params)

    def showSeasons(self, cItem):
        printDBG("TopCinema.showSeasons >>> %s" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            return

        ############################################################
        # Extract seasons block
        ############################################################
        tmp = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<section class="allseasonss',
            '</section>',
            True
        )[1]

        printDBG('tmp.showSeasons >>> %s' % tmp)

        # Each season is one <div class="Small--Box"> ... </a>
        seasons = self.cm.ph.getAllItemsBeetwenMarkers(
            tmp,
            '<div class="Small--Box',
            '</a>',
            True
        )

        for s in seasons:

            ############################################################
            # URL
            ############################################################
            url = self.cm.ph.getSearchGroups(s, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            ############################################################
            # Title from <h2>
            ############################################################
            title = self.cm.ph.getDataBeetwenMarkers(s, '<h2>', '</h2>', False)[1].strip()

            if not title:
                # fallback to title="..." attribute
                title = self.cm.ph.getSearchGroups(s, r'title="([^"]+)"')[0]

            if not title:
                title = "Season"

            ############################################################
            # Icon: Prefer data-src, fallback to src
            ############################################################
            icon = self.cm.ph.getSearchGroups(s, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(s, r'src="([^"]+)"')[0]

            # Final fallback if still empty
            if not icon:
                icon = "https://topcinema.surf/wp-content/uploads/2025/10/cover.jpg"

            icon = icon.strip()

            ############################################################
            # Add the season entry
            ############################################################
            params = dict(cItem)
            params.update({
                'title': title,
                "good_for_fav": True,
                'url': url,
                'icon': icon,
                'category': 'show_episodes'
            })

            printDBG("season.params >>> %s" % params)
            self.addDir(params)

    def showEpisodes(self, cItem):
        printDBG("TopCinema.showEpisodes >>> %s" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            return

        #########################################################
        # Extract the episodes section
        #########################################################
        tmp = self.cm.ph.getDataBeetwenMarkers(
            data,
            '<section class="allepcont',
            '</section>',
            True
        )[1]

        printDBG('tmp.showEpisodes >>> %s' % tmp)

        #########################################################
        # Extract each <a ... </a> block (each episode)
        #########################################################
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(
            tmp,
            '<a ',
            '</a>',
            True
        )
        data_items.reverse()

        printDBG('episodes.count >>> %s' % len(data_items))

        # If nothing found, fallback to Small--Box
        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        #########################################################
        # Parse each episode
        #########################################################
        for ep in data_items:

            #############################################
            # Episode URL
            #############################################
            pureurl = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
            if not pureurl:
                continue

            # Ensure URL is encoded correctly
            baseurl, filenameurl = pureurl.rsplit('/', 1)
            url = baseurl + '/' + urllib_quote_plus(filenameurl)

            #############################################
            # Title (correct: use <h2> text)
            #############################################
            title = self.cm.ph.getDataBeetwenMarkers(ep, '<h2>', '</h2>', False)[1].strip()

            if not title:
                # fallback to title="..."
                title = self.cm.ph.getSearchGroups(ep, r'title="([^"]+)"')[0]

            if not title:
                title = "Episode"

            #############################################
            # Icon (prefer data-src → fallback to src)
            #############################################
            pureicon = self.cm.ph.getSearchGroups(ep, r'data-src="([^"]+)"')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(ep, r'src="([^"]+)"')[0]

            icon = ''
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                icon = baseicon + '/' + urllib_quote_plus(filenameicon)

            #############################################
            # Add episode to list
            #############################################
            params = {
                'category': 'explore_item',
                'title': title,
                "good_for_fav": True,
                'icon': icon,
                'url': url,
                'good_for_fav': True
            }

            printDBG("episode.params >>> %s" % params)
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            params = dict(cItem)
            params.update({'title': 'Next Page ▶', 'url': next_page, 'category': 'show_episodes'})
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            params = dict(cItem)
            params.update({'title': '◀ Previous Page', 'url': prev_page, 'category': 'show_episodes'})
            self.addDir(params)

    def listSearchResult(self, cItem, search_pattern, search_type):
        printDBG("TopCinema.listSearchResult cItem[%s], search_pattern[%s] search_type[%s]" % (cItem, search_pattern, search_type))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('?s=') + urllib_quote_plus(search_pattern)
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

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('TopCinema.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'TopCinema - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("TopCinema.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

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
