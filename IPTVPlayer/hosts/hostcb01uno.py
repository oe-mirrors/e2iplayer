# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 05.05.2026 - update to current url - Masta2002
# 08.10.2026 - host standard, domain cb01uno.wiki (cb01uno.watch / .club redirect there; rows of an older domain
#   are moved to the current one):
#   - episodes get their own url (series page + "#s<season>e<episode>") - before every episode had the series url
#     (one downloaded marker for all of them); seasons are the page url + "#s<season>"
#   - seasons / episodes from the spoiler blocks of the page: only episodes with a playable link (Maxstream sits
#     behind uprot.net + a Cloudflare check - skipped), a season that appears twice (ITA / SUB ITA) keeps both
#   - film links named after their section ("Mixdrop" / "Mixdrop [HD]"), the download section is left out;
#     getVideoLinks returned None for a non-stayonline link
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old rows), downloaded
#     marker, "Title (Year)" / "Show - SxxExx" names, sidecar on the links, INFO via moviemeta merged with the
#     site's fields (genre, duration, country, year)
#   - First / Jump / Next page with the last page from the pager, search for films or series, local pages (with
#     Jump) for the long year list, no IndexError on an empty page
#   - default user agent, getPageCFProtection + covers with the cookie / UA of a Cloudflare check
# 09.10.2026 - MaxStream links: uprot.net (Cloudflare check + its own image captcha) is solved in MyE2i's browser
#   mode, its CONTINUE link (a one-time maxstream.video/uprots/... token) goes to urlparser parserMAXSTREAM right
#   away; a series that only has the "TUTTA LA SERIE" MaxStream folder lists the folder's episodes
# 09.10.2026 - box log: the MyE2i cookies go into the uprot jar file (pycurl sent them only once, every
#   request met Cloudflare again); a MaxStream folder of a whole series is paged (100 a page) and
#   "Show.01x01..." file names count as S01E01 too
import base64
import os
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remember_user_agent, remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetCookieDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://cb01uno.wiki/"


STAYONLINE_URL = "https://stayonline.pro/"
LOCAL_PAGE_SIZE = 50
FOLDER_PAGE_SIZE = 100
# MaxStream links go through the uprot.net link protector (msf = film, mse = episode, msfi = folder entry,
# msfld = folder of a whole series)
UPROT_RE = re.compile(r"^https?://(?:www\.)?uprot\.net/", re.I)
# the CONTINUE button of an unlocked uprot page; a hidden decoy link without a button sits next to it
UPROT_CONTINUE_RE = re.compile(r'<a href="(https?://maxstream\.[a-z]+/uprots/[^"]+)"\s*>\s*<button', re.I)
# "TUTTA LA SERIE - <a href=...msfld...>" on a series page
UPROT_FOLDER_RE = re.compile(r'TUTT[EA] L[EA] \w+\s+(?:&#8211;|–|-)\s+<a href="?(https?://(?:www\.)?uprot\.net/msfld/[^" >]+)', re.I)
# alternations, no character classes: in Python 2 "–" / "×" are several bytes
SERIES_SUFFIX_RE = re.compile(r"\s+(?:–|-)\s+(?:\d+\s*(?:×|x)\s*\d+|stagion|completa|serie|miniserie|ita\b|sub).*$", re.I)
EPISODE_RE = re.compile(r"^\s*(\d+)\s*(?:×|x)\s*(\d+)((?:\s*[/-]\s*\d+)*)", re.I)


class Cb01(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Cb01", "cookie": "Cb01.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/2026/01/logo-official-uno-2026.png")
        self.MENU = [{"category": "movies", "title": _("Movies")}, {"category": "series", "title": _("Series")}] + self.searchItems()
        self.MOVIES = [{"category": "list_items", "title": _("Movies"), "url": self.MAIN_URL},
                       {"category": "list_genres", "title": _("Genres"), "url": self.MAIN_URL},
                       {"category": "list_year", "title": _("Year"), "url": self.MAIN_URL}]
        self.SERIES = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serietv/")},
                       {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("serietv/")},
                       {"category": "list_year", "title": _("Year"), "url": self.getFullUrl("serietv/")}]
        self.watchedHelper = IPTVWatchedHelper("cb01uno")
        self.wfInitFolderCache()
        # uprot.net's own jar: cf_clearance + the short session of a solved image captcha
        self.UPROT_COOKIE = GetCookieDir("cb01uno_uprot.cookie")

    def _fixDomain(self, url):
        # rows (favourites) of an older cb01 domain -> the current one
        return re.sub(r"^https?://(?:www\.)?cb01[^/]*/", self.MAIN_URL, url or "")

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(self._fixDomain(baseUrl.split("#", 1)[0]), addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        # the covers sit behind the same Cloudflare check as the pages: cf_clearance + the UA that passed it
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video":
                prefix = "video"
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            season, episode = self._season(cItem), str(cItem.get("episode", "") or "")
            episode = str(int(episode)) if episode.isdigit() else episode
            if "#" not in url:
                # season / episode rows from before 08.10.2026 carried the plain series url
                if prefix == "season" and season:
                    url = "%s#s%s" % (url, season)
                elif prefix == "video" and season and episode:
                    url = "%s#s%se%s" % (url, season, episode)
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _season(cItem):
        # "season" since 08.10.2026, "seasons" in older favourites
        return str(cItem.get("season", "") or cItem.get("seasons", "") or "").strip()

    @staticmethod
    def _pageUrlTpl(url):
        # WordPress paging: <list>/page/<n>/[?s=...]
        base, sep, query = url.partition("?")
        base = re.sub(r"page/\d+/?$", "", base)
        if not base.endswith("/"):
            base += "/"
        return (base + "page/{page}/" + sep + query.replace("{", "{{").replace("}", "}}"))

    @staticmethod
    def _splitFilmTitle(title):
        # "Beast [HD] (2026)" -> ("Beast", "2026")
        year = re.search(r"\(((?:19|20)\d\d)\)\s*$", title)
        name = re.sub(r"\s*\[[^\]]*\]", "", title)
        name = re.sub(r"\s*\((?:19|20)\d\d\)\s*$", "", name).strip()
        return name or title, year.group(1) if year else ""

    @staticmethod
    def _seriesName(title):
        # "American Horror Story - 13x04/05 - ITA" -> "American Horror Story"
        return SERIES_SUFFIX_RE.sub("", title).strip() or title

    def _seasonBlocks(self, data):
        # [(season id, season number, head text, [(episode, label, [(url, name)])])] of a series page
        blocks, used = [], {}
        for head, body in re.findall(r'class="sp-head[^"]*"[^>]*>(.*?)</div>\s*<div class="sp-body[^"]*">(.*?)<div class="spdiv">', data, re.DOTALL):
            head = self.cleanHtmlStr(head)
            num = self.cm.ph.getSearchGroups(head, r"STAGION[EI]\s+(\d+)", ignoreCase=True)[0]
            if not num:
                continue
            episodes = []
            for line in re.split(r"<p[^>]*>|<br\s*/?>", body):
                text = self.cleanHtmlStr(line.split("<a ", 1)[0])
                m = EPISODE_RE.match(text)
                if not m:
                    continue
                links = [(url, self.cleanHtmlStr(name)) for url, name in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', line, re.DOTALL)]
                if links:
                    episodes.append((str(int(m.group(2))), self.cleanHtmlStr(m.group(0)), links))
            if not episodes:
                continue
            used[num] = used.get(num, 0) + 1
            # the same season twice (ITA / SUB ITA): the second one gets its own id
            sid = num if used[num] == 1 else "%s-%d" % (num, used[num])
            blocks.append((sid, num, head, episodes))
        return blocks

    def _siteInfo(self, data):
        # the fields of a film / series page: (info dict, plot, year)
        info = {}
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        m = re.match(r"^(.+?)\s+-\s+DURATA\s+(\d+)\S*\s+-\s+(.+?)(?:\s+-\s+(\d{4}))?\s+(.*)$", desc)
        plot = desc
        if m:
            info["genres"] = m.group(1).title()
            info["duration"] = "%s min" % m.group(2)
            info["country"] = m.group(3).title()
            plot = m.group(5)
        # "... +Info » Streaming: Maxstream Mixdrop Download: ..." - the link list of the page follows the plot
        plot = plot.split("+Info", 1)[0].strip()
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>(.*?)</h1>")[0])
        year = self.cm.ph.getSearchGroups(title, r"\(((?:19|20)\d\d)\)")[0] or \
            self.cm.ph.getSearchGroups(data, r'/category/(?:anno-)?((?:19|20)\d\d)/"\s+rel="category')[0]
        if year:
            info["year"] = year
        return info, plot, year

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("cb01uno.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        url = self._fixDomain(cItem["url"])
        pageUrlTpl = self._pageUrlTpl(url)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="card-image">', 'class="card-action'):
            itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            if not itemUrl or not title:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<strong[^>]*>(.*?)</strong>")[0])
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"</strong>\s*<br\s*/?>(.*?)</a>")[0])
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "url": itemUrl, "icon": icon, "desc": "\n".join(x for x in (desc, plot) if x)})
            if "/serietv/" in itemUrl:
                name = self._seriesName(title)
                # the card names the latest episode ("Show - 13x04/05 - ITA") - normalised: the show only
                params.update({"category": "list_seasons", "title": name if normalize else title, "s_title": name, "meta_type": "tv"})
                self.addDir(params)
            else:
                name, year = self._splitFilmTitle(title)
                if normalize:
                    title = "%s (%s)" % (name, year) if year else name
                params.update({"category": "video", "title": title, "s_title": name, "s_year": year, "meta_type": "movie"})
                self.addVideo(params)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</ul>", False)[1]
        pages = [int(n) for n in re.findall(r"/page/(\d+)/", pager)]
        hasNext = page + 1 in pages or 'rel="next"' in data
        addPagingItems(self, cItem, page, hasNext, max(pages + [page]) if hasNext else page, pageUrlTpl)

    def listSeasons(self, cItem):
        printDBG("cb01uno.listSeasons |%s|" % cItem)
        url = self._fixDomain(cItem["url"].split("#", 1)[0])
        sts, data = self.getPage(url)
        if not sts:
            return
        blocks = self._seasonBlocks(data)
        if not blocks:
            folderUrl = UPROT_FOLDER_RE.search(data)
            if folderUrl:
                # only the MaxStream folder of the whole series (e.g. Vampirina)
                _info, plot, _year = self._siteInfo(data)
                self.listUprotFolder(dict(cItem, folder_url=folderUrl.group(1), s_plot=plot))
                return
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        _info, plot, year = self._siteInfo(data)
        sTitle = cItem.get("s_title", "") or self._seriesName(cItem["title"])
        fields = {"s_title": sTitle, "s_year": year, "desc": plot, "s_plot": plot, "meta_type": "tv"}
        if len(blocks) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=blocks[0][0], url="%s#s%s" % (url, blocks[0][0]), **fields), blocks)
            return
        normalize = IsMediaNamingNormalized()
        for sid, num, head, episodes in blocks:
            seasonTag = formatSxxExx(num) if normalize else "%s %s" % (_("Season"), num)
            if sid != num or "SUB" in head.upper():
                seasonTag = "%s [%s]" % (seasonTag, head.split("-", 1)[-1].strip() if "-" in head else head)
            params = dict(cItem)
            params.pop("seasons", None)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": sid, "url": "%s#s%s" % (url, sid)})
            params.update(fields)
            params["desc"] = "%s\n%s: %d\n%s" % (head, _("Episodes"), len(episodes), plot)
            self.addDir(params)

    def listEpisodes(self, cItem, blocks=None):
        printDBG("cb01uno.listEpisodes |%s|" % cItem)
        url = self._fixDomain(cItem["url"].split("#", 1)[0])
        if blocks is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            blocks = self._seasonBlocks(data)
            if not cItem.get("s_title"):
                # an old favourite: the show name from the page
                cItem = dict(cItem, s_title=self._seriesName(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>(.*?)</h1>")[0])))
        sid = self._season(cItem)
        block = [b for b in blocks if b[0] == sid]
        if not block:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sid, num, head, episodes = block[0]
        sTitle = cItem.get("s_title", "") or self._seriesName(cItem["title"])
        lang = " [SUB ITA]" if "SUB" in head.upper() else ""
        normalize = IsMediaNamingNormalized()
        for episode, label, links in episodes:
            if normalize:
                title = "%s - %s%s" % (sTitle, formatSxxExx(num, episode), lang)
            else:
                title = "%s - %s%s" % (sTitle, label, lang)
            params = stripPagerKeys(dict(cItem))
            params.pop("seasons", None)
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%s" % (url, sid, episode),
                           "season": sid, "episode": episode, "meta_type": "tv",
                           # the plot, not the season row's desc (head + episode count + plot)
                           "desc": "%s - %s\n%s" % (head, label, cItem.get("s_plot", cItem.get("desc", "")))})
            self.addVideo(params)

    def listUprotFolder(self, cItem):
        # uprot.net/msfld/<id>: one row per file ("Show.S01E01.ITA.WEB.avi") with a msfi/<id> "Watch" link
        printDBG("cb01uno.listUprotFolder |%s|" % cItem)
        sts, data = self._uprotPage(cItem["folder_url"])
        if not sts:
            return
        url = self._fixDomain(cItem["url"].split("#", 1)[0])
        sTitle = cItem.get("s_title", "") or self._seriesName(cItem["title"])
        normalize = IsMediaNamingNormalized()
        rows = re.findall(r"<tr><td>\s*([^<]+?)\s*<td>.*?<a[^>]+href='(https?://(?:www\.)?uprot\.net/msfi/[^']+)'", data, re.DOTALL)
        if not rows:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        # a whole series is one folder (South Park: 335 files) - local pages
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = max(1, (len(rows) + FOLDER_PAGE_SIZE - 1) // FOLDER_PAGE_SIZE)
        page = min(page, lastPage)
        first = (page - 1) * FOLDER_PAGE_SIZE
        for idx, (name, link) in enumerate(rows[first:first + FOLDER_PAGE_SIZE], first):
            # "Show.S01E01.ITA.WEB.avi" or "South.Park.01x01.Cartman....mkv"
            sxe = re.search(r"[Ss](\d{1,2})[Ee](\d{1,3})|(?<![\dx])(\d{1,2})x(\d{1,3})(?!\d)", name)
            if sxe:
                season, episode = str(int(sxe.group(1) or sxe.group(3))), str(int(sxe.group(2) or sxe.group(4)))
                key = "#s%se%s" % (season, episode)
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode)) if normalize else name
            else:
                season, episode, key, title = "", "", "#f%d" % idx, name
            params = stripPagerKeys(dict(cItem))
            params.pop("seasons", None)
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": url + key,
                           "season": season, "episode": episode, "meta_type": "tv", "uprot_url": link,
                           "desc": "%s\n%s" % (name, cItem.get("s_plot", ""))})
            self.addVideo(params)
        if lastPage > 1:
            # local pages of one folder: the template (the series url itself) only enables "Jump"
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    def listValue(self, cItem, marker):
        printDBG("cb01uno.listValue |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, marker, "</li></ul>", False)[1]
        values = []
        for url, title in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', data):
            title = self.cleanHtmlStr(title)
            if title and (url, title) not in values:
                values.append((url, title))
        lastPage = max(1, (len(values) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        for url, title in values[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)
        if lastPage > 1:
            # local pages of one site page: the template (the page url itself) only enables "Jump"
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("cb01uno.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        base = self.getFullUrl("serietv/") if searchType == "series" else self.MAIN_URL
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": "%s?s=%s" % (base, urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _filmLinks(self, data):
        # [(url, name)] of the streaming sections of a film page ("Streaming:", "Streaming HD:") up to the first
        # download section ("Download:", older pages "Download HD (SUB-ITA):"); the section labels are <u> or, on
        # older pages, <strong> (box log 09.10.2026: "Batman: The Killing Joke (2016)" had no links)
        links, section = [], ""
        start = data.find('<table class="cbtable"')
        if start < 0:
            return links
        for label, url, name in re.findall(r'<(?:u|strong)>(.*?)</(?:u|strong)>|<a href="([^"]+)"[^>]*>([^<]+)</a>', data[start:]):
            if label:
                section = self.cleanHtmlStr(label)
                if section.upper().startswith("DOWNLOAD"):
                    break
                continue
            name = self.cleanHtmlStr(name)
            # the site's own links (cb01.channel, its download pages) are no hosters
            if not self.cm.isValidUrl(url) or "cb01" in url.split("/", 3)[2]:
                continue
            links.append((url, "%s [HD]" % name if "HD" in section.upper() else name))
        return links

    def getLinksForVideo(self, cItem):
        printDBG("cb01uno.getLinksForVideo [%s]" % cItem)
        if cItem.get("uprot_url"):
            # an episode of a MaxStream folder (listUprotFolder)
            urltab = [{"name": "MaxStream", "url": strwithmeta(cItem["uprot_url"], {"Referer": cItem.get("folder_url", self.MAIN_URL)}), "need_resolve": 1}]
            return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        season, episode = self._season(cItem), str(cItem.get("episode", "") or "")
        links = []
        if season and episode:
            # "02" in rows from before 08.10.2026
            episode = str(int(episode)) if episode.isdigit() else episode
            for sid, _num, _head, episodes in self._seasonBlocks(data):
                if sid == season:
                    links = [ep[2] for ep in episodes if ep[0] == episode]
                    links = links[0] if links else []
                    break
        else:
            links = self._filmLinks(data)
        urltab = []
        for url, name in links:
            if url.startswith("/"):
                url = self.getFullUrl(url)
            urltab.append({"name": name.capitalize() if name.islower() or name.isupper() else name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("cb01uno.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = str(videoUrl)
        if url.startswith(STAYONLINE_URL):
            # stayonline.pro/l/<id>/ -> ajax/linkView.php answers {"data": {"value": "<hoster url>"}}
            linkId = self.cm.ph.getSearchGroups(url, r"/l/([^/?#]+)")[0]
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": url})
            sts, data = self.cm.getPage(STAYONLINE_URL + "ajax/linkView.php", params, {"id": linkId, "ref": ""})
            url = ""
            if sts:
                try:
                    url = (json_loads(data).get("data") or {}).get("value", "")
                except Exception:
                    printExc()
        if UPROT_RE.match(url):
            # the CONTINUE link is a one-time token: it goes to urlparser (parserMAXSTREAM) right away
            sts, data = self._uprotPage(url, str(videoUrl.meta.get("Referer", "")) if isinstance(videoUrl, strwithmeta) else "")
            link = UPROT_CONTINUE_RE.search(data) if sts else None
            if not link:
                if sts:
                    SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
            url = strwithmeta(link.group(1), {"Referer": str(videoUrl).split("?", 1)[0]})
        if not self.cm.isValidUrl(url):
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)

    def _writeUprotJar(self, cookies):
        # the browser's cookies (MyE2i: [{"name", "value", "domain", "path", "secure", "expirationDate"}, ...]) as the
        # Netscape cookie file pycurl and urllib read; replaces the old jar
        lines = ["# Netscape HTTP Cookie File"]
        for c in cookies:
            if not isinstance(c, dict) or not c.get("name"):
                continue
            domain = c.get("domain") or "uprot.net"
            try:
                expires = int(c.get("expirationDate") or 0) or int(time.time()) + 86400
            except (TypeError, ValueError):
                expires = int(time.time()) + 86400
            lines.append("\t".join((domain, "TRUE" if domain.startswith(".") else "FALSE", c.get("path") or "/",
                                    "TRUE" if c.get("secure") else "FALSE", str(expires), c["name"], c.get("value", ""))))
        try:
            with open(self.UPROT_COOKIE, "w") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            printExc()

    @staticmethod
    def _myE2iCookies(url):
        # MyE2i's browser mode (every cookie of the site) like libs/recaptcha_mye2i, with its own window title: the
        # CONTINUE link behind the solved captcha is good for one visit - followed in the browser, it is gone for
        # the box
        from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
        from Plugins.Extensions.IPTVPlayer.components.recaptcha_mye2i_widget import UnCaptchaReCaptchaMyE2iWidget
        title = _("MyE2i captcha: solve it, then Job (no CONTINUE)")
        retArg = MainSessionWrapper().waitForFinishOpen(UnCaptchaReCaptchaMyE2iWidget, title=title, sitekey=time.time(), referer=url, captchaType="COOKIES")
        return retArg[0] if retArg else ""

    def _uprotPage(self, url, referer=""):
        # uprot.net shows a Cloudflare check and then its own image captcha ("Select all images with ..."); MyE2i's
        # browser mode solves both and hands over every cookie of the site (the solved captcha holds a few minutes)
        header = dict(self.HEADER, Referer=referer or self.MAIN_URL)
        userAgent = remembered_user_agent(self.UPROT_COOKIE)
        if userAgent:
            header["User-Agent"] = userAgent
        params = {"header": header, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.UPROT_COOKIE}
        for attempt in (1, 2):
            sts, data = self.cm.getPage(url, params)
            if sts and "upcaptcha-form" not in data:
                return True, data
            if attempt == 2:
                break
            token = self._myE2iCookies(url)
            if not token:
                break
            try:
                result = json_loads(base64.b64decode(token))
            except Exception:
                printExc()
                break
            # the jar holds the unsolved PHPSESSID uprot set on the first request - sent together with the browser's
            # solved one, uprot keeps the first and shows the captcha again: only the browser's cookies from here
            # into the jar file (box log 09.10.2026: as cookie_items pycurl only sent them once, every further uprot
            # request met the Cloudflare check again and opened MyE2i once more)
            self._writeUprotJar(result.get("cookie", []))
            if result.get("user_agent"):
                header["User-Agent"] = result["user_agent"]
                remember_user_agent(self.UPROT_COOKIE, result["user_agent"])
            # MyE2i 1.19 sends the button links of the solved page: a solved captcha opens the CONTINUE link only
            # once (box log 09.10.2026: the box asking again met the captcha), so it is taken from the browser -
            # only when the browser solved this very link (a reused tab may still show the previous job's page)
            if result.get("url", "").split("#", 1)[0].rstrip("/") == url.split("#", 1)[0].rstrip("/"):
                for link in result.get("links") or []:
                    if UPROT_CONTINUE_RE.search('<a href="%s"><button' % link):
                        return True, '<a href="%s"><button' % link
        SetIPTVPlayerLastHostError(_("MaxStream (uprot.net) asks for its image captcha: solve it in MyE2i, then open the video again."))
        return False, ""

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("cb01uno.getArticleContent [%s]" % cItem)
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("tv" if "/serietv/" in cItem.get("url", "") else "movie")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot not in text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listValue(self.currItem, "Genere")
        elif category == "list_year":
            self.listValue(self.currItem, " Anno")
        elif category == "movies":
            self.listsTab(self.MOVIES, self.currItem)
        elif category == "series":
            self.listsTab(self.SERIES, self.currItem)
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
        CHostBase.__init__(self, Cb01(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cb01uno")

    def getSearchTypes(self):
        return [(_("Movies"), "movies"), (_("Series"), "series")]

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
