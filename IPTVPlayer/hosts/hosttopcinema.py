# -*- coding: utf-8 -*-
# Last modified: 08/10/2025 - popking (odem2014)
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
###################################################
# FOREIGN import
###################################################
import re
import base64
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://topcinema.buzz/'  # main url of host


class TopCinema(CBaseHostClass):

    def __init__(self):
        # init global variables for this class

        CBaseHostClass.__init__(self, {'history': 'topcinema', 'cookie': 'topcinema.cookie'})  # names for history and cookie files in cache
        self.ph = ph

        # vars default values

        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = 'https://web6.topcinema.cam/search'

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

    def getLinksForVideo(self, cItem):
        printDBG("TopCinema.getLinksForVideo [%s]" % cItem)
        linksTab = []
        url = cItem['url']

        sts, data = self.getPage(url, self.defaultParams)
        if not sts or not data:
            return []

        # 1️⃣ Try to extract iframe src directly
        iframeUrl = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0]
        if iframeUrl:
            printDBG("Found iframe: %s" % iframeUrl)
            linksTab.append({
                'name': self.up.getHostName(iframeUrl).capitalize(),
                'url': strwithmeta(iframeUrl, {'Referer': url}),
                'need_resolve': 1
            })

        # 2️⃣ Try to extract encoded/redirected link from JS (common in sharevid.online)
        if not iframeUrl:
            encoded = self.cm.ph.getSearchGroups(data, r"atob\('([^']+)'")[0]
            if encoded:
                import base64
                try:
                    decoded = base64.b64decode(encoded).decode('utf-8')
                    printDBG("Decoded base64 URL: %s" % decoded)
                    linksTab.append({
                        'name': self.up.getHostName(decoded).capitalize(),
                        'url': strwithmeta(decoded, {'Referer': url}),
                        'need_resolve': 1
                    })
                except Exception as e:
                    printDBG("Base64 decode error: %s" % str(e))

        # 3️⃣ Try to extract var URL (e.g. var urlPlay = '...')
        if not linksTab:
            js_url = self.cm.ph.getSearchGroups(data, r"var\s+urlPlay\s*=\s*['\"]([^'\"]+)")[0]
            if js_url:
                printDBG("Found JS urlPlay: %s" % js_url)
                linksTab.append({
                    'name': self.up.getHostName(js_url).capitalize(),
                    'url': strwithmeta(js_url, {'Referer': url}),
                    'need_resolve': 1
                })

        # 4️⃣ Try to extract <source> video src (sometimes they exist)
        sources = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>')
        for s in sources:
            src = self.cm.ph.getSearchGroups(s, r'src="([^"]+)"')[0]
            if src:
                printDBG("Found direct video src: %s" % src)
                linksTab.append({
                    'name': self.up.getHostName(src).capitalize(),
                    'url': strwithmeta(src, {'Referer': url}),
                    'need_resolve': 0
                })

        # 5️⃣ Fallback to urlparser
        if not linksTab:
            printDBG("TopCinema.getLinksForVideo: no links found, using parser fallback...")
            resolved = self.getVideoLinks(url)
            for entry in resolved:
                if isinstance(entry, dict):
                    linksTab.append(entry)
                else:
                    linksTab.append({
                        'name': self.up.getHostName(url),
                        'url': entry,
                        'need_resolve': 1
                    })

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG('TopCinema.getVideoLinks >>> %s' % videoUrl)
        urlsTab = []

        # 🔹 Add VikingFile support
        if 'vikingfile.com' in videoUrl:
            printDBG('Detected VikingFile link, trying to extract...')
            sts, data = self.cm.getPage(videoUrl)
            if not sts:
                printDBG('Failed to load VikingFile page')
                return urlsTab

            # 1️⃣ Try direct <video src="...">
            video = self.cm.ph.getSearchGroups(data, r'<video[^>]+src=["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']')[0]
            if video:
                printDBG('Found direct video src: %s' % video)
                urlsTab.append({'name': 'VikingFile', 'url': video, 'need_resolve': 0})
                return urlsTab

            # 2️⃣ Try Base64 encoded URL (inside atob("..."))
            b64_url = self.cm.ph.getSearchGroups(data, r'atob\(["\']([^"\']+)["\']\)')[0]
            if b64_url:
                try:
                    import base64
                    decoded = base64.b64decode(b64_url).decode('utf-8')
                    printDBG('Decoded Base64 VikingFile URL: %s' % decoded)
                    if decoded.startswith('http'):
                        urlsTab.append({'name': 'VikingFile (decoded)', 'url': decoded, 'need_resolve': 0})
                        return urlsTab
                except Exception as e:
                    printDBG('VikingFile decode error: %s' % e)

            # 3️⃣ Try embedded iframe with /f/ pattern
            iframe = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src=["\'](https?://vikingfile\.com/f/[^"\']+)["\']')[0]
            if iframe:
                printDBG('Found VikingFile iframe: %s' % iframe)
                sts, iframe_data = self.cm.getPage(iframe)
                if sts:
                    video = self.cm.ph.getSearchGroups(iframe_data, r'<video[^>]+src=["\'](https?://[^"\']+)["\']')[0]
                    if video:
                        urlsTab.append({'name': 'VikingFile (iframe)', 'url': video, 'need_resolve': 0})
                        return urlsTab

            printDBG('VikingFile: no playable link found, may require CAPTCHA')
            return urlsTab

        # 🔹 keep your existing resolver for all other hosts
        return self.up.getVideoLinkExt(videoUrl)

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG('TopCinema.listMainMenu')

        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {'category': 'movies_folder', 'title': _('الافلام')},
            # {'category': 'series_folder', 'title': _('المسلسلات')},
        ] + self.searchItems()

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام اجنبي'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': _('افلام اسيوية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': _('افلام انيمى'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/')},
            {'category': 'list_items', 'title': _('افلام تركية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': _('افلام عربية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': _('افلام هندية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a/')}
        ]

        # self.SERIES_CAT_TAB = [
            # {'category': 'series', 'title': _('مسلسلات عربية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            # {'category': 'series', 'title': _('مسلسلات اجنبي'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/')},
            # {'category': 'series', 'title': _('مسلسلات تركية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            # {'category': 'series', 'title': _('مسلسلات اسيوية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/')},
            # {'category': 'series', 'title': _('مسلسلات انيمى'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/')},
            # {'category': 'series', 'title': _('مسلسلات مدبلجة'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            # {'category': 'series', 'title': _('مسلسلات رمضان 2025'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2025/')},
            # {'category': 'series', 'title': _('مسلسلات هندية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')}
        # ]

        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG('TopCinema.listMoviesFolder')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    # def listSeriesFolder(self, cItem):
        # printDBG('TopCinema.listSeriesFolder')
        # self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("TopCinema.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<main class="site-inner', '</main>', False)[1]
        # printDBG('tmp.listItems >>> %s' % tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', False)
        # printDBG('data_items.listItems >>> %s' % data_items)

        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            title = title.replace('مترجم اون لاين', '').strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + '/' + fixedfilenameurl + "watch/"

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            icon = ''
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + '/' + fixedfilenameicon

            params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': url}
            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', False)[1]
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
        printDBG("TopCinema.listSeriesItems ----------")

        sts, data = self.getPage(cItem['url'])
        printDBG("data.listSeriesItems ||||||||||||||||||||||||||||||||||||")
        printDBG(data)
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="BlocksHolder', '<script type="speculationrules', False)[1]
        printDBG("tmp.listSeriesItems ||||||||||||||||||||||||||||||||||||")
        printDBG(tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', False)
        printDBG("data_items.listSeriesItems ||||||||||||||||||||||||||||||||||||")
        printDBG(data_items)
        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            # title = re.sub(r'\s*مترجم\s*أ?ون\s*لاين\s*', '', title).strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + '/' + fixedfilenameurl + "watch/"
            printDBG(url)

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            icon = ''

            params = {'category': 'exploreSeriesItems', 'title': title, 'icon': icon, 'url': url}
            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

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

    def exploreItems(self, cItem):
        printDBG('TopCinema.exploreItems')
        url = cItem['url']
        printDBG("|||||||||||||||||exploreUrl||||||||||||||||||||")
        printDBG(url)

        sts, data = self.getPage(url)
        if not sts:
            return

        # Extract servers section
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="ServersList"', '</ul>', False)[1]
        printDBG("|||||||||||||||||Servers block||||||||||||||||||||")
        printDBG(tmp)

        # Extract each server <li>
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        printDBG("|||||||||||||||||servers count||||||||||||||||||||")
        printDBG(str(len(items)))

        for item in items:
            link = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+?)"')[0]
            if not link:
                continue

            title = self.cleanHtmlStr(item)
            if not title:
                title = 'Server'

            printDBG("Found server title: %s" % title)
            printDBG("Found server link: %s" % link)

            params = MergeDicts(cItem, {
                'title': title,
                'url': self.getFullUrl(link),
                'type': 'video',
                'category': 'video',
                'need_resolve': 1
            })
            self.addVideo(params)

    def exploreSeriesItems(self, cItem):
        printDBG('TopCinema.exploreSeriesItems')
        url = cItem['url']
        printDBG("|||||||||||||||||url_exploreSeriesItems||||||||||||||||||||")
        printDBG(url)

        sts, data = self.getPage(url)
        printDBG("|||||||||||||||||data_exploreSeriesItems||||||||||||||||||||")
        printDBG(data)
        if not sts:
            return

        # Extract servers section
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="ServersList"', '</ul>', False)[1]
        printDBG("|||||||||||||||||Servers block||||||||||||||||||||")
        printDBG(tmp)

        # Extract each server <li>
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        printDBG("|||||||||||||||||servers count||||||||||||||||||||")
        printDBG(str(len(items)))

        for item in items:
            link = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+?)"')[0]
            if not link:
                continue

            title = self.cleanHtmlStr(item)
            if not title:
                title = 'Server'

            printDBG("Found server title: %s" % title)
            printDBG("Found server link: %s" % link)

            params = MergeDicts(cItem, {
                'title': title,
                'url': self.getFullUrl(link),
                'type': 'video',
                'category': 'video',
                'need_resolve': 1
            })
            self.addVideo(params)

    def safe_b64decode(self, data):
        """Base64 decode with automatic padding fix."""
        data += '=' * (-len(data) % 4)
        return base64.b64decode(data).decode('utf-8')

    def showSeasons(self, cItem):
        printDBG("TopCinema.showSeasons >>> %s" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # Debug output for inspection
        printDBG("====== showSeasons PAGE DATA ======")
        printDBG(data)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allseasonss', '</section>', False)[1]
        seasons = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box Season', '</a>')
        seasons.reverse()

        printDBG("====== showSeasons seasons DATA ======")
        printDBG(seasons)

        for s in seasons:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(s, r'<h3[^>]*class="title"[^>]*>([^<]+)</h3>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(s, r'alt="([^"]+)"')[0])
            url = self.cm.ph.getSearchGroups(s, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            params = dict(cItem)
            params.update({
                'title': title or 'Season',
                'url': urljoin(url, 'list/'),
                'category': 'show_episodes',
            })
            self.addDir(params)

    def showEpisodes(self, cItem):
        printDBG("TopCinema.showSeasons >>> %s" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        printDBG("====== showEpisodes episodes DATA ======")
        printDBG(data)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Posts--List SixInRow">', '<div class="paginate">', False)[1]
        printDBG("====== showEpisodes tmp DATA ======")
        printDBG(tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', False)
        data_items.reverse()
        printDBG("====== showEpisodes data_items DATA in reverse ======")
        printDBG(data_items)

        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            # title = re.sub(r'\s*مترجم\s*أ?ون\s*لاين\s*', '', title).strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + '/' + fixedfilenameurl

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            icon = ''
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + '/' + fixedfilenameicon

            params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': urljoin(url, 'watch/'), }
            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

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

    def listSearchResult(self, cItem, search_pattern, search_type):
        printDBG("TopCinema.listSearchResult cItem[%s], search_pattern[%s] search_type[%s]" % (cItem, search_pattern, search_type))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search?q=') + urllib_quote_plus(search_pattern)
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
        # elif category == 'series_folder':
            # self.listSeriesFolder(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)
        elif category == 'explore_episodes':
            self.exploreSeriesItems(self.currItem)
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
