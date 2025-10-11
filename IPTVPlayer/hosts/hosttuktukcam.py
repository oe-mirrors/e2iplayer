# -*- coding: utf-8 -*-
# Last modified: 08/10/2025 - popking (odem2014)
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
import re
import base64
###################################################

def GetConfigList():
    return []


def gettytul():
    return 'https://tuk.cam/'  # main url of host


class TukTukCam(CBaseHostClass):

    def __init__(self):
        # init global variables for this class

        CBaseHostClass.__init__(self, {'history': 'tuktukcam', 'cookie': 'tuktukcam.cookie'})  # names for history and cookie files in cache

        # vars default values

        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = 'https://tuk.cam/search'

        # url for default icon
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/tuktuk.png"

        # default header and http params
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("TukTukCam.getLinksForVideo [%s]" % cItem)
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
            printDBG("TukTukCam.getLinksForVideo: no direct links found, calling getVideoLinks()")
            # Delegate to getVideoLinks for parser-based resolution
            resolved = self.getVideoLinks(cItem['url'])
            printDBG("TukTukCam.getLinksForVideo: resolved via parser: %s" % str(resolved))
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
        printDBG("TukTukCam.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG('TukTukCam.listMainMenu')
        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {'category': 'movies_folder', 'title': _('الافلام')},
            {'category': 'series_folder', 'title': _('المسلسلات')},
            {'category': 'anime_folder', 'title': _('انمي')},
        ] + self.searchItems()
        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام اجنبى مدبلجة'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'list_items', 'title': _('افلام اجنبية'), 'url': self.getFullUrl('/category/movies/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': _('افلام تركية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': _('افلام هندية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'series', 'title': _('مسلسلات اجنبية'), 'url': self.getFullUrl('/category/series/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'series', 'title': _('مسلسلات اسيوية'), 'url': self.getFullUrl('/category/series/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')}
        ]

        self.ANIME_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام انيمى'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'series', 'title': _('مسلسلات انيمى'), 'url': self.getFullUrl('/category/anime/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/')}
        ]
        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG('TukTukCam.listMoviesFolder')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG('TukTukCam.listSeriesFolder')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listAnimeFolder(self, cItem):
        printDBG('TukTukCam.listAnimeFolder')
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("TukTukCam.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # --- Extract movie/series blocks ---
        tmp = self.cm.ph.getDataBeetwenMarkers(data,'<section class="MasterArchiveSection loadFilter ArcArc"','</div></section>', False)[1]
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Block--Item">', '</a></div>')

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
            title = re.sub(r"مترجم\s*حصرى\s*اون\s*لاين\s*على\s*أكثر\s*من\s*سيرفر", "", title).strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + "/" + fixedfilenameurl + "watch/"

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
            baseicon, filenameicon = pureicon.rsplit('/', 1)
            fixedfilenameicon = urllib_quote_plus(filenameicon)
            icon = baseicon + "/" + fixedfilenameicon

            params = dict(cItem)
            params.update({'category': 'explore_item', 'title': title, 'icon': icon, 'url': url})
            printDBG(str(params))
            self.addDir(params)

        # --- Extract pagination section ---
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', False)[1]
        if pagination_block:
            # Get current page
            current_page = self.cm.ph.getSearchGroups(pagination_block, r'class="page-numbers current">(\d+)<')[0]
            current_page = int(current_page) if current_page.isdigit() else 1

            # Get next and previous URLs
            next_page = self.cm.ph.getSearchGroups(pagination_block, r'class="next page-numbers" href="([^"]+)"')[0]
            prev_page = self.cm.ph.getSearchGroups(pagination_block, r'class="prev page-numbers" href="([^"]+)"')[0]

            # Add "Previous Page"
            if prev_page:
                prev_url = self.getFullUrl(prev_page)
                params = dict(cItem)
                params.update({
                    'title': '◀ Previous Page',
                    'url': prev_url,
                    'category': 'list_items'
                })
                self.addDir(params)

            # Add "Next Page"
            if next_page:
                next_url = self.getFullUrl(next_page)
                params = dict(cItem)
                params.update({
                    'title': 'Next Page ▶',
                    'url': next_url,
                    'category': 'list_items'
                })
                self.addDir(params)

        printDBG("Pagination handled successfully.")


    def listSeriesItems(self, cItem):
        printDBG("TukTukCam.listSeriesItems ----------")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        series_dict = {}
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="MasterArchiveSection loadFilter ArcArc"', '</div></section>', False)[1]
        blocks = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Block--Item">', '</div></a></div>')

        for block in blocks:
            pureurl = self.getFullUrl(self.cm.ph.getSearchGroups(block, 'href="([^"]+?)"')[0])
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + "/" + fixedfilenameurl + "watch/"

            pureicon = self.cm.ph.getSearchGroups(block, 'data-src="([^"]+?)"')[0]
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + "/" + fixedfilenameicon
            else:
                icon = cItem.get('icon', '')

            desc = self.cm.ph.getSearchGroups(block, '<p[^>]*?>([^<]+?)</p>')[0]
            full_title = self.cm.ph.getSearchGroups(block, '<h3[^>]*?>([^<]+?)</h3>')[0].strip()
            clean_title = re.sub(r'(الحلقة\s*\d+.*|مترجمة.*|الاخيرة.*)', '', full_title, flags=re.UNICODE).strip()
            clean_title = re.sub(r'\s{2,}', ' ', clean_title)
            title = clean_title

            if title in series_dict:
                continue
            series_dict[title] = True

            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'explore_episodes',
            })
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', False)[1]

        nextPage = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        prevPage = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]

        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG("NEXT PAGE FOUND >>> %s" % nextPage)
            params = dict(cItem)
            params.update({
                'title': 'Next Page ▶',
                'url': nextPage,
                'category': 'series',
            })
            self.addDir(params)

        if prevPage:
            prevPage = self.getFullUrl(prevPage)
            printDBG("PREV PAGE FOUND >>> %s" % prevPage)
            params = dict(cItem)
            params.update({
                'title': '◀ Previous Page',
                'url': prevPage,
                'category': 'series',
            })
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG('TukTukCam.exploreItems')
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="watch--servers--list">', '</div></div>', False)[1]
        printDBG('listitems tmp |||||||||||||||||||||||||||||||||| print:')
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in items:
            # Extract the label (e.g. "سيرفر 1") and quality (data-qu="480")
            label = self.cm.ph.getSearchGroups(item, '<span>([^<]+)</span>')[0].strip()
            link = self.cm.ph.getSearchGroups(item, 'data-link="([^"]+?)"')[0]

            if not link:
                continue

            printDBG("Found server link: %s" % link)

            params = MergeDicts(cItem, {
                'title': label,
                'url': link,
                'type': 'video',
                'category': 'video',
                'need_resolve': 1
            })
            self.addVideo(params)

    def exploreSeriesItems(self, cItem):
        printDBG('TukTukCam.exploreSeriesItems')
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return

        # Extract the block that contains episodes
        episodes_block = self.cm.ph.getDataBeetwenMarkers(data,
            '<div class="episodes--list--side"', '></div></div>', False)[1]

        episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, '<a', '</a>')
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

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TukTukCam.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search?q=') + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG('TukTukCam.getFavouriteData')
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('TukTukCam.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('TukTukCam.setInitListFromFavouriteItem')
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TukTukCam.handleService start')

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
        elif category == 'series':
            self.listSeriesItems(self.currItem)
        # FOLDERS
        elif category == 'movies_folder':
            self.listMoviesFolder(self.currItem)
        elif category == 'series_folder':
            self.listSeriesFolder(self.currItem)
        elif category == 'ramadan_folder':
            self.listRamadanFolder(self.currItem)
        elif category == 'anime_folder':
            self.listAnimeFolder(self.currItem)
        elif category == 'other_folder':
            self.listOtherFolder(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)
        elif category == 'explore_episodes':
            self.exploreSeriesItems(self.currItem)
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
        CHostBase.__init__(self, TukTukCam(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
