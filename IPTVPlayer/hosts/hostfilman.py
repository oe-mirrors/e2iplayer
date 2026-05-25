# -*- coding: utf-8 -*-
# Last Modified: 25.05.2026 - damagic

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox

###################################################
# FOREIGN import
###################################################
import re
import base64
import time
import os

try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry

###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filman_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filman_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filman_cookie_phpsessid = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Filman login:", config.plugins.iptvplayer.filman_login))
    optionList.append(getConfigListEntry("Filman hasło:", config.plugins.iptvplayer.filman_password))
    optionList.append(getConfigListEntry("Filman cookie (PHPSESSID):", config.plugins.iptvplayer.filman_cookie_phpsessid))
    return optionList


###################################################


def gettytul():
    return "https://filman.cc/"


class Filman(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filman.online", "cookie": "filman.cookie"})
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.MAIN_URL = "https://filman.cc/"
        self.DEFAULT_ICON_URL = "https://filman.cc/public/dist/images/logo.png"
        self.HTTP_HEADER = {"User-Agent": self.USER_AGENT, "DNT": "1", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "Accept-Language": "pl,en-US;q=0.7,en;q=0.3", "Referer": self.getMainUrl(), "Origin": self.getMainUrl(), "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1"}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json, text/javascript, */*; q=0.01"})
        self.cacheMovieFilters = {"cats": [], "sort": [], "years": [], "az": []}
        self.cacheLinks = {}
        self.cacheVersions = {}
        self.pendingLinks = {}
        self.defaultParams = {"header": self.HTTP_HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ""
        self.password = ""
        self._lastTokenRequest = 0
        self._tokenRequestCount = 0
        self.cookieDeleted = False

    def addDir(self, params):
        params['type'] = 'category'
        self.currList.append(params)

    def addVideoAsFolder(self, params):
        params['type'] = 'category'
        params['image_type'] = 'VIDEO'
        self.currList.append(params)

    def _deleteCookie(self):
        try:
            if os.path.exists(self.COOKIE_FILE):
                os.remove(self.COOKIE_FILE)
                self.cookieDeleted = True
                printDBG("Filman cookie deleted successfully from: %s" % self.COOKIE_FILE)
                return True
            else:
                printDBG("Filman cookie file does not exist: %s" % self.COOKIE_FILE)
        except Exception as e:
            printDBG("Failed to delete cookie: %s" % str(e))
        return False

    def _overwriteCookie(self, sessid):
        try:
            with open(self.COOKIE_FILE, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("filman.cc\tFALSE\t/\tFALSE\t\tPHPSESSID\t" + sessid + "\n")
            self.cookieDeleted = False
            printDBG("Filman cookie overwritten with PHPSESSID")
            return True
        except Exception as e:
            printDBG("Failed to write cookie: %s" % str(e))
            return False

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Filman.listMainMenu")
        MAIN_CAT_TAB = [
            {"category": "list_items", "title": "Filmy Premiery", "url": self.getFullUrl("/filmy/sort:premiere/")},
            {"category": "list_items", "title": "Filmy Nowe Linki", "url": self.getFullUrl("/filmy/")},
            {"category": "list_items", "title": "Filmy Oceny na Filmweb", "url": self.getFullUrl("/filmy/sort:filmweb/")},
            {"category": "list_items", "title": "Seriale Nowe Odcinki", "url": self.getFullUrl("/seriale/")},
            {"category": "list_sort", "title": _("Series"), "url": self.getFullUrl("/seriale/")},
            {"category": "list_items", "title": _("Children"), "url": self.getFullUrl("/dla-dzieci-pl/")},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {"cats": [], "sort": [], "years": [], "az": []}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-sort"', "</ul>", False)[1]
        dat = re.compile('<li[^>]+?data-sort="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters["sort"].append({"title": self.cleanHtmlStr(item[1]), "sort": item[0]})
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-category"', "</ul>", False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters["cats"].append({"title": self.cleanHtmlStr(item[1]), "url": cItem["url"] + "category:%s/" % item[0]})

    def listMovieFilters(self, cItem, category):
        filter = cItem["category"].split("_")[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = self.cacheMovieFilters[filter]
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        for item in tab:
            params = dict(cItem)
            if category is not None:
                params["category"] = category
            params.update(item)
            self.addDir(params)

    def _parseItemInfo(self, item):
        info = {"title": "", "icon": "", "year": "", "quality": "", "rating": "", "desc": ""}
        link_match = re.search(r'<a\s+href="([^"]+)"', item)
        if link_match:
            url = link_match.group(1)
            if url.startswith('#') or url.startswith('javascript'):
                link_match = None
        if link_match:
            info["url"] = self.getFullUrl(link_match.group(1))
        title_match = re.search(r'data-title="([^"]*)"', item)
        if title_match:
            info["title"] = title_match.group(1).replace("&quot;", '"').replace("&amp;", "&")
        if not info["title"]:
            title_match = re.search(r'<h1\s+class="film_title">(.*?)</h1>', item, re.DOTALL)
            if title_match:
                info["title"] = self.cleanHtmlStr(title_match.group(1))
        if not info["title"]:
            title_match = re.search(r'<div\s+class="film_title">(.*?)</div>', item, re.DOTALL)
            if title_match:
                info["title"] = self.cleanHtmlStr(title_match.group(1))
        if not info["title"]:
            a_match = re.search(r'<a\s+[^>]*?title="([^"]+)"[^>]*?>', item)
            if a_match:
                info["title"] = a_match.group(1).replace("&quot;", '"').replace("&amp;", "&")
        if not info["title"]:
            alt_match = re.search(r'<img\s+[^>]*?alt="([^"]+)"', item)
            if alt_match:
                info["title"] = alt_match.group(1)
        img_match = re.search(r'<img\s+src="([^"]+)"', item)
        if img_match:
            info["icon"] = self.getFullIconUrl(img_match.group(1))
        year_match = re.search(r'<div\s+class="film_year">(.*?)</div>', item, re.DOTALL)
        if year_match:
            info["year"] = self.cleanHtmlStr(year_match.group(1))
        qual_match = re.search(r'<div\s+class="quality-version[^"]*">(.*?)</div>', item, re.DOTALL)
        if qual_match:
            info["quality"] = self.cleanHtmlStr(qual_match.group(1))
        rate_match = re.search(r'<div\s+class="rate">(.*?)</div>', item, re.DOTALL)
        if rate_match:
            info["rating"] = self.cleanHtmlStr(rate_match.group(1))
        desc_match = re.search(r'data-text="([^"]*)"', item)
        if desc_match:
            info["desc"] = desc_match.group(1).replace("&quot;", '"').replace("&amp;", "&")
        return info

    def _cleanTitleForFilename(self, title):
        if not title:
            return "Video"
        title = title.split('/')[0].strip()
        title = title.replace(':', '')
        title = re.sub(r'\s+', ' ', title).strip()
        if not title:
            return "Video"
        return title

    def listItems(self, cItem):
        printDBG("Filman.listItems %s" % cItem)
        page = cItem.get("page", 1)
        url = cItem["url"]
        sort = cItem.get("sort", "")
        if sort and sort not in url:
            url = url + sort
        if page > 1:
            sep = "&" if "?" in url else "?"
            url = "%s%spage=%d" % (url, sep, page)
        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            if hasattr(data, 'meta') and data.meta.get('status_code') == 404:
                printDBG("Filman.listItems got 404 for URL: %s" % url)
                return
        except:
            pass
        self.setMainUrl(data.meta["url"])
        is_search = "search?phrase=" in cItem.get("url", "")
        item_list_match = re.search(r'<div[^>]*id="item-list"[^>]*>(.*?)(?:<div class="row fade-in-section">|<footer|$)', data, re.DOTALL)
        if not item_list_match:
            item_list_match = re.search(r'<div[^>]*id="search-results"[^>]*>(.*?)(?:<div class="row fade-in-section">|<footer|$)', data, re.DOTALL)
        if not item_list_match:
            printDBG("Filman.listItems could not find item-list container")
            return
        main_content = item_list_match.group(1)
        raw_items = []
        if 'movie-item' in main_content:
            parts = main_content.split('<div class="col-xs-6 col-sm-2 movie-item">')
            if len(parts) > 1:
                raw_items = ['<div class="col-xs-6 col-sm-2 movie-item">' + p for p in parts[1:]]
        else:
            parts = main_content.split('<div class="col-xs-6 col-sm-3 col-lg-2">')
            if len(parts) > 1:
                raw_items = ['<div class="col-xs-6 col-sm-3 col-lg-2">' + p for p in parts[1:]]
        printDBG("Filman.listItems found %d items" % len(raw_items))
        for item in raw_items:
            info = self._parseItemInfo(item)
            if "url" not in info:
                continue
            film_url = info["url"]
            title = info["title"]
            icon = info.get("icon", self.DEFAULT_ICON_URL)
            desc_parts = []
            if info["year"]:
                desc_parts.append(_("Year: ") + info["year"])
            if info["rating"]:
                desc_parts.append(_("Rating: ") + info["rating"])
            if info["quality"]:
                desc_parts.append(_("Quality:") + " " + info["quality"])
            if info["desc"]:
                desc_parts.append(info["desc"])
            full_desc = "[/br]".join(desc_parts)
            is_series = '/s/' in film_url
            is_episode = '/e/' in film_url
            if is_series:
                params = {"good_for_fav": True, "category": "list_series", "url": film_url, "title": title, "desc": full_desc, "icon": icon}
                self.addDir(params)
            else:
                params = {"good_for_fav": True, "category": "list_versions", "url": film_url, "title": title, "desc": full_desc, "icon": icon}
                self.addVideoAsFolder(params)
        if not is_search:
            next_page_match = re.search(r'''<li\s+class=['"]next['"]\s*>\s*<a\s+href=['"]\?page=(\d+)['"][^>]*>Nast''', data)
            if not next_page_match:
                next_page_match = re.search(r'''<li\s+class=['"]next['"]\s*>\s*<a\s+href=['"]\?page=(\d+)['"]''', data)
            if next_page_match:
                next_page = int(next_page_match.group(1))
                printDBG("Filman.listItems adding next page: %d" % next_page)
                params = dict(cItem)
                params.update({"title": _("Next page"), "page": next_page, "icon": self.DEFAULT_ICON_URL})
                self.addDir(params)

    def listSeries(self, cItem):
        printDBG("Filman.listSeries %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        try:
            if hasattr(data, 'meta') and data.meta.get('status_code') == 404:
                printDBG("Filman.listSeries got 404 for URL: %s" % cItem["url"])
                return
        except:
            pass
        self.setMainUrl(data.meta["url"])
        ep_data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "episode-list"), ("<hr", ">"))[1]
        if not ep_data:
            ep_data = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "episode-list"), ("<hr", ">"))[1]
        if not ep_data:
            ep_data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "episodes"), ("</ul", ">"))[1]
        if not ep_data:
            ep_data = self.cm.ph.getDataBeetwenNodes(data, ("<div", "id", "item-content"), ("<hr", ">"))[1]
        if ep_data:
            tmp = self.cm.ph.getAllItemsBeetwenNodes(ep_data, ("<li", ">"), ("</li", ">"))
            if not tmp:
                tmp = re.findall(r'<li[^>]*>.*?<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>.*?</li>', ep_data, re.DOTALL)
                for url, title in tmp:
                    url = self.getFullUrl(url)
                    if url == "":
                        continue
                    title = self.cleanHtmlStr(title)
                    params = {"good_for_fav": True, "category": "list_versions", "url": url, "title": title, "icon": cItem["icon"]}
                    self.addVideoAsFolder(params)
            else:
                for item in tmp:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^"^']+?)['"]""")[0])
                    if url == "":
                        continue
                    title = self.cleanHtmlStr(item)
                    params = {"good_for_fav": True, "category": "list_versions", "url": url, "title": title, "icon": cItem["icon"]}
                    self.addVideoAsFolder(params)

    def listVersions(self, cItem):
        printDBG("Filman.listVersions %s" % cItem)
        cacheKey = cItem["url"]
        movie_title = cItem.get("title", "")
        if cacheKey in self.cacheVersions:
            versions = self.cacheVersions[cacheKey]
        else:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            if not movie_title:
                title_match = re.search(r'<h1[^>]*?itemprop="name"[^>]*?>(.*?)</h1>', data, re.DOTALL)
                if title_match:
                    movie_title = self.cleanHtmlStr(title_match.group(1))
                if not movie_title:
                    title_match = re.search(r'<h1\s+class="film_title">(.*?)</h1>', data, re.DOTALL)
                    if title_match:
                        movie_title = self.cleanHtmlStr(title_match.group(1))
            links_section = self.cm.ph.getDataBeetwenNodes(data, ("<table", ">", "links"), ("</table", ">"))[1]
            versions = []
            if links_section:
                rows = self.cm.ph.getAllItemsBeetwenNodes(links_section, ("<tr", ">"), ("</tr", ">"))
                for row in rows:
                    if "<th" in row:
                        continue
                    tds = self.cm.ph.getAllItemsBeetwenNodes(row, ("<td", ">"), ("</td", ">"))
                    if len(tds) < 3:
                        continue
                    link_id = self.cm.ph.getSearchGroups(row, r'''data-link-id=['"]([^"^']+?)['"]''')[0]
                    if not link_id:
                        continue
                    server_td = tds[0]
                    img_alt = self.cm.ph.getSearchGroups(server_td, r'<img[^>]+alt=["\']([^"\']+)["\']')[0]
                    if img_alt:
                        host_name = img_alt.strip()
                    else:
                        host_name = self.cleanHtmlStr(server_td).strip()
                    if not host_name:
                        host_name = self.cleanHtmlStr(server_td).strip()
                    version = self.cleanHtmlStr(tds[1]) if len(tds) > 1 else ""
                    quality = self.cleanHtmlStr(tds[2]) if len(tds) > 2 else ""
                    name = host_name if host_name else "Nieznany serwer"
                    if version and version != host_name:
                        name += " - " + version
                    if quality:
                        name += " [" + quality + "]"
                    versions.append({
                        "name": name,
                        "link_id": link_id,
                        "url": cItem["url"],
                        "host": host_name,
                        "version": version,
                        "quality": quality,
                        "movie_title": movie_title
                    })
            if versions:
                self.cacheVersions[cacheKey] = versions
                printDBG("Filman.listVersions found %d versions" % len(versions))
            else:
                printDBG("Filman.listVersions no versions found")
                return
        for version in versions:
            display_title = version.get("movie_title", cItem.get("title", ""))
            display_title = self._cleanTitleForFilename(display_title)
            params = {
                "good_for_fav": True,
                "category": "resolve_version",
                "title": display_title,
                "desc": "Serwer: " + version["name"],
                "link_id": version["link_id"],
                "parent_url": version["url"],
                "movie_title": version.get("movie_title", cItem.get("title", "")),
                "icon": cItem.get("icon", self.DEFAULT_ICON_URL)
            }
            self.addVideo(params)

    def resolveVersion(self, cItem):
        printDBG("Filman.resolveVersion %s" % cItem)
        link_id = cItem.get("link_id")
        parent_url = cItem.get("parent_url", "")
        raw_title = cItem.get("movie_title", cItem.get("title", "Video"))
        title = self._cleanTitleForFilename(raw_title)
        if not link_id:
            printDBG("Filman.resolveVersion: no link_id")
            return []
        playerUrl = self._getLinkToken(link_id)
        if not playerUrl:
            printDBG("Filman.resolveVersion: failed to get token")
            self.sessionEx.open(MessageBox, _("Nie udało się pobrać linku do odtwarzania.\nSpróbuj ponownie później."), type=MessageBox.TYPE_ERROR, timeout=5)
            return []
        resolved_url = self.resolveEmbedUrl(playerUrl)
        if not resolved_url or not resolved_url.startswith("http"):
            printDBG("Filman.resolveVersion: invalid resolved URL")
            return []
        printDBG("Filman.resolveVersion success: %s" % resolved_url)
        return [{"name": title, "url": strwithmeta(resolved_url, {"Referer": parent_url}), "need_resolve": 1}]

    def getLinksForVideo(self, cItem):
        printDBG("Filman.getLinksForVideo %s" % cItem)
        category = cItem.get("category", "")
        if category == "resolve_version":
            return self.resolveVersion(cItem)
        if category == "list_versions":
            return self.listVersions(cItem)
        return []

    def rot13(self, s):
        result = []
        for c in s:
            if 'a' <= c <= 'z':
                result.append(chr((ord(c) - ord('a') + 13) % 26 + ord('a')))
            elif 'A' <= c <= 'Z':
                result.append(chr((ord(c) - ord('A') + 13) % 26 + ord('A')))
            else:
                result.append(c)
        return ''.join(result)

    def decodeEmbedUrl(self, encoded_string):
        try:
            decoded_base64 = ensure_str(base64.b64decode(encoded_string))
            decoded_rot13 = self.rot13(decoded_base64)
            return decoded_rot13
        except:
            return ""

    def _xd_decode(self, enc, key):
        try:
            raw = base64.b64decode(enc)
            if isinstance(raw, bytes):
                raw = raw.decode('latin-1')
            out = ''
            for i in range(len(raw)):
                out += chr(ord(raw[i]) ^ ord(key[i % len(key)]))
            return out
        except Exception as e:
            printDBG("_xd_decode error: %s" % str(e))
            return ""

    def getHostNameFromUrl(self, url):
        try:
            host = re.search(r'https?://([^/]+)', url).group(1)
            host = host.replace('www.', '')
            return host.split('.')[0]
        except:
            return "filman"

    def resolveEmbedUrl(self, embedUrl):
        if not embedUrl or embedUrl.startswith('#') or 'filman.cc/#' in embedUrl:
            return embedUrl
        params = dict(self.defaultParams)
        params["header"] = dict(params["header"])
        params["header"]["Referer"] = self.getMainUrl()
        sts, data = self.getPage(embedUrl, params)
        if not sts:
            return embedUrl
        finalUrl = ""
        e_match = re.search(r"var\s+_e\s*=\s*'([^']+)'", data)
        a_match = re.search(r"var\s+_a\s*=\s*'([^']+)'", data)
        b_match = re.search(r"var\s+_b\s*=\s*'([^']+)'", data)
        c_match = re.search(r"var\s+_c\s*=\s*'([^']+)'", data)
        if e_match and a_match and b_match and c_match:
            key = a_match.group(1) + b_match.group(1) + c_match.group(1)
            decoded_url = self._xd_decode(e_match.group(1), key)
            if decoded_url and decoded_url.startswith('http'):
                finalUrl = decoded_url
        if not finalUrl:
            encoded_var = self.cm.ph.getSearchGroups(data, r'''var\s+_e\s*=\s*['"]([^'"]+)['"]''')[0]
            if encoded_var:
                decoded_url = self.decodeEmbedUrl(encoded_var)
                if decoded_url and decoded_url.startswith('http'):
                    finalUrl = decoded_url
        if not finalUrl:
            iframe_src = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src=["\']([^"\']+)["\']')[0]
            if iframe_src and iframe_src.startswith('http') and 'favicon' not in iframe_src and 'embed.js' not in iframe_src:
                finalUrl = iframe_src
        if not finalUrl:
            for host in ['streamtape','doodstream','lulustream','voe','mixdrop','upstream','vidguard','wolfstream','filemoon','streamhub']:
                urls = re.findall(r'["\'](https?://[^"\']*' + host + r'[^"\']*)["\']', data, re.IGNORECASE)
                if urls:
                    finalUrl = urls[0]
                    break
        if finalUrl and not finalUrl.startswith("http"):
            finalUrl = self.getFullUrl(finalUrl)
        if finalUrl:
            finalUrl = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', finalUrl)
            if any(bad in finalUrl for bad in ['favicon', '.js', 'tenor.com']):
                finalUrl = ""
        return finalUrl or embedUrl

    def _getLinkToken(self, link_id):
        now = time.time()
        elapsed = now - self._lastTokenRequest
        if self._tokenRequestCount >= 6:
            printDBG("Filman._getLinkToken cooling down after 6 requests, waiting 5s")
            time.sleep(5)
            self._tokenRequestCount = 0
        elif elapsed < 2.5:
            time.sleep(2.5 - elapsed)
        self._lastTokenRequest = time.time()
        self._tokenRequestCount += 1
        params = dict(self.defaultParams)
        params["header"] = dict(params["header"])
        params["header"]["Referer"] = self.getMainUrl()
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        params["header"]["Accept"] = "application/json, text/javascript, */*; q=0.01"
        max_retries = 3
        for attempt in range(max_retries):
            url = self.getFullUrl("/link/token?link_id=%s" % link_id)
            printDBG("Filman._getLinkToken requesting: %s (attempt %d)" % (url, attempt + 1))
            sts, data = self.getPage(url, params)
            if sts:
                try:
                    resp = json.loads(data)
                    if resp.get("ok") and resp.get("url"):
                        decoded = ensure_str(base64.b64decode(resp["url"]))
                        printDBG("Filman._getLinkToken success")
                        self._tokenRequestCount = max(0, self._tokenRequestCount - 1)
                        return decoded
                    elif "Za szybko" in str(resp.get("error", "")) or "429" in str(data):
                        printDBG("Filman._getLinkToken rate limited, waiting 6s")
                        time.sleep(6)
                        self._tokenRequestCount = 0
                        continue
                    else:
                        error_msg = resp.get("error", "Unknown error")
                        printDBG("Filman._getLinkToken failed: %s" % error_msg)
                        if attempt < max_retries - 1:
                            time.sleep(1.5)
                            continue
                        return ""
                except Exception as e:
                    printDBG("Filman._getLinkToken parse error: %s" % str(e))
                    if attempt < max_retries - 1:
                        time.sleep(1.5)
                    continue
                    return ""
            else:
                printDBG("Filman._getLinkToken request failed, retrying")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return ""
        return ""

    def getVideoLinks(self, baseUrl):
        baseUrl = strwithmeta(baseUrl)
        for key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if baseUrl in self.cacheLinks[key][idx]["url"]:
                    if not self.cacheLinks[key][idx]["name"].startswith("*"):
                        self.cacheLinks[key][idx]["name"] = "*" + self.cacheLinks[key][idx]["name"] + "*"
                    break
        return self.up.getVideoLinkExt(baseUrl)

    def getArticleContent(self, cItem):
        printDBG("Filman.getArticleContent %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        desc = cItem.get("desc", "")
        year = ""
        duration = ""
        views = ""
        genres_str = ""
        single_info = self.cm.ph.getDataBeetwenNodes(data, ('<div', 'id="single-info"'), ('</div', '>'))[1]
        if single_info:
            h1_match = re.search(r'<h1[^>]*?itemprop="name"[^>]*?>(.*?)</h1>', single_info, re.DOTALL)
            if not h1_match:
                h1_match = re.search(r'<h1[^>]*?itemprop="partOfSeries"[^>]*?>(.*?)</h1>', single_info, re.DOTALL)
            if h1_match:
                title = self.cleanHtmlStr(h1_match.group(1))
            episode_subtitle = re.search(r'<span\s+itemprop="name">(.*?)</span>', single_info, re.DOTALL)
            if episode_subtitle:
                ep_name = self.cleanHtmlStr(episode_subtitle.group(1))
                if ep_name:
                    title = title + " - " + ep_name
            meta_items = re.findall(r'<div\s+class="flm-meta-item">(.*?)</div>', single_info, re.DOTALL)
            for meta in meta_items:
                value_match = re.search(r'<span\s+class="flm-meta-value">(.*?)</span>', meta, re.DOTALL)
                if value_match:
                    val = self.cleanHtmlStr(value_match.group(1))
                    if '📅' in meta:
                        year = val
                    elif '⏳' in meta:
                        duration = val
                    elif '👁' in meta:
                        views = val
            genres = re.findall(r'<a[^>]*?class="flm-genre-tag"[^>]*?>(.*?)</a>', single_info)
            genres_str = ", ".join([self.cleanHtmlStr(g) for g in genres])
        poster_match = re.search(r'<img\s+class="main-poster"[^>]*?src="([^"]+)"', data)
        if poster_match:
            icon = self.getFullIconUrl(poster_match.group(1))
        desc_match = re.search(r'<p\s+class="description">(.*?)</p>', data, re.DOTALL)
        if desc_match:
            desc = self.cleanHtmlStr(desc_match.group(1))
        desc_parts = []
        if year:
            desc_parts.append(_("Year: ") + year)
        if duration:
            desc_parts.append(_("Duration: ") + duration)
        if views:
            desc_parts.append(_("Views: ") + views)
        if genres_str:
            desc_parts.append(_("Genre: ") + genres_str)
        if desc:
            desc_parts.append(desc)
        full_desc = "[/br]".join(desc_parts)
        return [{"title": title, "text": full_desc, "images": [{"title": "", "url": icon}], "other_info": {"custom_items_list": []}}]

    def tryTologin(self):
        printDBG("tryTologin start")
        manual_sessid = config.plugins.iptvplayer.filman_cookie_phpsessid.value.strip()
        if manual_sessid:
            self._overwriteCookie(manual_sessid)
            sts, data = self.getPage(self.getFullUrl("/logowanie"))
            if sts and "/wylogowanie" in data:
                self.loggedIn = True
                self.cookieDeleted = False
                return True
        if self.loggedIn is None or self.login != config.plugins.iptvplayer.filman_login.value or self.password != config.plugins.iptvplayer.filman_password.value or self.cookieDeleted:
            self.login = config.plugins.iptvplayer.filman_login.value
            self.password = config.plugins.iptvplayer.filman_password.value
            if not self.login.strip() or not self.password.strip():
                return False
            login_params = dict(self.defaultParams)
            login_params["header"] = dict(login_params["header"])
            login_params["header"]["Referer"] = self.getFullUrl("/logowanie")
            sts, data = self.getPage(self.getFullUrl("/logowanie"), login_params)
            if not sts:
                return False
            if "/wylogowanie" in data:
                self.loggedIn = True
                self.cookieDeleted = False
                return True
            csrf_token = ""
            tmp = self.cm.ph.getSearchGroups(data, r'name="_csrf" value="([^"]+)"')
            if tmp:
                csrf_token = tmp[0]
            printDBG("tryTologin CSRF token: [%s]" % csrf_token)
            post_data = {
                "login": self.login,
                "password": self.password,
                "remember": "on",
                "submit": ""
            }
            if csrf_token:
                post_data["_csrf"] = csrf_token
            sitekey = "6LcQs24iAAAAALFibpEQwpQZiyhOCn-zdc-eFout"
            token = None
            printDBG("Trying sitekey: %s" % sitekey)
            token, _ = self.processCaptcha(sitekey, self.getFullUrl("/logowanie"))
            if not token:
                ent_sitekey = "6LdjECEpAAAAAII12AekMIVTsLnFA6A1Qeu7YRnU"
                printDBG("Trying enterprise sitekey: %s" % ent_sitekey)
                token, _ = self.processCaptcha(ent_sitekey, self.getFullUrl("/logowanie"))
            if token:
                post_data["g-recaptcha-response"] = token
                printDBG("Got recaptcha token")
            else:
                printDBG("Failed to get any recaptcha token – login will likely fail")
            sts, _ = self.getPage(self.getFullUrl("/logowanie"), login_params, post_data)
            sts, data = self.getPage(self.getFullUrl("/logowanie"), login_params)
            if sts and "/wylogowanie" in data:
                self.loggedIn = True
                self.cookieDeleted = False
            else:
                self.loggedIn = False
                msg = ""
                tmp2 = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "alert"), ("</div", ">"))
                if tmp2:
                    msg = self.cleanHtmlStr(tmp2[1])
                self.sessionEx.open(MessageBox, _("Login failed.") + "\n" + msg, type=MessageBox.TYPE_ERROR, timeout=10)
        return self.loggedIn

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filman.listSearchResult searchPattern=%s" % searchPattern)
        url = self.getFullUrl("/search?phrase=%s") % urllib_quote_plus(searchPattern)
        params = {"name": "category", "category": "list_items", "good_for_fav": False, "url": url}
        self.listItems(params)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        self.currList = []
        if name is None and category == "":
            self.listMainMenu({"name": "category"})
        elif category in ["list_cats", "list_years", "list_az"]:
            self.listMovieFilters(self.currItem, "list_sort")
        elif category == "list_sort":
            self.listMovieFilters(self.currItem, "list_items")
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_series":
            self.listSeries(self.currItem)
        elif category == "list_versions":
            self.listVersions(self.currItem)
        elif category == "resolve_version":
            links = self.getLinksForVideo(self.currItem)
            for link in links:
                self.addVideo(link)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Filman(), True, [])

    def withArticleContent(self, cItem):
        return True
