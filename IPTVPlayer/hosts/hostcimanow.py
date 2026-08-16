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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import time
import re
import base64
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://cimanow.cc/'  # main url of host


class CimaNow(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cimanow', 'cookie': 'cimanow.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + 'search/'
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/cimanow.png"
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
                printDBG('CimaNow.getPage retry %d failed: %s' % (attempt + 1, str(e)))

            # Cloudflare timing window delay
            time.sleep(1.5)

        printDBG(f"[CimaNow] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################
    def listMainMenu(self, cItem):
        printDBG('CimaNow.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'movies_categories', 'title': _('Movies')},
            {'category': 'series_categories', 'title': _('Series')},
            {'category': 'other_categories', 'title': _('Others')}
        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_movies', 'title': _('Arabic Movies'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a%d8%a9/')},
            {'category': 'list_movies', 'title': _('English Movies'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9/')},
            {'category': 'list_movies', 'title': _('Turkish Movies'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_movies', 'title': _('Indian Movies'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')},
            {'category': 'list_movies', 'title': _('Anime Movies'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%8a%d9%85%d9%8a%d8%b4%d9%86/')},
            {'category': 'list_movies', 'title': _('Short Movies'), 'url': self.getFullUrl('/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%82%d8%b5%d9%8a%d8%b1%d8%a9/')},
            {'category': 'list_movies', 'title': _('Documentary Movies'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%88%d8%ab%d8%a7%d8%a6%d9%82%d9%8a%d8%a9/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': _('Arabic Series'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': _('English Series'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': _('Turkish Series'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/')},
            {'category': 'list_series', 'title': _('Anime Series'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%8a%d9%85%d9%8a%d8%b4%d9%86/')},
            {'category': 'list_series', 'title': _('Ramadan 2025'), 'url': self.getFullUrl('/category/%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2025/')}
        ]

        self.OTHER_CAT_TAB = [
            {'category': 'list_movies', 'title': _('Masrahyat'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d8%b1%d8%ad%d9%8a%d8%a7%d8%aa/')},
            {'category': 'list_series', 'title': _('TV Shows'), 'url': self.getFullUrl('/category/%d8%a7%d9%84%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%a7%d9%84%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/')}
        ]

    def listMoviesCategories(self, cItem):
        printDBG('CimaNow.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG('CimaNow.listMoviesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listOtherCategories(self, cItem):
        printDBG('CimaNow.listOtherCategories')
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    ###################################################
    # LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
    ###################################################

    def listMoviesUnits(self, cItem):
        printDBG('CimaNow.listMoviesUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])

        main_encoded_block = self.cm.ph.getDataBeetwenMarkers(data, 'var hide_my_HTML_ =', 'var', False)[1]
        if not main_encoded_block:
            printDBG('listMoviesUnits: No main_encoded_block found')
            return

        # --- Clean concatenation and quotes ---
        main_encoded_block = main_encoded_block.replace("'+", "").replace("+ '", "").replace("'", "").replace('"', "").strip()

        # --- Decode JS-obfuscated HTML ---
        import urllib

        def decode_obfuscated_block(block):
            tokens = re.findall(r"[A-Za-z0-9+/=]{4,}", block)
            nums = []
            for t in tokens:
                padded = t + ("=" * ((4 - len(t) % 4) % 4))
                try:
                    decoded = base64.b64decode(padded).decode('latin1')
                except Exception:
                    continue
                digits = re.sub(r"\D", "", decoded)
                if not digits:
                    continue
                val = int(digits) - 87653
                if 0 <= val <= 0x10FFFF:
                    nums.append(val)
            try:
                b = bytes(nums)
                return b.decode('utf-8', errors='replace')
            except Exception:
                s = "".join(chr(n) for n in nums)
                pct = "".join("%%%02X" % (ord(ch) & 0xFF) for ch in s)
                return urllib.unquote(pct)

        main_block = decode_obfuscated_block(main_encoded_block)
        all_block = self.cm.ph.getDataBeetwenMarkers(main_block, '<section aria-label="posts">', '<footer>', False)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(all_block, '<article aria-label="post">', '</article>')
        printDBG('listMoviesUnits: Found %d items' % len(items))

        for item in items:
            ###################################################
            # URL
            ###################################################
            url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            printDBG('url.listMoviesUnits >>> %s' % url)

            ###################################################
            # ICON
            ###################################################
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]

            if icon:
                # Clean unwanted query
                icon = icon.replace("?quality=10", "").strip()

                # Safely encode non-ASCII URLs (Arabic, etc.)
                try:
                    icon = urllib_quote_plus(icon, safe=':/?&=#%')
                except Exception as e:
                    printDBG('icon.listMoviesUnits encode error: %s' % e)

                # Make it absolute
                icon = self.getFullUrl(icon)

            printDBG('icon.listMoviesUnits >>> %s' % icon)
            ###################################################
            # QUALITY (join multiple ribbons)
            ###################################################
            quality_list = re.findall(r'<li[^>]+aria-label="ribbon"[^>]*>([^<]+)</li>', item)
            quality = " ".join(self.cleanHtmlStr(q) for q in quality_list).strip()
            printDBG('quality.listMoviesUnits >>> %s' % quality)

            ###################################################
            # YEAR
            ###################################################
            year = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'<li[^>]+aria-label="year"[^>]*>([^<]+)</li>')[0]
            )
            printDBG('year.listMoviesUnits >>> %s' % year)

            ###################################################
            # TITLE
            ###################################################
            raw_title = self.cm.ph.getDataBeetwenMarkers(item, '<li aria-label="title">', '</li>', False)[1]
            title = self.cleanHtmlStr(re.sub(r'<em>.*?</em>', '', raw_title)).strip()
            printDBG('title.listMoviesUnits >>> %s' % title)

            ###################################################
            # DESCRIPTION
            ###################################################
            desc = f"{quality} | {year}"
            if not desc.strip():
                desc = title

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

            colored_quality = f"{E2ColoR(q_color)}{quality if quality else 'N/A'}{E2ColoR('white')}"

            ###################################################
            # FINAL ITEM
            ###################################################
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'desc': f"{colored_quality} | {year}",
                'category': 'explore_movies_items'
            })
            self.addDir(params)

        ###################################################
        # PAGINATION
        ###################################################
        pagination_block = self.cm.ph.getDataBeetwenMarkers(all_block, '<ul aria-label="pagination">', '</ul>', False)[1]
        printDBG('pagination_block.exploreMoviesItems >>> %s' % pagination_block)

        if pagination_block:
            # Extract all <li> entries
            li_items = self.cm.ph.getAllItemsBeetwenMarkers(pagination_block, '<li', '</li>')
            pages = []
            current_index = -1

            # Parse pagination links
            for idx, li in enumerate(li_items):
                href = self.cm.ph.getSearchGroups(li, r'href="([^"]+)"')[0]
                page_num = self.cleanHtmlStr(li)
                if not href:
                    href = ''
                pages.append({'num': page_num, 'url': href})

                # Check if it's the current (active) page
                if 'active' in li:
                    current_index = idx

            # Determine previous and next URLs
            prev_url = ''
            next_url = ''
            if current_index > 0 and pages[current_index - 1]['url']:
                prev_url = pages[current_index - 1]['url']
            if current_index >= 0 and current_index + 1 < len(pages):
                next_url = pages[current_index + 1]['url']

            # Add "previous" page
            if prev_url:
                params = dict(cItem)
                params.update({
                    'title': '<<< ' + _('Previous'),
                    'url': self.getFullUrl(prev_url),
                    'category': 'list_movies'
                })
                self.addDir(params)
                printDBG('listMoviesUnits: Found previous page %s' % prev_url)

            # Add "next" page
            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('Next') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': 'list_movies'
                })
                self.addDir(params)
                printDBG('listMoviesUnits: Found next page %s' % next_url)

    def exploreMoviesItems(self, cItem):
        printDBG('CimaNow.exploreMoviesItems >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.exploreMoviesItems >>> %s' % url)

        # 1) First request: open the main page to trigger Cloudflare JS check and save cookies
        sts, data = self.getPage(url)
        # printDBG('data.exploreMoviesItems >>> %s' % data)
        if not sts:
            printDBG('exploreMoviesItems: initial getPage failed')
            return

        # 2) Try to access the real "watching" page using the saved cookie (so CF clearance is sent)
        # Build watching URL
        if not url.endswith('/'):
            watch_url = url + '/watching/'
        else:
            # url already ends with '/', append watching/
            watch_url = url + 'watching/'
        printDBG('watch_url.exploreMoviesItems >>> %s' % watch_url)

        # Prepare params to force loading saved cookie and use CF protection helper directly
        addParams = dict(self.defaultParams)  # copy default params
        addParams['load_cookie'] = True   # load cookie that was saved by the first getPage()
        addParams['save_cookie'] = True
        addParams['cookiefile'] = self.COOKIE_FILE
        # Ensure cloudflare params exist (getPage normally sets them, but we're calling getPageCFProtection directly)
        addParams['cloudflare_params'] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent")
        }

        # small delay: many sites expect a short wait; keep it short to avoid long blocks
        try:
            import time
            time.sleep(1.5)
        except Exception:
            pass

        try:
            sts2, data2 = self.cm.getPageCFProtection(watch_url, addParams)
        except Exception as e:
            printDBG('exploreMoviesItems: getPageCFProtection exception for watching: %s' % str(e))
            sts2, data2 = False, ''

        # If watching page failed (CF not solved or watching not exists), fall back to the original page
        if not sts2 or not data2 or '/home' in data2:
            printDBG('exploreMoviesItems: watching page fetch failed or redirected; using original page data')
            page_data = data
        else:
            printDBG('exploreMoviesItems: watching page fetched successfully')
            page_data = data2
        # printDBG('page_data.exploreMoviesItems >>> %s' % page_data)
        main_encoded_block = self.cm.ph.getDataBeetwenMarkers(page_data, 'var hide_my_HTML_ =', 'var', False)[1]
        if not main_encoded_block:
            printDBG('listMoviesUnits: No main_encoded_block found')
            return

        # --- Clean concatenation and quotes ---
        main_encoded_block = main_encoded_block.replace("'+", "").replace("+ '", "").replace("'", "").replace('"', "").strip()

        # --- Decode JS-obfuscated HTML ---
        import urllib

        def decode_obfuscated_block(block):
            tokens = re.findall(r"[A-Za-z0-9+/=]{4,}", block)
            nums = []
            for t in tokens:
                padded = t + ("=" * ((4 - len(t) % 4) % 4))
                try:
                    decoded = base64.b64decode(padded).decode('latin1')
                except Exception:
                    continue
                digits = re.sub(r"\D", "", decoded)
                if not digits:
                    continue
                val = int(digits) - 87653
                if 0 <= val <= 0x10FFFF:
                    nums.append(val)
            try:
                b = bytes(nums)
                return b.decode('utf-8', errors='replace')
            except Exception:
                s = "".join(chr(n) for n in nums)
                pct = "".join("%%%02X" % (ord(ch) & 0xFF) for ch in s)
                return urllib.unquote(pct)

        page_data_block = decode_obfuscated_block(main_encoded_block)
        # printDBG('page_data_block.exploreMoviesItems >>> %s' % page_data_block)
        watch_list = self.cm.ph.getDataBeetwenMarkers(page_data_block, '<ul class="tabcontent active" id="watch">', '<li aria-label="embed">', False)[1]
        printDBG('watch_list.exploreMoviesItems >>> %s' % watch_list)

        if not watch_list:
            printDBG('No watch list found')
            return

        # Extract all <li> items
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, '<li', '</li>')
        li_items = li_items[1:]
        printDBG('Found %d servers' % len(li_items))
        # --- Prepare default params for switch requests (reuse CF clearance cookie) ---
        switchParams = dict(self.defaultParams)
        switchParams['load_cookie'] = True
        switchParams['save_cookie'] = True
        switchParams['cookiefile'] = self.COOKIE_FILE
        switchParams['cloudflare_params'] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent")
        }

        for item in li_items:
            # Try to find an inline iframe first (some pages include the embed directly)
            inline_iframe = self.cm.ph.getSearchGroups(item, r'<iframe[^>]+src="([^"]+)"')[0]
            server_name = ""
            data_index = ""
            data_id = ""
            final_url = ""

            # Clean server name: text content of the <li> without tags (if present)
            try:
                # remove any tags and keep visible text
                server_name = re.sub(r'<[^>]+>', '', item).strip()
                # if server_name contains many spaces/newlines, collapse them
                server_name = re.sub(r'\s+', ' ', server_name).strip()
                # If server_name includes the iframe markup text, remove 'iframe' text
                server_name = server_name.replace('iframe', '').strip()
            except Exception:
                server_name = 'Unknown Server'

            if inline_iframe:
                # Found an inline iframe -> use it directly
                final_url = inline_iframe
                printDBG('exploreMoviesItems: inline iframe found -> %s' % final_url)
            else:
                # Extract data-index and data-id for switch request
                data_index = self.cm.ph.getSearchGroups(item, r'data-index="([^"]+)"')[0]
                data_id = self.cm.ph.getSearchGroups(item, r'data-id="([^"]+)"')[0]

                if not data_index or not data_id:
                    printDBG('exploreMoviesItems: no data-index/data-id in li -> skip (server_name=%s)' % server_name)
                    continue

                # Build switch URL (relative to site)
                switch_path = '/wp-content/themes/Cima%%20Now%%20New/core.php?action=switch&index=%s&id=%s' % (data_index, data_id)
                switch_url = self.getFullUrl(switch_path)
                printDBG('exploreMoviesItems: switch_url -> %s (server=%s)' % (switch_url, server_name))

                # Request the switch URL (use CF helper so cookies/clearance are sent)
                try:
                    sts3, data3 = self.cm.getPageCFProtection(switch_url, switchParams)
                except Exception as e:
                    printDBG('exploreMoviesItems: exception requesting switch_url: %s' % str(e))
                    sts3, data3 = False, ''

                if not sts3 or not data3:
                    printDBG('exploreMoviesItems: switch request failed for %s' % switch_url)
                    continue

                # Response expected to include an iframe; extract src
                iframe_src = self.cm.ph.getSearchGroups(data3, r'<iframe[^>]+src="([^"]+)"')[0]
                if iframe_src:
                    final_url = iframe_src
                    printDBG('exploreMoviesItems: iframe_src from switch -> %s' % final_url)
                else:
                    # sometimes response may contain the URL directly or within JS; try common patterns
                    final_url = self.cm.ph.getSearchGroups(data3, r'href="([^"]+)"')[0] or ''
                    if final_url:
                        printDBG('exploreMoviesItems: fallback href from switch -> %s' % final_url)
                    else:
                        printDBG('exploreMoviesItems: no iframe found in switch response for %s' % switch_url)
                        continue

            # Normalize final_url and make absolute if needed
            if final_url:
                final_url = final_url.strip()
                final_url = self.getFullUrl(final_url)
                printDBG('final_url.exploreMoviesItems >>> %s' % final_url)

            # Build readable title: prefer server_name, strip numeric attributes
            title = server_name or 'Server'
            # If server_name includes data-id/index text, try to clean it
            title = re.sub(r'data-index=.*', '', title).strip()
            if not title:
                title = 'Unknown Server'

            printDBG('exploreMoviesItems: adding video -> title: %s, url: %s' % (title, final_url))

            # Add the video item
            params = dict(cItem)
            params.update({
                'title': title,
                'url': final_url,
                'category': 'video',
                'type': 'video',
            })
            self.addVideo(params)

    def listSeriesUnits(self, cItem):
        printDBG('CimaNow.listSeriesUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])

        main_encoded_block = self.cm.ph.getDataBeetwenMarkers(data, 'var hide_my_HTML_ =', 'var', False)[1]
        if not main_encoded_block:
            printDBG('listSeriesUnits: No main_encoded_block found')
            return

        # --- Clean concatenation and quotes ---
        main_encoded_block = main_encoded_block.replace("'+", "").replace("+ '", "").replace("'", "").replace('"', "").strip()

        # --- Decode JS-obfuscated HTML ---
        import urllib

        def decode_obfuscated_block(block):
            tokens = re.findall(r"[A-Za-z0-9+/=]{4,}", block)
            nums = []
            for t in tokens:
                padded = t + ("=" * ((4 - len(t) % 4) % 4))
                try:
                    decoded = base64.b64decode(padded).decode('latin1')
                except Exception:
                    continue
                digits = re.sub(r"\D", "", decoded)
                if not digits:
                    continue
                val = int(digits) - 87653
                if 0 <= val <= 0x10FFFF:
                    nums.append(val)
            try:
                b = bytes(nums)
                return b.decode('utf-8', errors='replace')
            except Exception:
                s = "".join(chr(n) for n in nums)
                pct = "".join("%%%02X" % (ord(ch) & 0xFF) for ch in s)
                return urllib.unquote(pct)

        main_block = decode_obfuscated_block(main_encoded_block)
        all_block = self.cm.ph.getDataBeetwenMarkers(main_block, '<section aria-label="posts">', '<footer>', False)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(all_block, '<article aria-label="post">', '</article>')
        printDBG('listSeriesUnits: Found %d items' % len(items))

        for item in items:
            ###################################################
            # URL
            ###################################################
            url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            printDBG('url.listSeriesUnits >>> %s' % url)

            ###################################################
            # ICON
            ###################################################
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]

            if icon:
                # Clean unwanted query
                icon = icon.replace("?quality=10", "").strip()

                # Safely encode non-ASCII URLs (Arabic, etc.)
                try:
                    icon = urllib_quote_plus(icon, safe=':/?&=#%')
                except Exception as e:
                    printDBG('icon.listSeriesUnits encode error: %s' % e)

                # Make it absolute
                icon = self.getFullUrl(icon)

            printDBG('icon.listSeriesUnits >>> %s' % icon)
            ###################################################
            # QUALITY (join multiple ribbons)
            ###################################################
            quality_list = re.findall(r'<li[^>]+aria-label="ribbon"[^>]*>([^<]+)</li>', item)
            quality = " ".join(self.cleanHtmlStr(q) for q in quality_list).strip()
            printDBG('quality.listSeriesUnits >>> %s' % quality)

            ###################################################
            # YEAR
            ###################################################
            year = self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(item, r'<li[^>]+aria-label="year"[^>]*>([^<]+)</li>')[0]
            )
            printDBG('year.listSeriesUnits >>> %s' % year)

            ###################################################
            # TITLE
            ###################################################
            raw_title = self.cm.ph.getDataBeetwenMarkers(item, '<li aria-label="title">', '</li>', False)[1]
            title = self.cleanHtmlStr(re.sub(r'<em>.*?</em>', '', raw_title)).strip()
            printDBG('title.listSeriesUnits >>> %s' % title)

            ###################################################
            # DESCRIPTION
            ###################################################
            desc = f"{quality} | {year}"
            if not desc.strip():
                desc = title

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

            colored_quality = f"{E2ColoR(q_color)}{quality if quality else 'N/A'}{E2ColoR('white')}"

            ###################################################
            # FINAL ITEM
            ###################################################
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'desc': f"{colored_quality} | {year}",
                'category': 'explore_series_items'
            })
            self.addDir(params)

        ###################################################
        # PAGINATION
        ###################################################
        pagination_block = self.cm.ph.getDataBeetwenMarkers(all_block, '<ul aria-label="pagination">', '</ul>', False)[1]
        printDBG('pagination_block.exploreMoviesItems >>> %s' % pagination_block)

        if pagination_block:
            # Extract all <li> entries
            li_items = self.cm.ph.getAllItemsBeetwenMarkers(pagination_block, '<li', '</li>')
            pages = []
            current_index = -1

            # Parse pagination links
            for idx, li in enumerate(li_items):
                href = self.cm.ph.getSearchGroups(li, r'href="([^"]+)"')[0]
                page_num = self.cleanHtmlStr(li)
                if not href:
                    href = ''
                pages.append({'num': page_num, 'url': href})

                # Check if it's the current (active) page
                if 'active' in li:
                    current_index = idx

            # Determine previous and next URLs
            prev_url = ''
            next_url = ''
            if current_index > 0 and pages[current_index - 1]['url']:
                prev_url = pages[current_index - 1]['url']
            if current_index >= 0 and current_index + 1 < len(pages):
                next_url = pages[current_index + 1]['url']

            # Add "previous" page
            if prev_url:
                params = dict(cItem)
                params.update({
                    'title': '<<< ' + _('Previous'),
                    'url': self.getFullUrl(prev_url),
                    'category': 'list_series'
                })
                self.addDir(params)
                printDBG('listSeriesUnits: Found previous page %s' % prev_url)

            # Add "next" page
            if next_url:
                params = dict(cItem)
                params.update({
                    'title': _('Next') + ' >>>',
                    'url': self.getFullUrl(next_url),
                    'category': 'list_series'
                })
                self.addDir(params)
                printDBG('listSeriesUnits: Found next page %s' % next_url)

    def exploreSeriesItems(self, cItem):
        printDBG('CimaNow.exploreSeriesItems >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.exploreSeriesItems >>> %s' % url)

        # 1) First request: open the main page to trigger Cloudflare JS check and save cookies
        sts, data = self.getPage(url)
        # printDBG('data.exploreSeriesItems >>> %s' % data)
        if not sts:
            printDBG('exploreSeriesItems: initial getPage failed')
            return

        # Prepare params to force loading saved cookie and use CF protection helper directly
        addParams = dict(self.defaultParams)  # copy default params
        addParams['load_cookie'] = True   # load cookie that was saved by the first getPage()
        addParams['save_cookie'] = True
        addParams['cookiefile'] = self.COOKIE_FILE
        # Ensure cloudflare params exist (getPage normally sets them, but we're calling getPageCFProtection directly)
        addParams['cloudflare_params'] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent")
        }

        # small delay: many sites expect a short wait; keep it short to avoid long blocks
        try:
            import time
            time.sleep(1.5)
        except Exception:
            pass

        try:
            sts2, data2 = self.cm.getPageCFProtection(url, addParams)
        except Exception as e:
            printDBG('exploreSeriesItems: getPageCFProtection exception for watching: %s' % str(e))
            sts2, data2 = False, ''

        # If watching page failed (CF not solved or watching not exists), fall back to the original page
        if not sts2 or not data2 or '/home' in data2:
            printDBG('exploreSeriesItems: watching page fetch failed or redirected; using original page data')
            page_data = data
        else:
            printDBG('exploreSeriesItems: watching page fetched successfully')
            page_data = data2
        # printDBG('page_data.exploreSeriesItems >>> %s' % page_data)
        main_encoded_block = self.cm.ph.getDataBeetwenMarkers(page_data, 'var hide_my_HTML_ =', 'var', False)[1]
        if not main_encoded_block:
            printDBG('listMoviesUnits: No main_encoded_block found')
            return

        # --- Clean concatenation and quotes ---
        main_encoded_block = main_encoded_block.replace("'+", "").replace("+ '", "").replace("'", "").replace('"', "").strip()

        # --- Decode JS-obfuscated HTML ---
        import urllib

        def decode_obfuscated_block(block):
            tokens = re.findall(r"[A-Za-z0-9+/=]{4,}", block)
            nums = []
            for t in tokens:
                padded = t + ("=" * ((4 - len(t) % 4) % 4))
                try:
                    decoded = base64.b64decode(padded).decode('latin1')
                except Exception:
                    continue
                digits = re.sub(r"\D", "", decoded)
                if not digits:
                    continue
                val = int(digits) - 87653
                if 0 <= val <= 0x10FFFF:
                    nums.append(val)
            try:
                b = bytes(nums)
                return b.decode('utf-8', errors='replace')
            except Exception:
                s = "".join(chr(n) for n in nums)
                pct = "".join("%%%02X" % (ord(ch) & 0xFF) for ch in s)
                return urllib.unquote(pct)

        page_data_block = decode_obfuscated_block(main_encoded_block)
        # printDBG('page_data_block.exploreSeriesItems >>> %s' % page_data_block)
        season_list = self.cm.ph.getDataBeetwenMarkers(page_data_block, '<section aria-label="seasons">', '</section>', False)[1]
        printDBG('season_list.exploreSeriesItems >>> %s' % season_list)

        if not season_list:
            printDBG('No season list found')
            return

        # Extract all <li> items
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(season_list, '<li', '</li>')
        printDBG('Found %d seasons' % len(li_items))
        # --- Prepare default params for switch requests (reuse CF clearance cookie) ---
        switchParams = dict(self.defaultParams)
        switchParams['load_cookie'] = True
        switchParams['save_cookie'] = True
        switchParams['cookiefile'] = self.COOKIE_FILE
        switchParams['cloudflare_params'] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent")
        }

        seasons = []

        for item in li_items:
            season_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not season_url:
                continue

            # --- Extract season title (before <em>) ---
            season_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'>([^<]+)<em>')[0])
            if not season_title:
                season_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'>([^<]+)</a>')[0])

            # --- Extract episode count text ---
            episodes_text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<em>\(([^)]+)\)</em>')[0])

            # --- Defaults ---
            if not season_title:
                season_title = 'موسم'
            if not episodes_text:
                episodes_text = ''

            # --- Extract numeric season number for sorting ---
            season_num = re.search(r'(\d+)', season_title)
            try:
                season_num = int(season_num.group(1)) if season_num else 0
            except:
                season_num = 0

            # --- Combine full title ---
            full_title = '%s - %s' % (season_title.strip(), episodes_text.strip()) if episodes_text else season_title.strip()

            printDBG('Season: %s | URL: %s' % (full_title, season_url))

            seasons.append({
                'num': season_num,
                'title': full_title,
                'url': season_url,
            })

        # --- Sort seasons by numeric order (ascending) ---
        seasons.sort(key=lambda s: s['num'])

        # --- Add to directory ---
        for s in seasons:
            params = dict(cItem)
            params.update({
                'title': s['title'],
                'url': s['url'],
                'category': 'list_series_episodes',  # flow to listSeriesEpisodes()
            })
            self.addDir(params)

    def listSeriesEpisodes(self, cItem, data=None):
        printDBG('CimaNow.listSeriesEpisodes >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.listSeriesEpisodes >>> %s' % url)

        # 1) First request: open the main page to trigger Cloudflare JS check and save cookies
        sts, data1 = self.getPage(url)
        # printDBG('data.listSeriesEpisodes >>> %s' % data1)
        if not sts:
            printDBG('listSeriesEpisodes: initial getPage failed')
            return

        # Prepare params to force loading saved cookie and use CF protection helper directly
        addParams = dict(self.defaultParams)  # copy default params
        addParams['load_cookie'] = True   # load cookie that was saved by the first getPage()
        addParams['save_cookie'] = True
        addParams['cookiefile'] = self.COOKIE_FILE
        # Ensure cloudflare params exist (getPage normally sets them, but we're calling getPageCFProtection directly)
        addParams['cloudflare_params'] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent")
        }

        # small delay: many sites expect a short wait; keep it short to avoid long blocks
        try:
            import time
            time.sleep(1.5)
        except Exception:
            pass

        try:
            sts2, data2 = self.cm.getPageCFProtection(url, addParams)
        except Exception as e:
            printDBG('listSeriesEpisodes: getPageCFProtection exception for watching: %s' % str(e))
            sts2, data2 = False, ''

        # If watching page failed (CF not solved or watching not exists), fall back to the original page
        if not sts2 or not data2 or '/home' in data2:
            printDBG('listSeriesEpisodes: watching page fetch failed or redirected; using original page data')
            page_data = data1
        else:
            printDBG('listSeriesEpisodes: watching page fetched successfully')
            page_data = data2
        # printDBG('page_data.listSeriesEpisodes >>> %s' % page_data)
        main_encoded_block = self.cm.ph.getDataBeetwenMarkers(page_data, 'var hide_my_HTML_ =', 'var', False)[1]
        if not main_encoded_block:
            printDBG('listSeriesEpisodes: No main_encoded_block found')
            return

        # --- Clean concatenation and quotes ---
        main_encoded_block = main_encoded_block.replace("'+", "").replace("+ '", "").replace("'", "").replace('"', "").strip()

        # --- Decode JS-obfuscated HTML ---
        import urllib

        def decode_obfuscated_block(block):
            tokens = re.findall(r"[A-Za-z0-9+/=]{4,}", block)
            nums = []
            for t in tokens:
                padded = t + ("=" * ((4 - len(t) % 4) % 4))
                try:
                    decoded = base64.b64decode(padded).decode('latin1')
                except Exception:
                    continue
                digits = re.sub(r"\D", "", decoded)
                if not digits:
                    continue
                val = int(digits) - 87653
                if 0 <= val <= 0x10FFFF:
                    nums.append(val)
            try:
                b = bytes(nums)
                return b.decode('utf-8', errors='replace')
            except Exception:
                s = "".join(chr(n) for n in nums)
                pct = "".join("%%%02X" % (ord(ch) & 0xFF) for ch in s)
                return urllib.unquote(pct)

        page_data_block = decode_obfuscated_block(main_encoded_block)

        # --- Extract episodes list ---
        episodes_part = self.cm.ph.getDataBeetwenMarkers(page_data_block, '<ul class="tabcontent active" id="eps">', '</ul>', False)[1]
        if not episodes_part:
            printDBG('No episode list found in season')
            return

        episode_items = self.cm.ph.getAllItemsBeetwenMarkers(episodes_part, '<li', '</li>')
        episode_items.reverse()
        printDBG('episode_items.listSeriesEpisodes >>> %s' % episode_items)
        printDBG('Found %d episodes' % len(episode_items))

        for item in episode_items:
            # --- Episode URL ---
            ep_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]

            # --- Episode Title (from aria-label, title, or <b>/<em> content) ---
            ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'aria-label="([^"]+)"')[0])
            if not ep_title:
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not ep_title:
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<b>([^<]+)</b>')[0])
            if not ep_title:
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<em>([^<]+)</em>')[0])

            # --- Episode Image (prefer the second <img> if multiple exist) ---
            imgs = re.findall(r'<img[^>]+src="([^"]+)"', item)
            ep_icon = ''
            if imgs:
                ep_icon = imgs[-1]  # usually the episode thumbnail (not logo)
                if ep_icon:
                # Safely encode non-ASCII URLs (Arabic, etc.)
                    try:
                        ep_icon = urllib_quote_plus(ep_icon, safe=':/?&=#%')
                    except Exception as e:
                        printDBG('ep_icon.listSeriesUnits encode error: %s' % e)

                # Make it absolute
                ep_icon = self.getFullUrl(ep_icon)

            # --- Episode Number (from <em> or extracted digits) ---
            ep_number = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<em>([^<]+)</em>')[0])
            if not ep_number:
                ep_number = self.cm.ph.getSearchGroups(ep_title, r'(\d+)')[0]

            # --- Description (optional — from aria-label, alt, or combined text) ---
            ep_desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not ep_desc:
                ep_desc = ep_title

            # --- Build final episode parameters ---
            params = dict(cItem)
            params.update({
                'title': ep_title if ep_title else 'Episode %s' % ep_number,
                'url': ep_url,
                'icon': ep_icon,
                'desc': ep_desc,
                'category': 'explore_movies_items',  # flow back to exploreItems()
            })

            self.addDir(params)

        printDBG('Finished listing episodes for: %s' % cItem.get('title', 'Unknown'))

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('CimaNow.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'CimaNow - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("CimaNow.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaNow.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listMoviesUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('CimaNow.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'explore_movies_items':
            self.exploreMoviesItems(self.currItem)
        elif category == 'explore_series_items':
            self.exploreSeriesItems(self.currItem)
        elif category == 'movies_categories':
            self.listMoviesCategories(self.currItem)
        elif category == 'series_categories':
            self.listSeriesCategories(self.currItem)
        elif category == 'other_categories':
            self.listOtherCategories(self.currItem)
        elif category == 'list_movies':
            self.listMoviesUnits(self.currItem)
        elif category == 'list_series':
            self.listSeriesUnits(self.currItem)
        elif category == 'list_series_episodes':
            self.listSeriesEpisodes(self.currItem)

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
        CHostBase.__init__(self, CimaNow(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
