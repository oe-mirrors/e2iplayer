# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - Space Power Fan (spacepowerfan.com, Arabic-dubbed cartoons and anime, WordPress "Kiranime" theme): movies,
#     series, cartoons and search; First page / Jump / Next page over /page/N/ (last page from the page numbers)
#   - Cloudflare challenges every request there (curl-impersonate included, 08.10.2026): pages go through
#     getPageCFProtection (MyE2i solve on the box), covers (wp-content/uploads) get the same cf_clearance
#     cookie and the User-Agent that passed the check
#   - title -> episodes (VIDEO rows keyed on the episode page url, local paging over 100); a movie with one
#     episode is one VIDEO row; links: the episode page's servers (data-embed-id = "<n>:<base64 iframe/url>"),
#     the site's own player pages give their <source> directly, the rest goes to urlparser
#   - watched flag (title -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx", the season taken from "الجزء/الموسم <n>" in the title), sidecar, INFO via moviemeta +
#     the title page's fields
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import b64Decode, printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://spacepowerfan.com/"


LOCAL_PAGE_SIZE = 100
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3),
    ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
# "وان بيس الجزء الثاني مدبلج" / "... الموسم 3"
SEASON_RE = re.compile(r"\s*(?:الجزء|الموسم)\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
# words behind every name of the site: "مدبلج بالعربية" / "اونلاين"
TAIL_RE = re.compile(r"\s+(?:مدبلج(?:ة)?|بالعربية|بالعربي|اونلاين|أونلاين)(?=\s|$)")
VIDEO_CATEGORIES = ("spf_video",)
FOLDER_CATEGORIES = ("spf_show",)


def _cleanName(name):
    return re.sub(r"\s{2,}", " ", TAIL_RE.sub("", name or "")).strip(" -")


def _splitSeason(name):
    # "وان بيس الجزء الثاني" -> ("وان بيس", 2); no season word -> (name, 1)
    match = SEASON_RE.search(name or "")
    if not match:
        return name, 1
    value = match.group(1)
    season = int(value) if value.isdigit() else dict(SEASON_ORDINALS).get(value, 1)
    return (name[:match.start()] + name[match.end():]).strip(" -") or name, season


class SpacePowerFan(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "spacepowerfan", "cookie": "spacepowerfan.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/spacepowerfan135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("spacepowerfan")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self.getFullUrl((baseUrl or "").replace("&amp;", "&")), addParams, post_data)

    def _path(self, url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].rstrip("/").lower()

    def _cfMeta(self):
        # cf_clearance + the User-Agent that passed the check, for downloads outside getPage (covers, own player)
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def _isSite(self, url):
        return self.up.getDomain(url).endswith("spacepowerfan.com")

    def getFullIconUrl(self, url, currUrl=None):
        # the covers (wp-content/uploads) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http") or not self._isSite(url):
            return url
        return strwithmeta(url, self._cfMeta())

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("spf_list",):
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

    def _icon(self, html):
        icon = self.cm.ph.getSearchGroups(html, r"""<img[^>]+src=['"]([^'"]+)['"]""")[0]
        if not icon or icon.startswith("data:"):
            icon = self.cm.ph.getSearchGroups(html, r"""srcset=['"]([^'" ]+)""")[0]
        return self.getFullIconUrl(icon) if icon and not icon.startswith("data:") else ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "spf_list", "title": _("Movies"), "url": self.getFullUrl("/anime-type/movie/")},
            {"category": "spf_list", "title": _("Series"), "url": self.getFullUrl("/anime-type/tv/")},
            {"category": "spf_list", "title": _("Cartoons"), "url": self.getFullUrl("/anime-type/%D9%83%D8%B1%D8%AA%D9%88%D9%86/")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def _addCard(self, card, isMovie):
        url = self.cm.ph.getSearchGroups(card, r'(?s)<h2>\s*<a href="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(card, r'href="(https?://[^"]+/anime/[^"]+)"')[0]
        name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r"(?s)<span data-nt-title[^>]*>(.*?)</span>")[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r"(?s)<span data-en-title[^>]*>(.*?)</span>")[0])
        if not url or not name:
            return False
        enName = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r"(?s)<span data-en-title[^>]*>(.*?)</span>")[0])
        status = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="status_show"[^>]*>\s*<span>(.*?)</span>')[0])
        episodes = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r"(?s)>\s*E\s*(\d+)\s*</span>")[0])
        desc = " | ".join(x for x in (enName, status, "%s: %s" % (_("Episodes"), episodes) if episodes else "") if x)
        show, season = _splitSeason(_cleanName(name))
        # "One Piece Arabic S2" / "Dragon Ball Z Kai arc Ceel AR" -> the name for moviemeta
        metaTitle = re.sub(r"(?i)\s+(?:arabic|ar|arc|S\d+)\b.*$", "", enName).strip() or show
        self.addDir({"name": "category", "category": "spf_show", "good_for_fav": True, "url": url, "title": name, "desc": desc,
                     "icon": self._icon(card), "s_title": show, "s_season": season, "meta_type": "movie" if isMovie else "tv",
                     "meta_title": metaTitle})
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        if "?" in baseUrl:
            base, query = baseUrl.split("?", 1)
            pageTpl = base.rstrip("/") + "/page/{page}/?" + query.replace("{", "{{").replace("}", "}}")
        else:
            pageTpl = baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("SpacePowerFan.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        isMovie = "/anime-type/movie" in baseUrl
        count = 0
        # one card of a list: from "kira-anime" up to the next card
        for card in data.split("kira-anime")[1:]:
            if self._addCard(card, isMovie):
                count += 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, "page-numbers", "</ul>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)/", pager)] + [page])
        addPagingItems(self, dict(cItem, base_url=baseUrl, url=baseUrl), page, bool(count) and lastPage > page, lastPage, pageTpl)

    def listShow(self, cItem):
        printDBG("SpacePowerFan.listShow [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        folderTitle = cItem.get("folder_title") or cItem.get("title", show)
        block = self.cm.ph.getDataBeetwenMarkers(data, "episode-list", "</section>", False)[1] or data
        episodes, seen = [], set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, ("<div", ">", "swiper-slide"), "</a>"):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not href or href in seen:
                continue
            seen.add(href)
            # the card repeats "الحلقة N" (badge + caption) around an icon name: the episode label only
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]) or self.cleanHtmlStr(item)
            number = EPISODE_RE.search(text)
            label = number.group(0) if number else text
            number = number or re.search(r"(\d+)/?$", href)
            episodes.append((int(number.group(1)) if number else len(episodes) + 1, href, label, self._icon(item)))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        episodes.sort(key=lambda e: e[0])
        if cItem.get("meta_type") == "movie" and len(episodes) == 1:
            params = dict(cItem, category="spf_video", url=episodes[0][1], show_url=cItem["url"])
            self.addVideo(params)
            return
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for number, href, label, icon in episodes[start:start + LOCAL_PAGE_SIZE]:
            if IsMediaNamingNormalized():
                title = "%s - %s" % (show, formatSxxExx(season, number))
            else:
                title = "%s - %s" % (folderTitle, label or number)
            self.addVideo({"name": "category", "category": "spf_video", "good_for_fav": True, "url": href, "title": title,
                           "icon": icon or cItem.get("icon", ""), "desc": label, "show_url": cItem["url"], "s_title": show,
                           "s_season": season, "s_episode": str(number), "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, folder_title=folderTitle), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("SpacePowerFan.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        # one result page (no pager there); /search answers a 301 to /search/
        base = self.getFullUrl("/search/?s_keyword=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "spf_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("SpacePowerFan.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        # every server button carries its base64 server name and base64 iframe/url in data-embed-id, separated by a colon
        for embed, label in re.findall(r"""(?s)data-embed-id=['"]([^'"]+)['"][^>]*>(.*?)</span>""", data):
            try:
                server, link = (b64Decode(part) for part in embed.split(":", 1)) if ":" in embed else ("", b64Decode(embed))
            except Exception:
                printExc()
                continue
            if "<iframe" in link:
                link = self.cm.ph.getSearchGroups(link, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0]
            link = link.strip().replace("&#038;", "&").replace("&amp;", "&")
            if link.startswith("//"):
                link = "https:" + link
            # mega.nz (cloud player, no parser) can never play here
            if not self.cm.isValidUrl(link) or link in seen or self.up.getDomain(link).endswith("mega.nz"):
                continue
            seen.add(link)
            name = self.cleanHtmlStr(server) or self.cleanHtmlStr(label) or self.up.getDomain(link)
            urltab.append({"name": name, "url": strwithmeta(link, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("SpacePowerFan.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if self.up.getDomain(videoUrl).endswith("4shared.com"):
            return decorateResolvedLinkItems(self._fourShared(videoUrl), sidecar)
        if not self._isSite(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        # the site's own player: /video-embed-page/?video_url=<mp4 on its video CDN, no Cloudflare check there>
        direct = self.cm.ph.getSearchGroups(videoUrl, r"[?&]video_url=([^&]+)")[0]
        if direct:
            direct = urllib_unquote(direct)
            if self.cm.isValidUrl(direct):
                header = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
                return decorateResolvedLinkItems([{"name": "mp4", "url": strwithmeta(direct, header)}], sidecar)
        # other own player pages: <video><source src="..mp4"></video> on the same Cloudflare domain
        sts, data = self.getPage(videoUrl)
        if not sts:
            return []
        links = []
        for src, label in re.findall(r"""<source[^>]+src=['"]([^'"]+)['"](?:[^>]+(?:label|size)=['"]([^'"]*)['"])?""", data):
            src = self.getFullUrl(src.replace("&amp;", "&"))
            meta = self._cfMeta() if self._isSite(src) else {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
            links.append({"name": label or "mp4", "url": strwithmeta(src, meta)})
        if not links:
            iframe = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0]
            if self.cm.isValidUrl(iframe):
                links = self.up.getVideoLinkExt(strwithmeta(iframe, {"Referer": videoUrl}))
        return decorateResolvedLinkItems(links, sidecar)

    def _fourShared(self, embedUrl):
        # www.4shared.com/web/embed/file/<id> (not in urlparser's hostMap, 08.10.2026): <source src="..preview.mp4">
        # on its own CDN, the link is bound to the client IP
        sts, data = self.cm.getPage(str(embedUrl), {"header": dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        src = self.cm.ph.getSearchGroups(data, r"""<source[^>]+src=['"]([^'"]+)['"]""")[0].replace("&amp;", "&")
        if not self.cm.isValidUrl(src):
            return []
        return [{"name": "4shared", "url": strwithmeta(src, {"Referer": "https://www.4shared.com/", "User-Agent": self.HEADER.get("User-Agent")})}]

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a title page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)data-synopsis[^>]*>(.*?)</div>')[0])
        # <li><span>label:</span> <span>value</span></li> / <li><span>النوع:</span> <a>genre</a>..</li>
        fields = {}
        for label, value in re.findall(r"(?s)<li[^>]*>\s*<span[^>]*>\s*([^<:]+?)\s*:\s*</span>(.*?)</li>", data):
            fields[label.strip()] = value
        info = {}
        for key, label in (("original_title", "English"), ("released", "تم عرضه"), ("duration", "المدة الزمنية"),
                           ("episodes", "الحلقات"), ("rating", "التقييم"), ("status", "الحالة")):
            value = self.cleanHtmlStr(fields.get(label, ""))
            if value:
                info[key] = value
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", fields.get("النوع", ""))]
        if genres:
            info["genres"] = ", ".join(g for g in genres if g)
        year = self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("SpacePowerFan.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("show_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type") or "tv", title, info.get("year", ""), () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        status = info.get("status", "")
        info.update(meta.get("info", {}))
        if status:
            info["status"] = status  # the site's airing status, not moviemeta's
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
        printDBG("SpacePowerFan.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "spf_list":
            self.listItems(self.currItem)
        elif category == "spf_show":
            self.listShow(self.currItem)
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
        CHostBase.__init__(self, SpacePowerFan(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("spacepowerfan")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
