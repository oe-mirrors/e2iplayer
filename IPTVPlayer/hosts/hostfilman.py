# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 25.06.2026 - damagic
# 10.10.2026 - host standard: watched flag (series -> season -> episode; a series with more than one season gets
#   season folders), favourites reopen without state, downloaded marker on the film / episode url,
#   "Title (Year)" / "Show - SxxExx" names only when name normalisation is on (raw site labels otherwise),
#   sidecar on the links, First / Jump / Next page, INFO via moviemeta merged with the
#   site's fields, default user agent; the PHPSESSID option is a hidden secret now and no longer overwrites the
#   whole cookie file on every list (that threw away the Cloudflare clearance), dead rot13 helpers removed
#   links are no longer renamed to "*name*" after use - that broke the link list's own used mark (tick + colour)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError, TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems

###################################################
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
from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret

###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filman_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.filman_password = ConfigSecret(default="", fixed_size=False)
# a session cookie of the user's own browser login - a secret like the password
config.plugins.iptvplayer.filman_cookie_phpsessid = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Filman %s:" % _("login"), config.plugins.iptvplayer.filman_login))
    optionList.append(getConfigListEntry("Filman %s:" % _("password"), config.plugins.iptvplayer.filman_password))
    optionList.append(getConfigListEntry("Filman cookie (PHPSESSID):", config.plugins.iptvplayer.filman_cookie_phpsessid))
    return optionList


###################################################


def gettytul():
    return "https://filman.cc/"


class Filman(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_year", "season", "episode", "meta_type", "sort")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filman.online", "cookie": "filman.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.MAIN_URL = "https://filman.cc/"
        # the site logo sits behind Cloudflare too and is asked for before the check is solved (main menu): use the plugin's tile
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/filman135.png")
        self.HTTP_HEADER = {"User-Agent": self.USER_AGENT, "DNT": "1", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "Accept-Language": "pl,en-US;q=0.7,en;q=0.3", "Referer": self.getMainUrl(), "Origin": self.getMainUrl(), "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1"}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json, text/javascript, */*; q=0.01"})

        self.cacheMovieFilters = {"cats": [], "sort": [], "years": [], "az": []}
        self.cacheLinks = {}
        self.pendingLinks = {}
        self.defaultParams = {"header": self.HTTP_HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.loggedIn = None
        self.login = ""
        self.password = ""
        self.sessid = ""
        self.watchedHelper = IPTVWatchedHelper("filman")
        self.wfInitFolderCache()

    def _setSessionCookie(self, sessid):
        # puts the user's PHPSESSID into the cookie jar and keeps the other cookies (cf_clearance!)
        try:
            lines = []
            if os.path.isfile(self.COOKIE_FILE):
                with open(self.COOKIE_FILE, "r") as f:
                    lines = [line for line in f.read().splitlines() if line.strip() and "\tPHPSESSID\t" not in line]
            if not lines or not lines[0].startswith("#"):
                lines.insert(0, "# Netscape HTTP Cookie File")
            lines.append("filman.cc\tFALSE\t/\tFALSE\t0\tPHPSESSID\t" + sessid)
            with open(self.COOKIE_FILE, "w") as f:
                f.write("\n".join(lines) + "\n")
            printDBG("Filman PHPSESSID set in the cookie file")
            return True
        except Exception as e:
            printDBG("Failed to write cookie: %s" % str(e))
            return False

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl.split("#", 1)[0])
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def getFullIconUrl(self, url, currUrl=None):
        # the posters sit behind the same Cloudflare check as the pages: the icon download needs the site's
        # cf_clearance cookie and the User-Agent that passed the check, otherwise it gets a 403
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.getMainUrl()}
        cookieHeader = ""
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            if os.path.isfile(self.COOKIE_FILE):
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ")
            if cookieHeader:
                from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not url:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            prefix = {"list_series": "series", "list_season": "season"}.get(cItem.get("category", ""), "")
            return "%s:%s" % (prefix, url) if prefix else ""
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
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
            if params.get("category") == "list_items":
                params["good_for_fav"] = True
            self.addDir(params)

    def _parseItemInfo(self, item):
        info = {"title": "", "icon": "", "year": "", "quality": "", "rating": "", "desc": ""}

        link_match = re.search(r'<a\s+href="([^"]+)"', item)
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

    def _cleanTitleForFilename(self, title, year=""):
        if not title:
            return "Video"
        title = title.split('/')[0].strip()
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        if not title:
            return "Video"
        if year:
            title = title + " (" + year + ")"
        return title

    @staticmethod
    def _seriesName(title):
        # "Wiedźmin / The Witcher (2019) online pl" -> "Wiedźmin"
        title = re.sub(r'\s*\(\d{4}\)\s*$', '', title or '').strip()
        title = re.sub(r'\s*\bonline\s+pl\b\s*', '', title, flags=re.IGNORECASE).strip()
        return title.split('/')[0].strip()

    def listItems(self, cItem):
        printDBG("Filman.listItems %s" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        # the pager rows carry the url of the list itself in base_url (their own url is only for Jump)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl
        sort = cItem.get("sort", "")
        if sort and sort not in url:
            url = url + sort
        listUrl = url
        if page > 1:
            sep = "&" if "?" in url else "?"
            url = "%s%spage=%d" % (url, sep, page)

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta["url"])

        is_search = "search?phrase=" in baseUrl
        if is_search and "/logowanie" in data.meta.get("url", ""):
            # since 10.2026 the site sends a search without a login to its login page
            SetIPTVPlayerLastHostError(_("Login needed"))
            return

        if is_search:
            items = []
            item_lists = re.findall(r'<div id="item-list" class="row">(.*?)</div>\s*</div>\s*</div>', data, re.DOTALL)
            if not item_lists:
                item_lists = re.findall(r'<div id="item-list" class="row">(.*?)</div>\s*</div>', data, re.DOTALL)
            for item_list in item_lists:
                raw_items = item_list.split('<div class="col-xs-6 col-sm-3 col-lg-2">')[1:]
                for raw in raw_items:
                    items.append('<div class="col-xs-6 col-sm-3 col-lg-2">' + raw)
        else:
            items = []
            item_section = ""
            for tag_open, tag_close in [
                (('<div', 'id="item-list"'), ('<div', 'class="text-center"')),
                (('<div', 'id="item-list"'), ('</div', '>')),
                (('<div', 'id="item-list"'), ('<footer', '>')),
                (('<div', 'id="item-list"'), ('<script', '>')),
            ]:
                item_section = self.cm.ph.getDataBeetwenNodes(data, tag_open, tag_close)[1]
                if item_section:
                    break
            if not item_section:
                tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wrapper">', '<footer>', False)[1]
                if tmp:
                    for tag_open, tag_close in [
                        (('<div', 'id="item-list"'), ('<div', 'class="text-center"')),
                        (('<div', 'id="item-list"'), ('</div', '>')),
                        (('<div', 'id="item-list"'), ('<script', '>')),
                    ]:
                        item_section = self.cm.ph.getDataBeetwenNodes(tmp, tag_open, tag_close)[1]
                        if item_section:
                            break
            if item_section:
                raw_items = item_section.split('<div class="col-xs-6 col-sm-3 col-lg-2">')[1:]
                for raw in raw_items:
                    items.append('<div class="col-xs-6 col-sm-3 col-lg-2">' + raw)
            if not items:
                items = re.findall(r'<div class="col-xs-6 col-sm-3 col-lg-2">.*?</div>\s*</div>\s*</div>', data, re.DOTALL)

        printDBG("Filman.listItems found %d items" % len(items))

        normalize = IsMediaNamingNormalized()
        for item in items:
            info = self._parseItemInfo(item)
            if "url" not in info:
                continue

            film_url = info["url"]
            title = info["title"]
            icon = info.get("icon") or self.DEFAULT_ICON_URL

            desc_parts = []
            if info["year"]:
                desc_parts.append(_("Year:") + " " + info["year"])
            if info["rating"]:
                desc_parts.append(_("Rating:") + " " + info["rating"])
            if info["quality"]:
                desc_parts.append(_("Quality:") + " " + info["quality"])
            if info["desc"]:
                desc_parts.append(info["desc"])
            full_desc = "[/br]".join(desc_parts)

            is_series = "/s/" in film_url or "/serial/" in film_url
            if not is_series and not title:
                continue

            if is_series:
                display_title = title
                if info["year"] and info["year"] not in display_title:
                    display_title = display_title + " (" + info["year"] + ")"
                params = {"name": "category", "good_for_fav": True, "category": "list_series", "url": film_url, "title": display_title, "desc": full_desc, "icon": icon,
                          "s_title": self._seriesName(title), "s_year": info["year"], "meta_type": "tv"}
                self.addDir(params)
            else:
                params = {"name": "category", "good_for_fav": True, "url": film_url, "title": self._cleanTitleForFilename(title, info["year"]) if normalize else title,
                          "desc": full_desc, "icon": icon, "s_title": title, "s_year": info["year"], "meta_type": "movie"}
                self.addVideo(params)

        if not is_search:
            next_page_match = re.search(r'''<li\s+class=['"]next['"]\s*>\s*<a\s+href=['"]\?page=(\d+)['"][^>]*>Nast''', data)
            if not next_page_match:
                next_page_match = re.search(r'''<li\s+class=['"]next['"]\s*>\s*<a\s+href=['"]\?page=(\d+)['"]''', data)
            if not next_page_match:
                printDBG("Filman.listItems NO next page found in data")
            # no last page: the pager behind the Cloudflare check could not be checked for a "last" link, and the
            # highest number of a pager window would cap Jump below the real end
            tpl = listUrl.replace("{", "{{").replace("}", "}}") + ("&" if "?" in listUrl else "?") + "page={page}"
            addPagingItems(self, dict(cItem, base_url=baseUrl), page, bool(next_page_match) and bool(items), 0, tpl)

    def _episodes(self, data):
        # [(season, episode, url, ep_title)] in page order - "[s01e02] Title" links to /e/...
        episodes = []
        for url, raw_title in re.findall(r'<a\s+href=["\']([^"\']+)["\'][^>]*?>\s*(.*?)</a>', data, re.DOTALL | re.IGNORECASE):
            if '/e/' not in url:
                continue
            url = self.getFullUrl(url)
            if url == "" or url in [e[2] for e in episodes]:
                continue
            raw_title = self.cleanHtmlStr(raw_title).strip()
            match = re.match(r'\[?s(\d+)e(\d+)\]?\s*(.*)', raw_title, re.IGNORECASE)
            if match:
                episodes.append((str(int(match.group(1))), str(int(match.group(2))), url, match.group(3).strip()))
            else:
                episodes.append(("", "", url, raw_title))
        return episodes

    def listSeries(self, cItem):
        printDBG("Filman.listSeries %s" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta["url"])
        episodes = self._episodes(data)
        seasons = []
        for ep in episodes:
            if ep[0] and ep[0] not in seasons:
                seasons.append(ep[0])
        sTitle = cItem.get("s_title", "") or self._seriesName(cItem.get("title", ""))
        if len(seasons) < 2:
            self.listEpisodes(dict(cItem, s_title=sTitle), episodes)
            return
        normalize = IsMediaNamingNormalized()
        for season in sorted(seasons, key=int):
            count = len([ep for ep in episodes if ep[0] == season])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_season", "season": season, "s_title": sTitle, "url": "%s#s%s" % (url, season),
                           "title": "%s - %s" % (sTitle, formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)),
                           "desc": "%s: %d\n%s" % (_("Episodes"), count, cItem.get("desc", ""))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("Filman.listEpisodes %s" % cItem)
        season = str(cItem.get("season", "") or "")
        if episodes is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            episodes = [ep for ep in self._episodes(data) if ep[0] == season]
        sTitle = cItem.get("s_title", "") or self._seriesName(cItem.get("title", ""))
        normalize = IsMediaNamingNormalized()
        for epSeason, epNum, url, epTitle in episodes:
            if normalize and epSeason and epNum:
                title = "%s - %s" % (sTitle, formatSxxExx(epSeason, epNum))
            elif epNum:
                tag = "S%02dE%02d" % (int(epSeason), int(epNum))
                title = self._cleanTitleForFilename("%s [%s] %s" % (sTitle, tag, epTitle) if epTitle else "%s [%s]" % (sTitle, tag))
            else:
                title = self._cleanTitleForFilename("%s - %s" % (sTitle, epTitle))
            params = {"name": "category", "good_for_fav": True, "url": url, "title": title, "icon": cItem.get("icon", ""), "s_title": sTitle,
                      "s_year": cItem.get("s_year", ""), "season": epSeason, "episode": epNum, "meta_type": "tv",
                      "desc": "%s[/br]%s" % (epTitle, cItem.get("desc", "")) if epTitle else cItem.get("desc", "")}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        url = self.getFullUrl("/search?phrase=%s") % urllib_quote_plus(searchPattern)
        params = {"name": "category", "category": "list_items", "good_for_fav": False, "url": url}
        self.listItems(params)

    def getHostNameFromUrl(self, url):
        try:
            host = re.search(r'https?://([^/]+)', url).group(1)
            host = host.replace('www.', '')
            return host.split('.')[0]
        except Exception:
            return "filman"

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

    def _tryDecodeXdFromData(self, data):
        e_match = re.search(r"var\s+_e\s*=\s*'([^']+)'", data)
        a_match = re.search(r"var\s+_a\s*=\s*'([^']+)'", data)
        b_match = re.search(r"var\s+_b\s*=\s*'([^']+)'", data)
        c_match = re.search(r"var\s+_c\s*=\s*'([^']+)'", data)

        if e_match and a_match and b_match and c_match:
            _e = e_match.group(1)
            _a = a_match.group(1)
            _b = b_match.group(1)
            _c = c_match.group(1)
            key = _a + _b + _c
            decoded_url = self._xd_decode(_e, key)
            if decoded_url and decoded_url.startswith('http'):
                return decoded_url
        return ""

    def _tryFindIframeOrHostUrl(self, data):
        iframe_src = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src=["\']([^"\']+)["\']')[0]
        if iframe_src and iframe_src.startswith('http') and 'favicon' not in iframe_src and 'embed.js' not in iframe_src:
            return iframe_src

        for host in ['streamtape', 'doodstream', 'lulustream', 'voe', 'mixdrop', 'upstream', 'vidguard', 'wolfstream', 'filemoon', 'streamhub', 'vidoza', 'vidmoly', 'savefiles', 'veev', 'vrra', 'myvidplay', 'vidara']:
            urls = re.findall(r'["\'](https?://[^"\']*' + host + r'[^"\']*(?:/e/|/embed/)[^"\']*)["\']', data, re.IGNORECASE)
            if urls:
                return urls[0]
        return ""

    def _getLinkToken(self, link_id):
        # the token endpoint refuses requests that come right after the page (the author's value, see #476)
        time.sleep(1.0)

        params = dict(self.defaultParams)
        params["header"] = dict(params["header"])
        params["header"]["Referer"] = self.getMainUrl()
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        params["header"]["Accept"] = "application/json, text/javascript, */*; q=0.01"

        url = self.getFullUrl("/link/token?link_id=%s" % link_id)
        printDBG("Filman._getLinkToken requesting: %s" % url)
        sts, data = self.getPage(url, params)

        if sts and data:
            try:
                resp = json.loads(data)
                if resp.get("ok") and resp.get("url"):
                    decoded = ensure_str(base64.b64decode(resp["url"]))
                    printDBG("Filman._getLinkToken success")
                    return decoded
                else:
                    printDBG("Filman._getLinkToken failed: %s" % data)
                    return ""
            except Exception as e:
                printDBG("Filman._getLinkToken parse error: %s" % str(e))
                return ""
        else:
            printDBG("Filman._getLinkToken request failed")
            return ""

    def getLinksForVideo(self, cItem):
        cacheKey = cItem["url"]
        if cacheKey in self.cacheLinks:
            return self.cacheLinks[cacheKey]
        self.cacheLinks = {}

        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []

        links_section = self.cm.ph.getDataBeetwenNodes(data, ("<table", ">", "links"), ("</table", ">"))[1]
        retTab = []
        if links_section:
            rows = self.cm.ph.getAllItemsBeetwenNodes(links_section, ("<tr", ">"), ("</tr", ">"))
            for row in rows:
                if "<th" in row:
                    continue
                player_data = self.cm.ph.getDataBeetwenNodes(row, ("<td", ">", "link-to-video"), ("</td", ">"))[1]
                if not player_data:
                    continue

                link_id = self.cm.ph.getSearchGroups(player_data, r'''data-link-id=['"]([^"^']+?)['"]''')[0]
                if not link_id:
                    iframe_data = self.cm.ph.getSearchGroups(player_data, r'''data-iframe=['"]([^"^']+?)['"]''')[0]
                    if iframe_data:
                        try:
                            decoded = ensure_str(base64.b64decode(iframe_data))
                            try:
                                player_data_json = json.loads(decoded)
                                playerUrl = player_data_json.get("src", "")
                            except Exception:
                                playerUrl = decoded
                        except Exception:
                            playerUrl = ""

                        if playerUrl and playerUrl.startswith('http'):
                            host_name = self.getHostNameFromUrl(playerUrl)
                            name = host_name
                            retTab.append({"name": name, "url": strwithmeta(playerUrl, {"Referer": cItem["url"]}), "need_resolve": 1})
                    continue

                tds = self.cm.ph.getAllItemsBeetwenNodes(row, ("<td", ">"), ("</td", ">"))
                version = self.cleanHtmlStr(tds[1]) if len(tds) > 2 else ""
                quality = self.cleanHtmlStr(tds[2]) if len(tds) > 2 else ""

                server_td = tds[0]
                img_alt = self.cm.ph.getSearchGroups(server_td, r'<img[^>]+alt=["\']([^"\']+)["\']')[0]
                if img_alt:
                    host_name = img_alt.strip()
                else:
                    host_name = self.cleanHtmlStr(server_td).strip()

                name = host_name if host_name else "filman"
                if version and version != host_name:
                    name += " - " + version
                if quality:
                    name += " - " + quality

                self.pendingLinks[link_id] = {"link_id": link_id, "url": cItem["url"]}

                retTab.append({"name": name, "url": strwithmeta(link_id, {"Referer": cItem["url"], "link_id": link_id, "pending": True}), "need_resolve": 1})
        if retTab:
            retTab = applySidecarToLinks(retTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))
            self.cacheLinks[cacheKey] = retTab
        elif links_section and "/premium" in links_section:
            SetIPTVPlayerLastHostError("Only premium links are available for this title.")
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Filman.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        sidecar = sidecarFromUrlMeta(baseUrl, IsSidecarEnabled())

        link_id = baseUrl.meta.get("link_id", "")
        is_pending = baseUrl.meta.get("pending", False)

        if not link_id or not is_pending:
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(baseUrl), sidecar)

        embed_url = self._getLinkToken(link_id)
        if not embed_url:
            return []

        params = dict(self.defaultParams)
        params["header"] = dict(params["header"])
        params["header"]["Referer"] = self.getMainUrl()
        sts, data = self.getPage(embed_url, params)
        if not sts:
            return []

        finalUrl = self._tryDecodeXdFromData(data)

        if not finalUrl:
            finalUrl = self._tryFindIframeOrHostUrl(data)

        if not finalUrl:
            return []

        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(finalUrl, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Filman.getArticleContent %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            data = ""

        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        desc = ""
        pageTitle = ""
        info = {}

        single_info = self.cm.ph.getDataBeetwenNodes(data, ('<div', 'id="single-info"'), ('</div', '>'))[1]

        if single_info:
            h1_match = re.search(r'<h1[^>]*?itemprop="name"[^>]*?>(.*?)</h1>', single_info, re.DOTALL)
            if not h1_match:
                h1_match = re.search(r'<h1[^>]*?itemprop="partOfSeries"[^>]*?>(.*?)</h1>', single_info, re.DOTALL)
            if h1_match:
                pageTitle = self.cleanHtmlStr(h1_match.group(1))
                pageTitle = re.sub(r'\s*\bonline\s+pl\b\s*', '', pageTitle, flags=re.IGNORECASE).strip()

            meta_items = re.findall(r'<div\s+class="flm-meta-item">(.*?)</div>', single_info, re.DOTALL)
            for meta in meta_items:
                value_match = re.search(r'<span\s+class="flm-meta-value">(.*?)</span>', meta, re.DOTALL)
                if value_match:
                    val = self.cleanHtmlStr(value_match.group(1))
                    if '📅' in meta:
                        info["year"] = val
                    elif '⏳' in meta:
                        info["duration"] = val
                    elif '👁' in meta:
                        info["views"] = val

            genres = re.findall(r'<a[^>]*?class="flm-genre-tag"[^>]*?>(.*?)</a>', single_info)
            genres_str = ", ".join([self.cleanHtmlStr(g) for g in genres])
            if genres_str:
                info["genres"] = genres_str

        poster_match = re.search(r'<img\s+class="main-poster"[^>]*?src="([^"]+)"', data)
        if poster_match:
            icon = self.getFullIconUrl(poster_match.group(1))

        desc_match = re.search(r'<p\s+class="description">(.*?)</p>', data, re.DOTALL)
        if desc_match:
            desc = self.cleanHtmlStr(desc_match.group(1))

        # moviemeta: the IMDb id when the page links it, else the original title ("Pacjent / The Patient")
        mediaType = cItem.get("meta_type", "") or ("tv" if re.search(r"/(?:s|e|serial)/", cItem["url"]) else "movie")
        name = cItem.get("s_title", "") or pageTitle or title
        if mediaType == "tv":
            name = self._seriesName(pageTitle if (pageTitle and not cItem.get("s_title")) else name)
        lookup = name.split("/")[-1].strip() if "/" in name else name
        year = info.get("year", "") or cItem.get("s_year", "")
        meta = {}
        try:
            imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and lookup:
                meta = getMeta(mediaType, lookup, "" if mediaType == "tv" else year)
        except Exception:
            printExc()
        otherInfo = dict(meta.get("info", {}))
        otherInfo.update(info)
        text = desc or cItem.get("desc", "")
        metaPlot = meta.get("plot", "")
        if metaPlot and text and metaPlot not in text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = icon or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    ###################################################
    # login (own account / own browser session only)
    ###################################################
    def tryTologin(self):
        printDBG("tryTologin start")
        manual_sessid = config.plugins.iptvplayer.filman_cookie_phpsessid.value.strip()
        if manual_sessid:
            if manual_sessid == self.sessid:
                return self.loggedIn
            self.sessid = manual_sessid
            self._setSessionCookie(manual_sessid)
            sts, data = self.getPage(self.getFullUrl("/logowanie"))
            if sts and "/wylogowanie" in data:
                self.loggedIn = True
                return True
        else:
            self.sessid = ""

        if self.loggedIn is None or self.login != config.plugins.iptvplayer.filman_login.value or self.password != config.plugins.iptvplayer.filman_password.value:
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
            token, _unused = self.processCaptcha(sitekey, self.getFullUrl("/logowanie"))
            if not token:
                ent_sitekey = "6LdjECEpAAAAAII12AekMIVTsLnFA6A1Qeu7YRnU"
                printDBG("Trying enterprise sitekey: %s" % ent_sitekey)
                token, _unused = self.processCaptcha(ent_sitekey, self.getFullUrl("/logowanie"), captchaType="ENTERPRISE")

            if token:
                post_data["g-recaptcha-response"] = token
                printDBG("Got recaptcha token")
            else:
                printDBG("Failed to get any recaptcha token - login will likely fail")

            sts, _unused = self.getPage(self.getFullUrl("/logowanie"), login_params, post_data)
            sts, data = self.getPage(self.getFullUrl("/logowanie"), login_params)
            if sts and "/wylogowanie" in data:
                self.loggedIn = True
            else:
                self.loggedIn = False
                msg = ""
                tmp2 = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "alert"), ("</div", ">"))
                if tmp2:
                    msg = self.cleanHtmlStr(tmp2[1])
                try:
                    login_failed_text = str(_("Login failed."))
                except (TypeError, AttributeError):
                    login_failed_text = "Login failed."
                error_msg = login_failed_text
                if msg:
                    error_msg += "\n" + ensure_str(str(msg))
                self.sessionEx.open(MessageBox, error_msg, type=MessageBox.TYPE_ERROR, timeout=10)

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        self.cacheLinks = {}
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
        elif category == "list_season":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Filman(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filman")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_series", "list_season")
