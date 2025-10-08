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
import base64
###################################################
try:
	from urllib.parse import urlparse, parse_qs, urlencode, unquote
except ImportError:
	from urllib import urlencode, urlopen, unquote

LI_CLOSE = '</li>'

def GetConfigList():
    return []


def gettytul():
    return 'https://a.asd.homes/'  # main url of host


class ArabSeed(CBaseHostClass):

    def __init__(self):
        # init global variables for this class

        CBaseHostClass.__init__(self, {'history': 'arabseed', 'cookie': 'arabseed.cookie'})  # names for history and cookie files in cache
        # vars default values
        self.urlencode = urlencode
        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = 'https://a.asd.homes/search'

        # url for default icon
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/arabseed.png"

        # default header and http params
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        if any(ord(c) > 127 for c in base_url):
            base_url = urllib_quote_plus(base_url, safe="://")
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("ArabSeed.getLinksForVideo [%s]" % cItem)
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
            printDBG("ArabSeed.getLinksForVideo: no direct links found, calling getVideoLinks()")
            # Delegate to getVideoLinks for parser-based resolution
            resolved = self.getVideoLinks(cItem['url'])
            printDBG("ArabSeed.getLinksForVideo: resolved via parser: %s" % str(resolved))
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
        printDBG("ArabSeed.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG('ArabSeed.listMainMenu')

        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {'category': 'movies_folder', 'title': _('الافلام')},
            {'category': 'series_folder', 'title': _('المسلسلات')},
            {'category': 'ramadan_folder', 'title': _('رمضان')},
            {'category': 'anime_folder', 'title': _('انمي')},
            {'category': 'other_folder', 'title': _('اخري')},
        ] + self.searchItems()

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام Netfilx'), 'url': self.getFullUrl('/category/netfilx/%d8%a7%d9%81%d9%84%d8%a7%d9%85-netfilx/')},
            {'category': 'list_items', 'title': _('افلام اجنبي'), 'url': self.getFullUrl('/category/foreign-movies-6/')},
            {'category': 'list_items', 'title': _('افلام اسيوية'), 'url': self.getFullUrl('/category/asian-movies/')},
            {'category': 'list_items', 'title': _('افلام تركية'), 'url': self.getFullUrl('/category/turkish-movies/')},
            {'category': 'list_items', 'title': _('افلام عربي'), 'url': self.getFullUrl('/category/arabic-movies-6/')},
            {'category': 'list_items', 'title': _('افلام كلاسيكيه'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d9%84%d8%a7%d8%b3%d9%8a%d9%83%d9%8a%d9%87/')},
            {'category': 'list_items', 'title': _('افلام مدبلجة'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'list_items', 'title': _('افلام هندى'), 'url': self.getFullUrl('/category/indian-movies/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'series', 'title': _('مسلسلات Netfilx'), 'url': self.getFullUrl('/category/netfilx/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-netfilz/')},
            {'category': 'series', 'title': _('مسلسلات اجنبي'), 'url': self.getFullUrl('/category/foreign-series-2/')},
            {'category': 'series', 'title': _('مسلسلات تركيه'), 'url': self.getFullUrl('/category/turkish-series-2/')},
            {'category': 'series', 'title': _('مسلسلات عربي'), 'url': self.getFullUrl('/category/arabic-series-3/')},
            {'category': 'series', 'title': _('مسلسلات كرتون'), 'url': self.getFullUrl('/category/cartoon-series/')},
            {'category': 'series', 'title': _('مسلسلات كوريه'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d9%88%d8%b1%d9%8a%d9%87/')},
            {'category': 'series', 'title': _('مسلسلات مدبلجة'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'series', 'title': _('مسلسلات مصريه'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%b5%d8%b1%d9%8a%d9%87/')},
            {'category': 'series', 'title': _('مسلسلات هندية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')}
        ]

        self.RAMADAN_CAT_TAB = [
            {'category': 'series', 'title': _('مسلسلات رمضان 2025'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/ramadan-series-2025/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2024'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/ramadan-series-2024/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2023'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/ramadan-series-2023/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2022'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2022/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2021'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2021/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2020'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2020-hd/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2019'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2019/')}
        ]

        self.ANIME_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام انيميشن'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%8a%d9%85%d9%8a%d8%b4%d9%86/')},
            {'category': 'series', 'title': _('مسلسلات كرتون'), 'url': self.getFullUrl('/category/cartoon-series/')}
        ]

        self.OTHER_CAT_TAB = [
            {'category': 'list_items', 'title': _('اغاني عربي'), 'url': self.getFullUrl('/category/%d8%a7%d8%ba%d8%a7%d9%86%d9%8a-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': _('مصارعه'), 'url': self.getFullUrl('/category/wwe-shows/')},
            {'category': 'list_items', 'title': _('برامج تلفزيونية'), 'url': self.getFullUrl('/category/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': _('مسرحيات عربيه'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d8%b1%d8%ad%d9%8a%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/')}
        ]

        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG('ArabSeed.listMoviesFolder')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG('ArabSeed.listSeriesFolder')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listRamadanFolder(self, cItem):
        printDBG('ArabSeed.listRamadanFolder')
        self.listsTab(self.RAMADAN_CAT_TAB, cItem)

    def listAnimeFolder(self, cItem):
        printDBG('ArabSeed.listAnimeFolder')
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherFolder(self, cItem):
        printDBG('ArabSeed.listOtherFolder')
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("ArabSeed.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="blocks__section mt__30 mb__30', '</ul></div></div></section>', False)[1]
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li class="box__xs__2', LI_CLOSE)

        for m in data_items:
                   title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
                   pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
                   baseurl, filenameurl = pureurl.rsplit('/', 1)
                   fixedfilenameurl = urllib_quote_plus(filenameurl)
                   url = baseurl + "/" + fixedfilenameurl + "watch/"
                   pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
                   baseicon, filenameicon = pureicon.rsplit('/', 1)
                   fixedfilenameicon = urllib_quote_plus(filenameicon)
                   icon = baseicon + "/" + fixedfilenameicon
                   params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': url}
                   printDBG(str(params))
                   self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]

        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            printDBG("NEXT PAGE FOUND >>> %s" % next_page)
            params = dict(cItem)
            params.update({
                'title': 'Next Page ▶',
                'url': next_page,
                'category': 'list_items',
            })
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            printDBG("PREV PAGE FOUND >>> %s" % prev_page)
            params = dict(cItem)
            params.update({
                'title': '◀ Previous Page',
                'url': prev_page,
                'category': 'list_items',
            })
            self.addDir(params)

    def listSeriesItems(self, cItem):
        printDBG("ArabSeed.listSeriesItems ----------")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        seriesDict = {}  # Use to avoid duplicates

        blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="box__xs__2', LI_CLOSE)
        for block in blocks:
            pureurl = self.getFullUrl(self.cm.ph.getSearchGroups(block, 'href="([^"]+?)"')[0])
            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            baseurl, filenameurl = pureurl.rsplit('/', 1)
            url = baseurl + "/" + fixedfilenameurl
            if not url:
                continue

            pureicon = self.cm.ph.getSearchGroups(block, 'data-src="([^"]+?)"')[0]
            baseicon, filenameicon = pureicon.rsplit('/', 1)
            fixedfilenameicon = urllib_quote_plus(filenameicon)
            icon = baseicon + "/" + fixedfilenameicon
            desc = self.cm.ph.getSearchGroups(block, '<p[^>]*?>([^<]+?)</p>')[0]
            fullTitle = self.cm.ph.getSearchGroups(block, '<h3[^>]*?>([^<]+?)</h3>')[0].strip()

            # Remove episode numbers like "الحلقة 30" using regex
            title = re.sub(r'الحلقة\s*\d+', '', fullTitle, flags=re.UNICODE).strip()

            # Avoid duplicates
            if title in seriesDict:
                continue
            seriesDict[title] = True

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
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]

        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            printDBG("NEXT PAGE FOUND >>> %s" % next_page)
            params = dict(cItem)
            params.update({
                'title': 'Next Page ▶',
                'url': next_page,
                'category': 'series',
            })
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            printDBG("PREV PAGE FOUND >>> %s" % prev_page)
            params = dict(cItem)
            params.update({
                'title': '◀ Previous Page',
                'url': prev_page,
                'category': 'series',
            })
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("ArabSeed.exploreItems >>> %s" % cItem)
        url = cItem.get('url')
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        # --- Extractors ---
        def extract_first(patterns):
            for p in patterns:
                try:
                    v = self.cm.ph.getSearchGroups(data, p)[0]
                    if v:
                        return v.strip()
                except Exception:
                    continue
            return ''

        def extract_token_and_postid():
            token_patterns = [
                r"csrf__token['\"]:\s*['\"]([^'\"]+)",
                r"csrf_token['\"]:\s*['\"]([^'\"]+)",
                r"name=['\"]csrf-token['\"]\s+content=['\"]([^'\"]+)"
            ]
            postid_patterns = [
                r"psot_id['\"]:\s*'([^']+)'",
                r"post_id['\"]:\s*['\"]([^'\"]+)",
                r"post_id\s*:\s*'([^']+)'"
            ]
            return extract_first(token_patterns), extract_first(postid_patterns)

        token, post_id = extract_token_and_postid()
        if not token or not post_id:
            printDBG('[ArabSeed] Missing required POST params (csrf_token or post_id/psot_id)')
            return

        post_url = "https://a.asd.homes/get__watch__server/"
        servers = [0, 1, 2, 3, 4]
        qualities = [480, 720, 1080]

        # --- Helpers ---
        def make_payload(server, quality):
            return {
                'post_id': post_id,
                'quality': str(quality),
                'server': str(server),
                'csrf_token': token
            }

        def make_headers():
            return {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': url
            }

        def get_server_link(payload):
            sts, response = self.cm.getPage(
                post_url,
                {'header': make_headers(), 'raw_post_data': True},
                self.urlencode(payload)
            )
            if not sts or not response:
                return ''
            try:
                result = json_loads(response)
            except Exception as e:
                printDBG("JSON decode error: %s" % str(e))
                return ''
            if result.get("type") != "success":
                return ''
            return result.get("server", "")

        def normalize_server_name(link, index):
            name = self.cm.ph.getSearchGroups(link, r'https?://([^/]+)/')[0]
            if name == 'm.reviewrate.net':
                name = 'ArabSeed'
            return name or "server%d" % index

        # --- Main processing loop ---
        for server in servers:
            for quality in qualities:
                payload = make_payload(server, quality)
                link = get_server_link(payload)
                if not link:
                    continue

                server_name = normalize_server_name(link, server)
                full_label = "%s [%s]" % (server_name, quality)
                params_video = MergeDicts(cItem, {
                    'title': full_label,
                    'url': link,
                    'type': 'video',
                    'category': 'video',
                    'need_resolve': 1,
                })
                self.addVideo(params_video)

        printDBG("ArabSeed.exploreItems <<< done")

    def exploreSeriesItems(self, cItem):
        printDBG('ArabSeed.exploreSeriesItems')
        url = cItem['url']
        sts, data = self.getPage(url)

        if not sts:
            return

        # Extract the block that contains episodes
        episodes_block = self.cm.ph.getDataBeetwenMarkers(data,
            '<ul class="episodes__list', '</ul>', False)[1]

        printDBG('Episodes block:')
        printDBG(episodes_block)

        episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, '<li', LI_CLOSE)
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
                title = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({
                'title': title,
                'url': episode_url,
                'icon': cItem.get('icon', ''),
                'desc': cItem.get('desc', ''),
                'category': 'video',
            })

            printDBG('Adding episode: %s' % str(params))

            # 🔹 Start of server/quality extraction (same as exploreItems)
            sts2, data2 = self.cm.getPage(episode_url)
            if not sts2:
                continue

            def _extract_one(patterns):
                for p in patterns:
                    try:
                        v = self.cm.ph.getSearchGroups(data2, p)[0]
                        if v:
                            return v.strip()
                    except Exception:
                        pass
                return ''

            token = _extract_one([r"csrf__token['\"]:\s*['\"]([^'\"]+)", r"csrf_token['\"]:\s*['\"]([^'\"]+)", r"name=['\"]csrf-token['\"]\s+content=['\"]([^'\"]+)"])
            post_id = _extract_one([r"psot_id['\"]:\s*'([^']+)'", r"post_id['\"]:\s*['\"]([^'\"]+)", r"post_id\s*:\s*'([^']+)'"])

            if not token or not post_id:
                printDBG('[ArabSeed] Missing required POST params (csrf_token or post_id/psot_id) for episode')
                continue

            servers = [0, 1, 2, 3, 4]
            qualities = [480, 720, 1080]
            post_url = "https://a.asd.homes/get__watch__server/"

            for server in servers:
                for quality in qualities:
                    payload = {
                        'post_id': post_id,
                        'quality': str(quality),
                        'server': str(server),
                        'csrf_token': token
                    }
                    headers = {
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': episode_url
                    }

                    sts3, response = self.cm.getPage(post_url, {'header': headers, 'raw_post_data': True}, self.urlencode(payload))
                    if not sts3 or not response:
                        continue

                    try:
                        result = json_loads(response)
                    except Exception as e:
                        printDBG("JSON decode error (series): %s" % str(e))
                        continue

                    if result.get("type") != "success":
                        continue

                    link = result.get("server", "")
                    if not link:
                        continue

                    server_name = self.cm.ph.getSearchGroups(link, r'https?://([^/]+)/')[0]
                    if server_name == 'm.reviewrate.net':
                        server_name = 'ArabSeed'
                    if not server_name:
                        server_name = "server%d" % server

                    full_label = "%s [%s]" % (server_name, quality)
                    params_video = MergeDicts(cItem, {
                        'title': '%s - %s' % (title, full_label),
                        'url': link,
                        'type': 'video',
                        'category': 'video',
                        'need_resolve': 1,
                    })
                    self.addVideo(params_video)

        printDBG("ArabSeed.exploreSeriesItems <<< done")

    def safe_b64decode(self, data):
        """Base64 decode with automatic padding fix."""
        data += '=' * (-len(data) % 4)
        return base64.b64decode(data).decode('utf-8')

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabSeed.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search?q=') + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG('ArabSeed.getFavouriteData')
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('ArabSeed.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('ArabSeed.setInitListFromFavouriteItem')
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArabSeed.handleService start')

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
        CHostBase.__init__(self, ArabSeed(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True

        return False
