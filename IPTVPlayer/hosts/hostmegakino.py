# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 09.05.2026 - Mr.X
# 07.10.2026 - megakino22.com + host standard
#   DLE site: every page needs the yg_token cookie (index.php?yg=token, the site answers with a small
#   script page until it is set) - getPage fetches it on its own, so favourites open without the main menu.
#   - films are VIDEO rows keyed on their page url; a series page (one season) is a folder whose episodes get
#     their own key (page url + "#s<season>e<episode>") - before all episodes shared the page url
#   - watched flag (series:/video: keys, the season folder follows its episodes), favourites, downloaded
#     marker, name normalisation "Title (Year)" / "Show - SxxExx", sidecar, INFO via moviemeta + the site's
#     fields, First / Jump / Next page (last page from the pager, search: "Found N responses")
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://megakino22.com/"


SEASON_RE = re.compile(r"\s*[-:]?\s*(?:(\d+)\.?\s*Staffel|Staffel\s*(\d+))\s*$", re.I)
SEARCH_PAGE_SIZE = 20


class MegaKino(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MegaKino", "cookie": "MegaKino.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("films/")},
                     {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kinofilme/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serials/")},
                     {"category": "list_items", "title": _("Animation"), "url": self.getFullUrl("multfilm/")},
                     {"category": "list_items", "title": _("Documentary"), "url": self.getFullUrl("documentary/")},
                     {"category": "list_value", "title": _("Collections"), "s": ">Sammlung"},
                     {"category": "list_value", "title": _("Genres"), "s": ">Genres"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("megakino")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        url = baseUrl.split("#", 1)[0]
        sts, data = self.cm.getPageCFProtection(url, addParams, post_data)
        if sts and len(data) < 1000 and "yg=token" in data:
            # no (or an expired) yg_token cookie: the site sends a script that fetches it and reloads
            printDBG("MegaKino.getPage: fetching yg_token")
            self.cm.getPageCFProtection(self.MAIN_URL + "index.php?yg=token", dict(addParams), None)
            sts, data = self.cm.getPageCFProtection(url, addParams, post_data)
        return sts, data

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"video": "video", "list_episodes": "series"}.get(cItem.get("category", ""), "")
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _splitSeason(title):
        # "Show - 1 Staffel" / "Show - Staffel 14" -> ("Show", "1")
        m = SEASON_RE.search(title or "")
        if not m:
            return title, ""
        return title[:m.start()].strip(" -:") or title, m.group(1) or m.group(2)

    @staticmethod
    def _year(text):
        years = re.findall(r"\b((?:19|20)\d\d)\b", text or "")
        return years[-1] if years else ""

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("MegaKino.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = cItem.get("query", "")
        if query:
            pageUrlTpl = self.MAIN_URL + "index.php?do=search&subaction=search&story=%s&search_start={page}" % urllib_quote_plus(query)
            url = pageUrlTpl.format(page=page)
        else:
            url = cItem["url"]
            pageUrlTpl = ""
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="poster grid-item', "</a>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'poster__title[^>]*>([^<]+)')[0])
            if not title:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)')[0])
            subs = [self.cleanHtmlStr(s) for s in re.findall(r"(?s)<li>(.*?)</li>", item)]
            year = self._year(subs[0]) if subs else ""
            genres = subs[1] if len(subs) > 1 else ""
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'line-clamp">([^<]+)')[0])
            descLine = " | ".join(x for x in (year, genres) if x)
            if descLine:
                desc = "%s[/br]%s" % (descLine, desc) if desc else descLine
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
            show, season = self._splitSeason(title)
            if "/serials/" in url or genres.startswith("Serien") or season:
                params.update({"category": "list_episodes", "title": title, "s_title": show, "s_season": season or "1",
                               "meta_type": "tv", "meta_title": show, "meta_year": year})
                self.addDir(params)
            else:
                dispTitle = "%s (%s)" % (title, year) if (normalize and year and year not in title) else title
                params.update({"category": "video", "title": dispTitle, "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)

        lastPage = 0
        if query:
            total = self.cm.ph.getSearchGroups(data, r"Found\s+(\d+)\s+responses")[0]
            if total:
                lastPage = (int(total) + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        else:
            pager = self.cm.ph.getDataBeetwenMarkers(data, "pagination__pages", "</div>", False)[1]
            nums = [int(n) for n in re.findall(r">\s*(\d+)\s*<", pager)]
            lastPage = max(nums) if nums else 0
            pageHref = self.cm.ph.getSearchGroups(pager, r'href="([^"]*/page/)\d+/?"')[0]
            if pageHref:
                pageUrlTpl = self.getFullUrl(pageHref) + "{page}/"
        hasNext = bool(seen) and lastPage > page
        addPagingItems(self, cItem, page, hasNext, lastPage, pageUrlTpl)

    def listEpisodes(self, cItem):
        printDBG("MegaKino.listEpisodes")
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description"\s*data-rows="\d+">(.*?)</div>')[0]) or cItem.get("desc", "")
        show = cItem.get("s_title") or self._splitSeason(cItem.get("title", ""))[0]
        season = cItem.get("s_season") or "1"
        select = self.cm.ph.getDataBeetwenMarkers(data, "se-select", "</select>", False)[1]
        found = False
        for ep, label in re.findall(r'<option value="ep(\d+)"[^>]*>([^<]*)<', select):
            found = True
            label = self.cleanHtmlStr(label)
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, ep))
            else:
                title = "%s - %s" % (cItem.get("title", show), label or "%s %s" % (_("Episode"), ep))
            self.addVideo({"name": "category", "good_for_fav": True, "category": "video", "title": title, "url": "%s#s%se%s" % (url, season, ep),
                           "icon": cItem.get("icon", ""), "desc": desc, "s_title": show, "s_season": season, "s_episode": ep,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if not found:
            # the site files some films under a "Staffel" title - the page itself is the video
            params = dict(cItem)
            params.update({"category": "video", "url": url, "desc": desc})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("MegaKino.listValue")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], 'class="side-block__title')
        if not data:
            return
        for url, title in re.compile(r'href="([^"]+)(?:.*?title">|">)([^<]+)', re.DOTALL).findall(data[0]):
            title = self.cleanHtmlStr(title)
            if title:
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MegaKino.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if len(searchPattern.strip()) < 4:
            # the DLE search refuses shorter strings
            SetIPTVPlayerLastHostError(_("Search string must have at least 4 characters."))
            return
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "query": searchPattern.strip(), "url": "", "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MegaKino.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            return []
        # "#s1e3" of the episode url; "episode" ("ep3") of favourites saved by older versions
        ep = self.cm.ph.getSearchGroups(url, r"#s\d+e(\d+)$")[0] or self.cm.ph.getSearchGroups(cItem.get("episode", ""), r"ep(\d+)")[0]
        if ep:
            block = self.cm.ph.getDataBeetwenMarkers(data, 'id="ep%s"' % ep, "</select>", False)[1]
            raw = re.findall(r'value="([^"]+)', block)
        else:
            raw = re.findall(r'(?:film_main"\s*data-src|iframe\s*src)="([^"]+)', data)
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description"\s*data-rows="\d+">(.*?)</div>')[0]) or cItem.get("desc", "")
        urltab = []
        seen = set()
        for link in raw:
            link = link.replace("&amp;", "&").strip()
            link = "https:" + link if link.startswith("//") else link
            if not self.cm.isValidUrl(link) or link in seen or "youtube.com/embed/" in link:
                continue
            seen.add(link)
            urltab.append({"name": self.up.getHostName(link).capitalize(), "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("MegaKino.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MegaKino.getArticleContent [%s]" % cItem)
        info = {}
        desc = ""
        origTitle = ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description"\s*data-rows="\d+">(.*?)</div>')[0])
            origTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="alternativeHeadline">([^<]+)<')[0])
            yearRow = self.cm.ph.getSearchGroups(data, r'(?s)class="pmovie__year">(.*?)</div>')[0]
            fields = {"duration": r"(\d+ min)\s*$", "country": r'itemprop="countryOfOrigin">([^<]+)</span>'}
            for key, pattern in fields.items():
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(yearRow, pattern)[0])
                if value:
                    info[key] = value
            year = self._year(self.cleanHtmlStr(yearRow))
            if year:
                info["year"] = year
            fields = {"director": r'(?s)itemprop="directors">(.*?)</span>', "actors": r'(?s)itemprop="actors">(.*?)</span>', "genres": r'itemprop="genre">([^<]+)</div>'}
            for key, pattern in fields.items():
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, pattern)[0])
                if value:
                    info[key] = value
            if origTitle:
                info["original_title"] = origTitle
        meta = {}
        mediaType = cItem.get("meta_type", "")
        if mediaType:
            try:
                meta = getMeta(mediaType, cItem.get("meta_title", ""), cItem.get("meta_year", ""))
                if not meta and origTitle and origTitle != cItem.get("meta_title", ""):
                    meta = getMeta(mediaType, origTitle, cItem.get("meta_year", ""))
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        plot = meta.get("plot", "")
        text = desc or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = cItem.get("icon", "") or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

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
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, MegaKino(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("megakino")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ["video", "list_episodes"]
