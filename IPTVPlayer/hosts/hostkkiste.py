# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 02.06.2026 - MR.X
# 07.10.2026 - host standard
#   kkiste-io.ink (DLE, behind Cloudflare -> getPageCFProtection / MyE2i; the covers get the cf_clearance
#   cookie + the User-Agent that passed the check):
#   - films are VIDEO rows keyed on their page url; a series page is a folder whose episodes get their own key
#     (page url + "#s<season>e<episode>") - before all episodes shared the page url
#   - watched flag (series:/video: keys, the series folder follows its episodes), favourites, downloaded
#     marker, name normalisation "Title (Year)" / "Show - SxxExx", sidecar, INFO via moviemeta + the site's
#     fields, First / Jump / Next page (also for the search)
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import isPlayerUrl
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
    return "https://kkiste-io.ink/"


SEASON_RE = re.compile(r"\s*[-:]?\s*(?:(\d+)\.?\s*Staffel|Staffel\s*(\d+))\b.*$", re.I)


class KKisteAG(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kkiste.ag", "cookie": "kkiste.ag.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = "https://tarnkappe.info/wp-content/uploads/kkiste-logo.jpg"
        self.MAIN_URL = gettytul()
        self.MAIN_CAT_TAB = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/kinofilme-online/")},
                             {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/serienstream-deutsch/")},
                             {"category": "list_items", "title": _("Animation"), "url": self.getFullUrl("/animation/")},
                             {"category": "list_year", "title": _("Year"), "url": self.MAIN_URL},
                             {"category": "list_genres", "title": _("Genres"), "url": self.MAIN_URL}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("kkiste")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        # the posters sit behind the same Cloudflare check as the pages: cf_clearance + the UA that passed it
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.MAIN_URL}
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
        # "Show - Staffel 2" / "Show 2. Staffel" -> ("Show", "2")
        m = SEASON_RE.search(title or "")
        if not m:
            return title, ""
        return title[:m.start()].strip(" -:") or title, m.group(1) or m.group(2)

    def _episodeChunks(self, data):
        # [(episode number, label, html)] of a series page, in page order
        chunks = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<li id="serie', "</ul>"):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '><a href="#">([^<]+)')[0])
            nums = re.findall(r"\d+", label)
            chunks.append((str(int(nums[-1])) if nums else "", label, item))
        numbers = [c[0] for c in chunks]
        if "" in numbers or len(set(numbers)) != len(numbers):
            # labels without (unique) numbers: the position is the episode number
            chunks = [(str(idx + 1), label, item) for idx, (_num, label, item) in enumerate(chunks)]
        return chunks

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("KKisteAG.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = cItem.get("query", "")
        pageUrlTpl = ""
        if query:
            pageUrlTpl = self.getFullUrl("/index.php?do=search&subaction=search&story=%s&search_start={page}" % urllib_quote_plus(query))
            url = pageUrlTpl.format(page=page)
        else:
            url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'next"><a href="([^"]+)')[0]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="short">', "</article>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'href="[^"]+">([^<]+)')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'img src="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'st-desc">([^<]+)')[0])
            year = self.cm.ph.getSearchGroups(item, r">\s*((?:19|20)\d\d)\s*<")[0]
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
            show, season = self._splitSeason(title)
            if season or "taffel" in title or "serie" in title:
                params.update({"category": "list_episodes", "title": title, "s_title": show, "s_season": season or "1",
                               "meta_type": "tv", "meta_title": show, "meta_year": year})
                self.addDir(params)
            else:
                dispTitle = "%s (%s)" % (title, year) if (normalize and year and year not in title) else title
                params.update({"category": "video", "title": dispTitle, "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)

        nextParams = None
        if query:
            # DLE search pager: list_submit(<page>) links
            nums = [int(n) for n in re.findall(r"list_submit\((\d+)\)", data)]
            lastPage = max(nums) if nums else 0
            hasNext = lastPage > page
        else:
            nums = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/?"', data)]
            lastPage = max(nums) if nums else 0
            nextPage = self.getFullUrl(nextPage) if nextPage else ""
            pageHref = self.cm.ph.getSearchGroups(nextPage, r"^(.+/page/)\d+/?$")[0]
            if pageHref:
                pageUrlTpl = pageHref + "{page}/"
            elif nextPage:
                nextParams = {"url": nextPage}
            hasNext = self.cm.isValidUrl(nextPage) or (bool(pageUrlTpl) and lastPage > page)
        if lastPage < page:
            lastPage = 0
        addPagingItems(self, cItem, page, bool(seen) and hasNext, lastPage, pageUrlTpl, nextParams)

    def listEpisodes(self, cItem):
        printDBG("KKisteAG.listEpisodes")
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0]) or cItem.get("desc", "")
        show = cItem.get("s_title") or self._splitSeason(cItem.get("title", ""))[0]
        season = cItem.get("s_season") or "1"
        chunks = self._episodeChunks(data)
        for ep, label, _item in chunks:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, ep))
            else:
                title = "%s - %s" % (cItem.get("title", show), label or "%s %s" % (_("Episode"), ep))
            self.addVideo({"name": "category", "good_for_fav": True, "category": "video", "title": title, "url": "%s#s%se%s" % (url, season, ep),
                           "icon": cItem.get("icon", ""), "desc": desc, "s_title": show, "s_season": season, "s_episode": ep,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if not chunks:
            # no episode list - the page itself is the video
            params = dict(cItem)
            params.update({"category": "video", "url": url, "desc": desc})
            self.addVideo(params)

    def listGenres(self, cItem, t):
        printDBG("KKisteAG.Genres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, ">%s<" % t, "</ul>")
        if not data:
            return
        for url, title in re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data[0]):
            title = self.cleanHtmlStr(title)
            if not title or "kino" in title.lower() or "serie" in title.lower():
                continue
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title.replace(" stream", ""), "url": self.getFullUrl(url)})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KKisteAG.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "query": searchPattern.strip(), "url": "", "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("KKisteAG.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            return []
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0]) or cItem.get("desc", "")
        ep = self.cm.ph.getSearchGroups(url, r"#s\d+e(\d+)$")[0]
        if ep:
            data = "".join(item for num, _label, item in self._episodeChunks(data) if num == ep)
        elif cItem.get("episode"):
            # favourites saved by older versions: the episode label
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["episode"], "</ul>")
            data = data[0] if data else ""
        urltab = []
        seen = set()
        for link in re.findall('data-link="([^"]+)', data):
            link = link.replace("&amp;", "&").strip()
            link = "https:" + link if link.startswith("//") else link
            # devideosrc.co / meinecloud.click player pages resolve through urlparser (parserMEINECLOUD), other player pages don't
            if not self.cm.isValidUrl(link) or link in seen or "player.php" in link or (isPlayerUrl(link) and "/movie/" not in link and "/serial/" not in link):
                continue
            seen.add(link)
            urltab.append({"name": "Trailer" if "youtu" in link else self.up.getHostName(link).capitalize(), "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("KKisteAG.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("KKisteAG.getArticleContent [%s]" % cItem)
        info = {}
        desc = ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'video-box clearfix"><strong>([^"]+)</div>')[0])
            patterns = {"actors": r"Darsteller:(.*?)</div>", "director": r"Regisseur:(.*?)</div>", "year": r"Jahr:(.*?)</div>", "duration": r"Zeit:(.*?)</div>"}
            for key, pattern in patterns.items():
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, pattern)[0])
                if value:
                    info[key] = value
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d\d)")[0] or cItem.get("meta_year", "")
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], year)
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
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_year":
            self.listGenres(self.currItem, "Release Jahre")
        elif category == "list_genres":
            self.listGenres(self.currItem, "Genres")
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
        CHostBase.__init__(self, KKisteAG(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kkiste")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ["video", "list_episodes"]
