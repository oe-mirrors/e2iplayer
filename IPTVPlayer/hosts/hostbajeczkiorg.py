# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - revival of the back online bajeczki.org (WordPress "videonow" theme, https):
#   latest posts, films (+ genres, A-Z), all cartoons/series grouped by first letter (the site lists
#   1200+ categories on one page), category listings sorted by name (episodes in order), search;
#   First page / Jump / Next page over WordPress ".../page/N/";
#   players are plain <iframe>s in the post (flyf.lat, goodstream.vip, cloud.strp2p.site, ebd.cda.pl)
#   resolved by urlparser;
#   + watched flag / sidecar / name normalisation (SxxExx, "Title (Year)") / moviemeta INFO.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://bajeczki.org/"


# site junk in post titles: language versions, quality, "online"
JUNK_RE = re.compile(r"(?i)(?:\b(?:lektor|napisy|dubbing)(?:\s+pl)?\b|\bpl\s*(?:dub|sub)\b|\b(?:pl)?(?:dub|sub)(?:pl)?\b|\b(?:pl|eng|online|ca\S{1,3} film|hd|full\s*hd|720p|1080p|4k)\b)")
# plain (not u"") literals: page text is a utf-8 byte str on py2, str on py3 - the en dash matches both
DASH = "–"
SEP = r"(?:\s|-|:|,|/|\||" + DASH + ")"
SXE_RE = re.compile(r"^(.*?)" + SEP + r"*\bS(\d{1,2})\s*E(\d{1,3})\b" + SEP + r"*(.*)$", re.I)
SEZON_RE = re.compile(r"^(.*?)" + SEP + r"*\bsezon\s*(\d{1,2})\b" + SEP + r"*odcinek\s*(\d{1,3})\b" + SEP + r"*(.*)$", re.I)
# season marker of a category name: "Rick and Morty S09", "1883 - Sezon 01", "Hawkeye S01 PLDUB"
CAT_SEASON_RE = re.compile(SEP + r"*(?:\bS\d{1,2}\b|\bsezon\s*\d{1,2}\b).*$", re.I)
LEAD_SEP_RE = re.compile("^" + SEP + "+")
TRAIL_SEP_RE = re.compile(SEP + "+$")
MULTI_DASH_RE = re.compile(r"(?:\s+(?:-|" + DASH + r")){2,}\s+")
# a film post carries its year in the title: "[2021 PLDUB]", "(2015)"
YEAR_TAG_RE = re.compile(r"[\[(]\s*((?:19|20)\d{2})\b")
DEFAULT_THUMB = "thumbnail-default."
CATS_PER_PAGE = 100


class BajeczkiOrg(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "bajeczki.org", "cookie": "bajeczki.org.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.HEADER.update({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "pl,en;q=0.8"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/wp-content/uploads/2026/06/logo.png")
        self.allCats = []
        self.postCache = ("", "")

        self.watchedHelper = IPTVWatchedHelper("bajeczkiorg")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            # page 2+ of a category (".../page/N/?orderby=...") is the same folder
            url = re.sub(r"/page/\d+/", "/", str(cItem.get("url", "") or "").split("?", 1)[0].strip())
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category", "") == "list_items" and cItem.get("is_cat"):
                return "cat:%s" % url
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getPostPage(self, url):
        # INFO and the link list read the same post page - fetch it once
        if self.postCache[0] == url:
            return True, self.postCache[1]
        sts, data = self.getPage(url)
        if sts and data:
            self.postCache = (url, data)
        return sts, data

    def getFullIconUrl(self, url, currUrl=None):
        if DEFAULT_THUMB in url:
            return ""
        return CBaseHostClass.getFullIconUrl(self, url, currUrl)

    ###################################################
    # titles
    ###################################################
    def _stripJunk(self, title):
        title = JUNK_RE.sub(" ", title)
        title = re.sub(r"[\[(]\s*[\])]", " ", title)
        title = LEAD_SEP_RE.sub("", title)
        title = TRAIL_SEP_RE.sub("", title)
        title = MULTI_DASH_RE.sub(" - ", title)
        return re.sub(r"\s{2,}", " ", title).strip()

    def _parseMovieTitle(self, raw):
        # "Psi Patrol: Film / Paw Patrol: The Movie [2021 PLDUB]", "Ratter (2015) Lektor PL" -> (title, year, lang)
        m = YEAR_TAG_RE.search(raw)
        year = m.group(1) if m else ""
        low = raw.lower()
        lang = ""
        if "dub" in low:
            lang = _("Polish dubbing")
        elif "lektor" in low:
            lang = _("Polish voice-over")
        elif "plsub" in low or "napisy" in low:
            lang = _("Polish subtitles")
        elif re.search(r"\beng\b", low):
            lang = _("English")
        title = re.sub(r"\[[^\]]*\]", " ", raw)
        title = re.sub(r"\(\s*(?:19|20)\d{2}\s*\)", " ", title)
        title = self._stripJunk(title) or raw
        return title, year, lang

    def _showName(self, catName):
        return self._stripJunk(CAT_SEASON_RE.sub("", catName)) or catName

    def _buildItem(self, url, raw, catName, icon):
        # display title + meta fields of a post row
        params = {"url": url, "icon": icon}
        normalize = IsMediaNamingNormalized()
        sxe = SXE_RE.match(raw) or SEZON_RE.match(raw)
        if not sxe and ("/pelnometrazowe/" in url or YEAR_TAG_RE.search(raw)):
            # films also sit in other categories ("/swiateczne/10-przykazan-2007-pldub/")
            title, year, lang = self._parseMovieTitle(raw)
            metaTitle = title.split(" / ")[-1].strip() if " / " in title else title
            params.update({"meta_type": "movie", "meta_title": metaTitle, "meta_year": year, "lang": lang})
            if normalize:
                raw = "%s (%s)" % (title, year) if year else title
        elif "/zwiastun/" not in url:
            show = self._showName(catName) if catName else ""
            if sxe:
                show = self._stripJunk(sxe.group(1)) or show
                season, episode, epName = sxe.group(2), sxe.group(3), self._stripJunk(sxe.group(4))
                params.update({"season": season, "episode": episode, "ep_name": epName})
                if normalize:
                    raw = "%s - %s" % (show, formatSxxExx(season, episode))
            elif normalize:
                raw = self._stripJunk(raw.replace(DASH, "-"))
            if show:
                params.update({"meta_type": "tv", "meta_title": show, "s_title": show})
        params["title"] = raw
        return params

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        menu = [{"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/?s=")},
                {"category": "list_letters", "title": _("Cartoons and series"), "url": self.getFullUrl("/all-categories/")},
                {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/pelnometrazowe/")},
                {"category": "list_items", "title": "%s (A-Z)" % _("Movies"), "url": self.getFullUrl("/pelnometrazowe/?orderby=name&order=asc")},
                {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("/pelnometrazowe/")}] + self.searchItems()
        self.listsTab(menu, cItem)

    def listGenres(self, cItem):
        printDBG("BajeczkiOrg.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, "Wybierz kategori", "</div>", False)[1]
        for url, title in re.findall(r'<a[^>]+href="([^"]+/pelnometrazowe/[^"/]+/)"[^>]*>([^<]+)</a>', data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            self.addDir(params)

    def _getAllCats(self, url):
        if self.allCats:
            return self.allCats
        sts, data = self.getPage(url)
        if not sts:
            return []
        cats = []
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ("<div", ">", "category-bar"), ("</div", ">"), False):
            catUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "category-name"), ("</span", ">"), False)[1])
            if not catUrl or not title:
                continue
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "category-desc"), ("</span", ">"), False)[1])
            count = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "video-count"), ("</span", ">"), False)[1])
            count = self.cm.ph.getSearchGroups(count, r"(\d+)")[0]
            cats.append({"title": title, "url": catUrl, "desc": desc, "count": count})
        self.allCats = cats
        return cats

    def _letter(self, title):
        # first character (py2: decode the utf-8 byte str, or "Ł" would be split into bytes)
        try:
            isText = isinstance(title, type(u""))
            ch = (title if isText else title.decode("utf-8"))[:1].upper()
            if not ch.isalpha():
                return "#"
            return ch if isText else ch.encode("utf-8")
        except Exception:
            printExc()
        return "#"

    def listLetters(self, cItem):
        printDBG("BajeczkiOrg.listLetters")
        letters = []
        counts = {}
        for cat in self._getAllCats(cItem["url"]):
            letter = self._letter(cat["title"])
            if letter not in counts:
                letters.append(letter)
                counts[letter] = 0
            counts[letter] += 1
        for letter in sorted(letters, key=lambda x: (x != "#", x)):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_cats", "title": "%s (%d)" % (letter, counts[letter]), "letter": letter})
            self.addDir(params)

    def listCats(self, cItem):
        printDBG("BajeczkiOrg.listCats [%s]" % cItem.get("letter"))
        cats = [cat for cat in self._getAllCats(cItem["url"]) if self._letter(cat["title"]) == cItem.get("letter")]
        # a letter can hold a few hundred categories: local paging
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = (len(cats) + CATS_PER_PAGE - 1) // CATS_PER_PAGE
        for cat in cats[(page - 1) * CATS_PER_PAGE:page * CATS_PER_PAGE]:
            desc = cat["desc"]
            if cat["count"]:
                desc = "%s: %s[/br]%s" % (_("Videos"), cat["count"], desc)
            url = cat["url"]
            show = self._showName(cat["title"])
            params = {"name": "category", "good_for_fav": True, "category": "list_items", "is_cat": True, "title": cat["title"],
                      "url": url + ("&" if "?" in url else "?") + "orderby=name&order=asc", "desc": desc, "site_desc": cat["desc"],
                      "cat_name": cat["title"], "meta_type": "tv", "meta_title": show, "s_title": show}
            self.addDir(params)
        if lastPage > 1:
            # the whole list is in memory: the folder url is the (constant) "Jump" template
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "%7B").replace("}", "%7D"))

    def listItems(self, cItem):
        # WordPress paging: <path>/page/N/?<query>
        page = cItem.get("page", 1)
        baseUrl = re.sub(r"/page/\d+/", "/", cItem["url"])
        path, sep, query = baseUrl.partition("?")
        pageUrlTpl = path.rstrip("/") + "/page/{page}/" + sep + query
        url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
        printDBG("BajeczkiOrg.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        pager = " ".join(re.findall(r'<a[^>]+class="(?:next )?page-numbers[^"]*"[^>]*>', data))
        hasNext = 'class="next ' in pager or bool(re.search(r'<link[^>]+rel="next"', data))
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)/", pager)] + [page])

        main = self.cm.ph.getDataBeetwenNodes(data, ("<main", ">"), ("</main", ">"), False)[1] or data
        items = re.split(r'<(?:div|article)[^>]+class="hentry[^"]*"[^>]*>', main)[1:]
        catName = cItem.get("cat_name", "")
        seen = set()
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            raw = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<h2", ">"), ("</h2", ">"), False)[1])
            if not raw:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            cat = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "entry-category"), ("</span", ">"), False)[1])
            length = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "video-length"), ("</span", ">"), False)[1])
            date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "entry-date"), ("</span", ">"), False)[1])
            params = self._buildItem(url, raw, catName or cat, icon)
            desc = [params.pop("ep_name")] if params.get("ep_name") else []
            if params.get("lang"):
                desc.append(params["lang"])
            if length:
                desc.append("%s: %s" % (_("Duration"), length))
            if cat:
                desc.append(cat)
            if date:
                desc.append(date)
            params.update({"name": "category", "good_for_fav": True, "category": "video", "desc": " | ".join(desc)})
            self.addVideo(params)

        listItem = dict(cItem)
        listItem.update({"category": "list_items", "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext and bool(seen), lastPage, pageUrlTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("BajeczkiOrg.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/?s=") + urllib_quote_plus(searchPattern)})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _postContent(self, data):
        data = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "entry-content"), ("<div", ">", "entry-tags"), False)[1]
        data = re.sub(r"<!--[\s\S]*?-->", "", data)
        return data.split("wp-post-navigation", 1)[0]

    def getLinksForVideo(self, cItem):
        printDBG("BajeczkiOrg.getLinksForVideo [%s]" % cItem["url"])
        urlTab = []
        sts, data = self._getPostPage(cItem["url"])
        if not sts:
            return []
        content = self._postContent(data)
        referer = cItem["url"]
        seen = set()
        unsupported = []
        frames = re.findall(r'<iframe[^>]+?(?:data-src|src)="([^"]+)"', content, re.I)
        frames.extend(re.findall(r'<source[^>]+src="([^"]+)"', content, re.I))
        frames.extend(re.findall(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^"\'<\s]+)', content))
        for url in frames:
            url = url.replace("&amp;", "&").replace("&#038;", "&")
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            host = self.up.getHostName(url)
            meta = {"Referer": referer}
            if host.endswith("strp2p.site"):
                # the API wants the embedding site as r= (urlparser parserSBS reads it from the Referer)
                meta["Referer"] = self.MAIN_URL
                name = "Strp2p"
            elif re.search(r"\.(?:mp4|m3u8)(?:\?|$)", url):
                meta["direct_link"] = True
                name = "Direct"
            else:
                name = self.up.getHostName(url, True).capitalize()
                if self.up.checkHostSupport(url) != 1:
                    # no resolver - the row could only fail on play
                    printDBG("BajeczkiOrg: unsupported hoster [%s]" % url)
                    if host not in unsupported:
                        unsupported.append(host)
                    continue
            urlTab.append({"name": name, "url": strwithmeta(url, meta), "need_resolve": 1})

        if not urlTab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                # many older posts lost their player (removed embeds, commented-out dead hosters)
                SetIPTVPlayerLastHostError(_("No player found for this title."))
            return []
        sidecarTxt = self.cleanHtmlStr(content) or cItem.get("desc", "")
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("BajeczkiOrg.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if videoUrl.meta.get("direct_link"):
            return decorateResolvedLinkItems([{"name": "direct", "url": videoUrl}], sidecar)
        if self.cm.isValidUrl(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("BajeczkiOrg.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        text = cItem.get("site_desc", "")
        other = {}
        if cItem.get("type") == "video" and cItem.get("url"):
            sts, data = self._getPostPage(cItem["url"])
            if sts:
                text = self.cleanHtmlStr(self._postContent(data)) or text
                tags = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "entry-tags"), ("</div", ">"), False)[1]
                cats = [self.cleanHtmlStr(t) for t in re.findall(r'rel="category tag">([^<]+)<', tags)]
                cats = [c for c in cats if c and not c.startswith("►")]
                if cats:
                    other["categories"] = ", ".join(cats)
        meta = {}
        if cItem.get("meta_title"):
            try:
                meta = getMeta(cItem.get("meta_type", ""), cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        if meta:
            other.update(meta.get("info", {}))
            plot = meta.get("plot") or ""
            if plot:
                text = plot + ("[/br][/br]" + text if text and text != plot else "")
        if cItem.get("lang"):
            other["language"] = cItem["lang"]
        if cItem.get("season"):
            title = "%s - %s" % (cItem.get("s_title") or title, formatSxxExx(cItem["season"], cItem.get("episode")))
        images = [{"title": "", "url": url} for url in (meta.get("poster"), icon) if url]
        return [{"title": title, "text": text or cItem.get("desc", ""), "images": images[:1], "other_info": other}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("BajeczkiOrg.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_letters":
            self.listLetters(self.currItem)
        elif category == "list_cats":
            self.listCats(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BajeczkiOrg(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("bajeczkiorg")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or bool(cItem.get("is_cat"))
