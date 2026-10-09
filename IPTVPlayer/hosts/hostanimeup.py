# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - Anime4up (w1.anime4up.rest, Arabic-subtitled / dubbed anime, WordPress "Anime4up" theme): latest
#     episodes, anime list, movies, dubbed, subtitled, genres, seasons, A-Z and search, each with First page /
#     Jump / Next page from the site's /page/N/ pager
#   - Cloudflare challenges every request there (curl-impersonate included, 08.10.2026): pages go through
#     getPageCFProtection (MyE2i solve on the box), covers on the site's domain get the same cf_clearance cookie
#     and the User-Agent that passed the check
#   - anime -> episodes (VIDEO rows keyed on the episode page url, ascending, the show's own pager) + a folder
#     of the related seasons / works; the episode page's server list (data-watch, or the theme's AJAX player
#     when the page carries TxPlayerNonce) goes to urlparser, hosters urlparser does not know are left out
#   - watched flag (show -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx", the season taken from "2nd Season" / "Season 2" in the show name), sidecar, INFO via
#     moviemeta + the anime page's own fields
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://w1.anime4up.rest/"


# favourites of an older anime4up address are moved to the current one
OLD_DOMAIN_RE = re.compile(r"^https?://[^/]*anime4up[^/]*/")
CARD_START = '<div class="anime-card-themex">'
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
# "Kingdom 6th Season" / "Spy x Family Season 3" / "One Punch Man 3" keep their number in the name: the season
# is read from the first two forms only
SEASON_RE = re.compile(r"(?i)[\s:-]*(?:(\d+)(?:st|nd|rd|th) season|season ?(\d+))\b")
YEAR_RE = re.compile(r"((?:19|20)\d{2})")
# "<span>label:</span> value" rows of the anime page -> INFO keys
INFO_KEYS = (("category", "نوع الأنمي"), ("year", "بداية العرض"), ("episodes", "عدد الحلقات"), ("duration", "مدة الحلقة"),
             ("seasons", "الموسم"), ("status", "حالة الأنمي"))
RELATED_ENDS = ('class="comments', "<footer")
VIDEO_CATEGORIES = ("a4_video",)
FOLDER_CATEGORIES = ("a4_show",)


def _splitSeason(name):
    # "Honzuki no Gekokujou 4th Season" -> ("Honzuki no Gekokujou", 4); no season word -> (name, 1)
    match = SEASON_RE.search(name or "")
    if not match:
        return name, 1
    base = (name[:match.start()] + name[match.end():]).strip(" :-")
    return (base or name), int(match.group(1) or match.group(2))


def _year(text):
    match = YEAR_RE.search(text or "")
    return match.group(1) if match else ""


def _cards(data):
    # the anime-card-themex blocks of a page
    return data.split(CARD_START)[1:]


def _section(data, start, ends):
    # data from the start marker up to the first end marker that follows ("" without the start marker)
    pos = data.find(start)
    if pos < 0:
        return ""
    data = data[pos + len(start):]
    for end in ends:
        cut = data.find(end)
        if cut >= 0:
            data = data[:cut]
    return data


class Anime4up(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "anime4up", "cookie": "anime4up.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/animeup135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("anime4up")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        sts, data = self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)
        if not sts:
            # otherwise the list just stays empty: the Cloudflare check was not solved (MyE2i closed / no answer)
            # or the site refuses the country (Cloudflare 1009 / HTTP 451)
            meta = getattr(data, "meta", None) or {}
            body = "%s %s" % (meta.get("body_head") or "", data if isinstance(data, str) else "")
            if meta.get("status_code") == 451 or ("1009" in body and "country" in body):
                SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            else:
                SetIPTVPlayerLastHostError(_("The site's browser check (Cloudflare) could not be passed. The site may also be blocked in your country."))
        return sts, data

    @staticmethod
    def _quote(url):
        # the site writes its Arabic paths percent-encoded in lower case, the address bar unencoded: one form
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(OLD_DOMAIN_RE.sub(self.MAIN_URL, url))

    def _path(self, url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(self._canonUrl(url))).split("?")[0].rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        # the covers sit behind the same Cloudflare check as the pages: their download needs the cf_clearance
        # cookie and the User-Agent that passed the check (attached here, the host base runs every icon through
        # getFullIconUrl again)
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or "anime4up" not in self.up.getDomain(url):
            return url
        url = self._canonUrl(url)
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("a4_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "a4_latest", "title": _("Latest episodes"), "url": self.getFullUrl("/episode/")},
            {"category": "a4_list", "title": _("Anime list"), "url": self.getFullUrl("/قائمة-الانمي/")},
            {"category": "a4_list", "title": _("Movies"), "url": self.getFullUrl("/anime-type/movie-3/")},
            {"category": "a4_list", "title": _("Dubbed"), "url": self.getFullUrl("/anime-category/الانمي-المدبلج/")},
            {"category": "a4_list", "title": _("Subbed anime"), "url": self.getFullUrl("/anime-category/الأنمي-المترجم/")},
            {"category": "a4_filter", "title": _("Genres"), "marker": "genresDropdown"},
            {"category": "a4_filter", "title": _("Seasons"), "marker": "seasonsDropdown"},
            {"category": "a4_filter", "title": _("Alphabetically"), "marker": "e-alphabetical-filter"},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilter(self, cItem):
        # genres / seasons / letters from the filter bar of the anime list page
        sts, data = self.getPage(self.getFullUrl("/قائمة-الانمي/"))
        if not sts:
            return
        marker = cItem.get("marker", "")
        block = self.cm.ph.getDataBeetwenMarkers(data, marker, "</ul>", False)[1] if marker else ""
        for href, label in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block):
            title = self.cleanHtmlStr(label)
            if title:
                self.addDir({"name": "category", "category": "a4_list", "good_for_fav": True, "title": title, "url": self._canonUrl(href)})

    def _pageTpl(self, pager):
        # the url of any numbered pager link with its number replaced by {page}
        for href, num in re.findall(r"""href=['"]([^'"]+)['"][^>]*>\s*(\d+)\s*<""", pager):
            href = self._canonUrl(href)
            tpl = re.sub(r"(/page/|[?&]page=|[?&]ep_page=)%s(?=\D|$)" % num, r"\g<1>{page}", href, count=1)
            if "{page}" in tpl:
                return tpl
        return ""

    def _pager(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="page-numbers"', "</ul>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</nav>", False)[1]
        lastPage = max([int(n) for n in re.findall(r">\s*(\d+)\s*<", block)] + [0])
        return self._pageTpl(block), lastPage

    def _showFromCard(self, card):
        href = self.cm.ph.getSearchGroups(card, r'<h3[^>]*>\s*<a href="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)"\s+class="overlay"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r"(?s)<h3[^>]*>(.*?)</h3>")[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'alt="([^"]+)"')[0])
        if not href or not title:
            return None
        icon = self.cm.ph.getSearchGroups(card, r'data-image="([^"]+)"')[0]
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="anime-card-type">(.*?)</div>')[0])
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'data-content="([^"]*)"')[0])
        return {"url": self._canonUrl(href), "title": title, "icon": self.getFullIconUrl(icon) if icon else "", "kind": kind, "story": story}

    def _addShow(self, show):
        name, season = _splitSeason(show["title"])
        isMovie = show["kind"].lower() == "movie"
        desc = show["kind"]
        if show["story"]:
            desc = "%s[/br]%s" % (desc, show["story"]) if desc else show["story"]
        self.addDir({"name": "category", "category": "a4_show", "good_for_fav": True, "url": show["url"], "title": show["title"],
                     "icon": show["icon"], "desc": desc, "s_title": name, "s_season": season, "meta_type": "movie" if isMovie else "tv",
                     "meta_title": name})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not pageTpl else pageTpl.format(page=page)
        printDBG("Anime4up.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        grid = data.split('class="anime-list-content"', 1)[-1]
        seen = set()
        for card in _cards(grid):
            show = self._showFromCard(card)
            if not show or show["url"] in seen:
                continue
            seen.add(show["url"])
            self._addShow(show)
        tpl, lastPage = self._pager(data)
        pageTpl = pageTpl or tpl
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, bool(seen) and bool(pageTpl) and lastPage > page, lastPage, pageTpl)

    def listLatest(self, cItem):
        # "pinned-card" tiles of the latest episodes: show name, episode number, episode page
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not pageTpl else pageTpl.format(page=page)
        printDBG("Anime4up.listLatest [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        seen = set()
        for tile in data.split('<div class="pinned-card">')[1:]:
            href = self.cm.ph.getSearchGroups(tile, r'<a href="([^"]+)"')[0]
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tile, r"(?s)<h3>(.*?)</h3>")[0])
            episode = EPISODE_RE.search(self.cleanHtmlStr(tile))
            if not href or not show or href in seen:
                continue
            seen.add(href)
            name, season = _splitSeason(show)
            label = "%s - %s" % (show, self.cleanHtmlStr(episode.group(0))) if episode else show
            icon = self.cm.ph.getSearchGroups(tile, r'data-src="([^"]+)"')[0]
            info = " | ".join(self.cleanHtmlStr(x) for x in re.findall(r'(?s)<span class="anime-(?:type|duration)">(.*?)</span>', tile))
            self.addVideo({"name": "category", "category": "a4_video", "good_for_fav": True, "url": self._canonUrl(href),
                           "title": self._episodeTitle(name, season, episode.group(1) if episode else "", label),
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": info, "s_title": name, "s_season": season,
                           "s_episode": episode.group(1) if episode else "", "meta_type": "tv", "meta_title": name})
        tpl, lastPage = self._pager(data)
        pageTpl = pageTpl or tpl
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, bool(seen) and bool(pageTpl) and lastPage > page, lastPage, pageTpl)

    def listShow(self, cItem):
        # anime page (episodes in ascending order, the site's own pager) + its related seasons / works
        page = cItem.get("page", 1)
        baseUrl = self._canonUrl(cItem.get("url", "")).split("?")[0]
        pageTpl = cItem.get("page_tpl", "")
        url = (baseUrl + "?ep_order=asc") if page <= 1 or not pageTpl else pageTpl.format(page=page)
        printDBG("Anime4up.listShow [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        if page <= 1:
            self._addRelatedFolder(cItem, data)
        grid = _section(data, 'id="episodesList"', ('id="related-anime"', "<footer"))
        episodes = [e for e in (self._episodeCard(card) for card in _cards(grid)) if e]
        # ascending, also when the site ignores ep_order
        episodes.sort(key=lambda e: int(e[2]) if e[2].isdigit() else 0)
        show = cItem.get("s_title") or _splitSeason(cItem.get("title", ""))[0]
        base = {"name": "category", "category": "a4_video", "good_for_fav": True, "desc": cItem.get("desc", ""), "show_url": baseUrl,
                "s_title": show, "meta_title": cItem.get("meta_title", show)}
        if cItem.get("meta_type") == "movie" and len(episodes) == 1:
            year = _year(self._infoRow(data, "بداية العرض"))
            href, label, episode, icon = episodes[0]
            withYear = year and IsMediaNamingNormalized()
            self.addVideo(dict(base, url=href, icon=icon or cItem.get("icon", ""), title="%s (%s)" % (show, year) if withYear else cItem.get("title", show),
                               meta_type="movie", meta_year=year))
            return
        season = cItem.get("s_season", 1)
        for href, label, episode, icon in episodes:
            self.addVideo(dict(base, url=href, icon=icon or cItem.get("icon", ""), s_season=season, s_episode=episode, meta_type="tv",
                               title=self._episodeTitle(show, season, episode, label or "%s - %s" % (cItem.get("title", show), episode))))
        count = len(episodes)
        if not count and page <= 1:
            SetIPTVPlayerLastHostError(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="episodes-grid empty"[^>]*>(.*?)</div>')[0]) or _("No stream available"))
        tpl, lastPage = self._pager(grid)
        pageTpl = pageTpl or tpl
        listItem = stripPagerKeys(dict(cItem))
        listItem.update({"page_tpl": pageTpl})
        addPagingItems(self, listItem, page, bool(count) and bool(pageTpl) and lastPage > page, lastPage, pageTpl)

    def _addRelatedFolder(self, cItem, data):
        count = len([c for c in _cards(_section(data, 'id="related-anime"', RELATED_ENDS)) if self._showFromCard(c)])
        if count:
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "a4_related", "good_for_fav": False, "title": "%s (%d)" % (_("Related seasons and works"), count)})
            self.addDir(params)

    def _episodeCard(self, card):
        # (episode page, label, episode number, thumbnail) of an episode card, None without a link
        href = self.cm.ph.getSearchGroups(card, r'<div class="ep_num">\s*<a href="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)"')[0]
        if not href:
            return None
        label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'aria-label="([^"]+)"')[0])
        number = EPISODE_RE.search(self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<div class="ep_num">(.*?)</div>')[0]) or label)
        icon = self.cm.ph.getSearchGroups(card, r'data-image="([^"]+)"')[0]
        return self._canonUrl(href), label, number.group(1) if number else "", self.getFullIconUrl(icon) if icon else ""

    def listRelated(self, cItem):
        sts, data = self.getPage(self._canonUrl(cItem.get("url", "")).split("?")[0])
        if not sts:
            return
        seen = set()
        for card in _cards(_section(data, 'id="related-anime"', RELATED_ENDS)):
            show = self._showFromCard(card)
            if show and show["url"] not in seen:
                seen.add(show["url"])
                self._addShow(show)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("Anime4up.listSearchResult [%s]" % pattern)
        quoted = urllib_quote_plus(pattern)
        cItem = dict(cItem)
        cItem.update({"category": "a4_list", "s_pattern": pattern, "url": self.getFullUrl("/?search_param=animes&s=%s" % quoted),
                      "page_tpl": cItem.get("page_tpl") or self.getFullUrl("/page/{page}/?search_param=animes&s=%s" % quoted)})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _servers(self, data, pageUrl):
        # [(label, hoster url)] of an episode page
        servers = []
        nonce = self.cm.ph.getSearchGroups(data, r"""window\.TxPlayerNonce\s*=\s*['"]([^'"]+)['"]""")[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="episode-servers"', "</ul>", False)[1]
        for attrs, body in re.findall(r"(?s)<li([^>]*)>(.*?)</li>", block):
            label = self.cleanHtmlStr(re.sub(r"(?s)<noscript>.*?</noscript>", "", body)).replace("بدون اعلانات", "").strip()
            label = re.sub(r"\s+", " ", label)
            link = self.cm.ph.getSearchGroups(attrs, r'data-watch="([^"]+)"')[0]
            if not link and nonce:
                # theme AJAX player: data-type / data-i / data-id -> {"embed_url": ...}
                post = {"post": self.cm.ph.getSearchGroups(body + attrs, r'data-id="([^"]+)"')[0], "nume": self.cm.ph.getSearchGroups(body + attrs, r'data-i="([^"]+)"')[0],
                        "type": self.cm.ph.getSearchGroups(body + attrs, r'data-type="([^"]+)"')[0], "_ajax_nonce": nonce}
                params = dict(self.defaultParams, header=dict(self.HEADER, Referer=pageUrl, **{"X-Requested-With": "XMLHttpRequest"}))
                sts, ret = self.getPage(self.getFullUrl("/wp-content/themes/Anime4up/Ajaxt/iframe.php"), params, post)
                if sts:
                    try:
                        link = json_loads(ret).get("embed_url", "")
                    except Exception:
                        printExc()
                link = self.cm.ph.getSearchGroups(link, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0] or link
            link = link.replace("&amp;", "&").strip()
            if link.startswith("//"):
                link = "https:" + link
            if self.cm.isValidUrl(link):
                servers.append((label, link))
                # the page script adds a second Megamax player (share4max.com/e/<id>) after the first one
                megamax = re.match(r"https?://share4max\.com/iframe/([\w-]+)", link)
                if megamax:
                    servers.append(("%s 2" % label, "https://share4max.com/e/%s" % megamax.group(1)))
        return servers

    def getLinksForVideo(self, cItem):
        url = self._canonUrl(cItem.get("url", ""))
        printDBG("Anime4up.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        for label, link in self._servers(data, url):
            if link in seen:
                continue
            seen.add(link)
            if self.up.checkHostSupport(link) != 1:
                printDBG("Anime4up.getLinksForVideo unsupported hoster [%s]" % link)
                continue
            hostName = self.up.getHostName(link)
            urltab.append({"name": "%s - %s" % (hostName, label) if label else hostName, "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Anime4up.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _infoRow(self, data, label):
        return self.cm.ph.getSearchGroups(data, r'(?s)<span>\s*%s\s*:?\s*</span>(.*?)</div>' % label)[0]

    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of an anime page
        info = {}
        for key, label in INFO_KEYS:
            value = self.cleanHtmlStr(self._infoRow(data, label))
            if value:
                info[key] = value
        genres = ", ".join(x for x in (self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>",
                           self.cm.ph.getDataBeetwenMarkers(data, 'class="anime-genres"', "</ul>", False)[1])) if x)
        if genres:
            info["genres"] = genres
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="anime-story">(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="anime-thumbnail">\s*<img src="([^"]+)"')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("Anime4up.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        pageUrl = cItem.get("show_url") or cItem.get("url", "")
        if cItem.get("category") in VIDEO_CATEGORIES and not cItem.get("show_url"):
            # an episode from the latest list: its page links the anime page
            sts, data = self.getPage(pageUrl)
            pageUrl = self.cm.ph.getSearchGroups(data, r'(?s)<div class="anime-page-link">\s*<a href="([^"]+)"')[0] if sts else ""
        if pageUrl:
            sts, data = self.getPage(pageUrl)
            if sts:
                story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or "tv"
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        year = cItem.get("meta_year") or _year(info.get("year", ""))
        meta = {}
        try:
            meta = getMeta(mediaType, title, year, () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((k, v) for k, v in siteInfo.items() if k in ("episodes", "status", "seasons")))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster else "") or meta.get("poster") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Anime4up.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "a4_list":
            self.listItems(self.currItem)
        elif category == "a4_latest":
            self.listLatest(self.currItem)
        elif category == "a4_filter":
            self.listFilter(self.currItem)
        elif category == "a4_show":
            self.listShow(self.currItem)
        elif category == "a4_related":
            self.listRelated(self.currItem)
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
        CHostBase.__init__(self, Anime4up(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("anime4up")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
