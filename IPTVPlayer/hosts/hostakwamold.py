# -*- coding: utf-8 -*-
# Last Modified: 06.10.2026
# 06.10.2026 - the Akwam archive (the site's old design, now under akwam.ss/old/)
#   - menu: movies / series / other sections read live from the category bar, anime, search;
#     a category lists its sub-categories first ("All" + each), otherwise its titles directly;
#     First page / Jump / Next page (/page/N, last page from the pager) for categories and search
#   - movies, documentaries and plays are VIDEO rows on their page (each file of the page = one
#     link, the YouTube trailer last); every other page (series seasons, shows, wrestling, albums)
#     is a folder: trailer + one VIDEO/AUDIO row per file, oldest episode first
#   - files: GET of /old/download/<hash>/<name> opens a session, its XHR POST answers the signed
#     downet.net link (valid ~2 days) - resolved in getVideoLinks, so rows and favourites keep the
#     stable download url
#   - watched flag (page:<id> / file:<hash>), downloaded flag (canonical page / download url),
#     name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the
#     page's own story/poster/fields (Arabic-only titles: TMDb / TVmaze only), favourites
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, parseSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://akwam.ss/old/"


# Enigma2 colour codes ("\c00RRGGBB") - only for the list description, never in sidecar / INFO text
COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


# Arabic ordinals used in season labels ("الموسم الثالث"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:الموسم|الجزء|ج)\s*(\d+|%s)\s*$" % "|".join(o[0] for o in SEASON_ORDINALS))
# leading words of a title that make it a single film / play (one page = one work)
MOVIE_RE = re.compile(r"^(?:الفيلم الوثائقي|فيلم|الفيلم|مسرحية)\s")
META_MOVIE_RE = re.compile(r"^(?:فيلم|الفيلم)\s")
META_TV_RE = re.compile(r"^مسلسل\s")
# site words that do not belong into a title / file name
JUNK_RE = re.compile(r"(?:^|\s)(?:الفيلم الوثائقي|الفيلم|فيلم|مسلسل|مسرحية|مترجم|مترجمة|اون لاين|أون لاين|مشاهدة|كامل|كاملة|بجودة عالية)(?=\s|$)")
# dubbed and subtitled versions are separate pages with the same name - the dub mark stays in the title
DUB_RE = re.compile(r"(?:^|\s)مدبلجة?(?:\s+(?:للعربية|بالعربية|عربي))?(?=\s|$)")
DUB_WORD = "مدبلج"
YEAR_RE = re.compile(r"\s\(?((?:19|20)\d\d)\)?$")
# sections of the category bar that hold nothing playable
EXCLUDED_SECTIONS = ("البرامج", "الألعاب", "الاجهزة اللوحية", "الكتب و الابحاث", "الصور و الخلفيات")
ANIME_SECTION = "الانمي"
MOVIES_WORD = "فلام"
SERIES_WORD = "مسلسلات"
VIDEO_EXT = ("mkv", "mp4", "avi", "wmv", "flv", "mov", "m4v", "ts", "mpg", "mpeg", "rmvb", "3gp", "webm", "vob")
AUDIO_EXT = ("mp3", "m4a", "aac", "ogg", "wav", "wma", "flac")


class AkwamOld(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "page_url", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")
    FILES_PER_PAGE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "akwamold", "cookie": "akwamold.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.MAIN_URL + "scripts/site/img/main_logo.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "ako_section", "title": _("Movies"), "section": "movies"},
            {"category": "ako_section", "title": _("Series"), "section": "series"},
            {"category": "ako_cat", "title": _("Anime"), "url": self.MAIN_URL + "cat/83/" + urllib_quote(ANIME_SECTION)},
            {"category": "ako_section", "title": _("Other"), "section": "other"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("akwamold")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # the site links its pages with raw Arabic slugs - one ASCII form for requests,
        # the downloaded marker and favourites
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _pageId(url):
        m = re.search(r"/old/(\d+)(?:/|$)", url or "")
        return m.group(1) if m else ""

    def _pageUrl(self, url):
        # "https://akwam.ss/old/184415/<slug>" -> "https://akwam.ss/old/184415/": the slug is optional
        pid = self._pageId(url)
        return "%s%s/" % (self.MAIN_URL, pid) if pid else self._canonUrl(url)

    @staticmethod
    def _fileHash(url):
        m = re.search(r"/download/([0-9a-f]+)/", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", text or "")
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _splitDub(self, title):
        title = self._clean(title)
        dub = bool(DUB_RE.search(title))
        return re.sub(r"\s+", " ", DUB_RE.sub(" ", title)).strip(" -:|"), dub

    def _splitYear(self, title):
        # "فيلم Pokemon Mewtwo Strikes Back Evolution 2019 مدبلج للعربية" -> ("Pokemon Mewtwo Strikes Back Evolution", "2019", True)
        title, dub = self._splitDub(title)
        m = YEAR_RE.search(title)
        if m:
            return title[:m.start()].strip(" -:|"), m.group(1), dub
        return title, "", dub

    def _splitSeason(self, title):
        # "مسلسل S.W.A.T الموسم الثالث مترجم" -> ("S.W.A.T", 3, False); no season label -> season 1
        title, dub = self._splitDub(title)
        season = 1
        m = SEASON_RE.search(title)
        if m:
            val = m.group(1)
            season = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 1)
            title = title[:m.start()].strip()
        return title, season, dub

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ako_video", "ako_page", "ako_file"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category in ("ako_video", "ako_page"):
                pid = self._pageId(cItem.get("url", ""))
                return ("page:%s" % pid) if pid else ""
            if category == "ako_file":
                fid = self._fileHash(cItem.get("url", ""))
                return ("file:%s" % fid) if fid else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listSection(self, cItem):
        printDBG("AkwamOld.listSection [%s]" % cItem.get("section", ""))
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        bar = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="partions"', "</ul>", False)[1]
        section = cItem.get("section", "")
        for url, title in re.findall(r'data-title="[^"]*"\s*href="([^"]+/cat/\d+/[^"]*)">([^<]+)<', bar):
            title = self.cleanHtmlStr(title)
            if title in EXCLUDED_SECTIONS or title == ANIME_SECTION:
                continue
            if MOVIES_WORD in title:
                kind = "movies"
            elif SERIES_WORD in title:
                kind = "series"
            else:
                kind = "other"
            if kind == section:
                self.addDir({"name": "category", "good_for_fav": True, "category": "ako_cat", "title": title, "url": self._canonUrl(url)})

    def listCategory(self, cItem):
        # sub-categories first ("All" + each); a category without any lists its titles directly
        printDBG("AkwamOld.listCategory [%s]" % cItem.get("url", ""))
        url = self._canonUrl(cItem["url"])
        sts, data = self.getPage(url)
        if not sts:
            return
        block = self.cm.ph.getSearchGroups(data, r"(?s)الأقسام الفرعية</span>(.*?)</ul>")[0]
        subs = re.findall(r'<a href="([^"]+/cat/\d+/[^"]*)">([^<]+)<', block)
        if not subs:
            self.listItems(dict(cItem, category="list_items", url=url), data)
            return
        params = stripPagerKeys(dict(cItem))
        params.update({"good_for_fav": True, "category": "list_items", "title": "%s - %s" % (_("All"), cItem.get("title", "")), "url": url})
        self.addDir(params)
        for subUrl, title in subs:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self._canonUrl(subUrl)})

    def _parseItems(self, data):
        # category pages: "subject_box" cards; search pages: "tags_box" cards
        items = []
        for block in data.split('class="subject_box shape"')[1:]:
            items.append((self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0],
                          self.cm.ph.getSearchGroups(block, r'<img src="([^"]+)"')[0],
                          self.cm.ph.getSearchGroups(block, r"(?s)<h3>(.*?)</h3>")[0],
                          self.cm.ph.getSearchGroups(block, r'(?s)<span class="desc">(.*?)</span>')[0]))
        for block in data.split('<div class="tags_box">')[1:]:
            items.append((self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0],
                          self.cm.ph.getSearchGroups(block, r"url\(([^)]+)\)")[0].strip("'\""),
                          self.cm.ph.getSearchGroups(block, r"(?s)<h1>(.*?)</h1>")[0], ""))
        return items

    def listItems(self, cItem, data=None):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem.get("base_url") or re.sub(r"/page/\d+/?$", "", self._canonUrl(cItem["url"]).rstrip("/"))
        pageUrlTpl = baseUrl + "/page/{page}"
        if data is None:
            url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
            printDBG("AkwamOld.listItems [%s]" % url)
            sts, data = self.getPage(url)
            if not sts:
                return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for url, icon, title, info in self._parseItems(data):
            pageUrl = self._pageUrl(url)
            pid = self._pageId(pageUrl)
            title = self.cleanHtmlStr(title)
            if not pid or pid in seen or not title:
                continue
            seen.add(pid)
            info = self.cleanHtmlStr(info)
            params = {"name": "category", "good_for_fav": True, "url": pageUrl, "icon": self._canonUrl(icon) if icon else "",
                      "desc": ("%s%s:%s %s" % (E2ColoR("cyan"), _("Info"), E2ColoR("white"), info)) if info else ""}
            if MOVIE_RE.search(title):
                name, year, dub = self._splitYear(title)
                if normalize:
                    dispTitle = ("%s (%s)" % (name, year)) if year else name
                    if dub:
                        dispTitle = "%s %s" % (dispTitle, DUB_WORD)
                else:
                    dispTitle = title
                params.update({"category": "ako_video", "title": dispTitle})
                if META_MOVIE_RE.search(title) and name:
                    params.update({"meta_type": "movie", "meta_title": name, "meta_year": year})
                self.addVideo(params)
                continue
            show, season, dub = self._splitSeason(title)
            params.update({"category": "ako_page", "title": title, "s_title": ("%s %s" % (show, DUB_WORD)) if dub else show, "s_season": season})
            if META_TV_RE.search(title) and show:
                params.update({"meta_type": "tv", "meta_title": show})
            self.addDir(params)
        if not seen:
            # empty category / page or no search hits: a marker instead of an empty list
            self.addMarker({"title": _("No items found"), "desc": ""})
            return

        # pager: "pagination_next" = there is a next page, the highest "/page/N" = the last page
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</ul>", False)[1]
        hasNext = bool(seen) and "pagination_next" in pager
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)['\"]", pager)] + [page])
        listItem = dict(cItem)
        # list_items, not the copied "search": that would rebuild page 1 from the search pattern
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageUrlTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AkwamOld.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.MAIN_URL + "search/" + urllib_quote(searchPattern.strip(), safe="")
        self.listItems(cItem)

    ###################################################
    # page content
    ###################################################
    def _trailer(self, data):
        yid = self.cm.ph.getSearchGroups(data, r'class="youtube-player"[^>]*data-id="([^"]+)"')[0]
        return ("https://www.youtube.com/watch?v=%s" % yid) if yid else ""

    def _files(self, data):
        # every file box of a page: (download url, file name, size, episode label, date); the
        # boxes of a series page carry the episode title ("الحلقة العشرون") and the upload date
        files = []
        seen = set()
        for box in data.split("inner_direct_link")[1:]:
            url = self.cm.ph.getSearchGroups(box, r"href=['\"]([^'\"]+/download/[0-9a-f]+/[^'\"]+)['\"]")[0]
            fid = self._fileHash(url)
            if not fid or fid in seen:
                continue
            seen.add(fid)
            ftitle = self.cm.ph.getSearchGroups(box, r"(?s)class='sub_file_title'>(.*?)</span>")[0]
            fname = self.cleanHtmlStr(ftitle.split(" - <i>")[0])
            size = self.cleanHtmlStr(self.cm.ph.getSearchGroups(ftitle, r"<i>([^<]+)</i>")[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)class="sub_epsiode_title">(.*?)</h2>')[0])
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)class="sub_create_date"[^>]*>(.*?)</span>')[0]).strip(" -")
            files.append((self._canonUrl(url), fname, size, label, date))
        return files

    @staticmethod
    def _fileExt(fname):
        return fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

    @staticmethod
    def _episodeNum(fname, label):
        # "S.W.A.T.2017.S03E21.720p..." -> ("3", "21"); "Audition.Ep09.HD..." -> ("", "9"); "الحلقة 5" -> ("", "5")
        season, episode = parseSxxExx(fname)
        if not episode:
            m = re.search(r"(?i)(?:^|[._ -])Ep?\.?\s*0*(\d{1,4})(?=[._ -]|$)", fname)
            if not m:
                m = re.search(r"الحلقة\s*0*(\d+)", label)
            episode = m.group(1) if m else ""
        return season, episode

    def listPage(self, cItem):
        printDBG("AkwamOld.listPage [%s]" % cItem.get("url", ""))
        pageUrl = self._pageUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return
        icon = cItem.get("icon", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        trailer = self._trailer(data) if page == 1 else ""
        if trailer:
            self.addVideo({"name": "category", "category": "ako_trailer", "title": "%s - %s" % (_("Trailer"), cItem.get("title", "")),
                           "url": trailer, "icon": icon, "desc": cItem.get("desc", "")})
        files = [f for f in self._files(data) if self._fileExt(f[1]) in VIDEO_EXT + AUDIO_EXT]
        # pages list newest or oldest first - by episode number when every file has one
        nums = [self._episodeNum(f[1], f[3]) for f in files]
        if nums and all(e for _s, e in nums):
            files = [f for _n, f in sorted(zip(nums, files), key=lambda p: (int(p[0][0] or 0), int(p[0][1])))]
        else:
            files.reverse()  # most pages list the newest file first
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        # long anime runs (150+ files on one page) are split locally
        lastPage = max(1, (len(files) + self.FILES_PER_PAGE - 1) // self.FILES_PER_PAGE)
        single = len(files) == 1
        for url, fname, size, label, date in files[(page - 1) * self.FILES_PER_PAGE:page * self.FILES_PER_PAGE]:
            fSeason, episode = self._episodeNum(fname, label)
            fSeason = fSeason or season
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(fSeason, episode))
            elif normalize and single:
                title = show
            else:
                title = label or fname
            desc = ("%s (%s)" % (fname, size)) if size else fname
            if date:
                desc += "[/br]%s%s:%s %s" % (E2ColoR("cyan"), _("Added"), E2ColoR("white"), date)
            params = {"name": "category", "good_for_fav": True, "category": "ako_file", "title": title, "url": url, "icon": icon,
                      "desc": desc, "page_url": pageUrl, "s_title": show, "s_season": fSeason, "s_episode": episode,
                      "meta_type": cItem.get("meta_type", ""), "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}
            if self._fileExt(fname) in AUDIO_EXT:
                self.addAudio(params)
            else:
                self.addVideo(params)
        if not files and not trailer:
            # the site removed the files ("direct-no-file": expired or moved to the new design): a marker with
            # the site's note instead of an empty list
            note = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<span class='sub-no-file'>(.*?)</span>")[0])
            self.addMarker({"title": _("No items found"), "desc": note})
            return
        # local paging: the page url is constant, it only serves "Jump" as the page template
        addPagingItems(self, dict(cItem, url=pageUrl), page, page < lastPage, lastPage, pageUrl)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cm.ph.getSearchGroups(data, r'(?s)<div class="sub_desc">(.*?)<div class=')[0]
        story = re.sub(r"(?i)<br\s*/?>", "[/br]", story)
        story = "[/br]".join(s for s in (self.cleanHtmlStr(p) for p in story.split("[/br]")) if s)
        story = re.sub(r"^قصة[^:]{0,80}:\s*", "", story)
        # one-line release note: "النسخة البلوراي لفيلم ... بجودة 720P Bluray"
        sub = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h2 id="sub-description"[^>]*>(.*?)</h2>')[0])
        if sub and sub not in story:
            story = "%s[/br][/br]%s" % (sub, story) if story else sub
        info = {}
        quality = self.cm.ph.getSearchGroups(sub, r"بجودة\s+(.+)$")[0].strip()
        if quality:
            info["quality"] = quality
        poster = self.cm.ph.getSearchGroups(data, r'class="main_img"\s*src="([^"]+)"')[0]
        return story, self._canonUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("AkwamOld.getLinksForVideo [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        url = cItem.get("url", "")
        story = ""
        urltab = []
        if category == "ako_trailer":
            urltab.append({"name": "YouTube", "url": url, "need_resolve": 1})
        elif category == "ako_file":
            name = self.cm.ph.getSearchGroups(url, r"/download/[0-9a-f]+/([^/?#]+)")[0]
            urltab.append({"name": "Akwam %s" % urllib_unquote(name), "url": url, "need_resolve": 1})
            if cItem.get("page_url") and IsSidecarEnabled():
                sts, data = self.getPage(self._pageUrl(cItem["page_url"]))
                if sts:
                    story = self._siteInfo(data)[0]
        else:
            sts, data = self.getPage(self._pageUrl(url))
            if not sts:
                return []
            story = self._siteInfo(data)[0]
            for fUrl, fname, size, label, _date in self._files(data):
                if self._fileExt(fname) not in VIDEO_EXT + AUDIO_EXT:
                    continue
                name = " - ".join(v for v in (label, fname, size) if v)
                urltab.append({"name": name, "url": fUrl, "need_resolve": 1})
            trailer = self._trailer(data)
            if trailer:
                urltab.append({"name": "%s (YouTube)" % _("Trailer"), "url": trailer, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        sidecarItem = dict(cItem, desc=_stripColors(cItem.get("desc", "")))
        return applySidecarToLinks(urltab, buildSidecarFromItem(sidecarItem, IsSidecarEnabled(), story.replace("[/br]", "\n")))

    def getVideoLinks(self, videoUrl):
        printDBG("AkwamOld.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if not self._fileHash(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        # the GET opens the session the XHR POST checks ("bad authentication" without it)
        dlUrl = self._canonUrl(str(videoUrl))
        sts, _data = self.getPage(dlUrl)
        if not sts:
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=dlUrl, Accept="application/json, text/javascript, */*; q=0.01")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        sts, data = self.getPage(dlUrl, params, {})
        if not sts:
            return []
        link = ""
        try:
            link = (json_loads(data) or {}).get("direct_link", "") or ""
        except Exception:
            printExc()
        if not self.cm.isValidUrl(link):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        link = re.sub(r"^http://", "https://", link)  # the site's own player does the same; http answers 301
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL}
        return decorateResolvedLinkItems([{"name": "Akwam", "url": strwithmeta(link, meta)}], sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AkwamOld.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # Arabic-only titles: TMDb / TVmaze only, IMDb / Cinemeta / OMDb answer them with unrelated hits
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(self._pageUrl(cItem.get("page_url") or cItem.get("url", "")))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
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
        printDBG("AkwamOld.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "ako_section":
            self.listSection(self.currItem)
        elif category == "ako_cat":
            self.listCategory(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ako_page":
            self.listPage(self.currItem)
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
        CHostBase.__init__(self, AkwamOld(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("akwamold")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ako_video", "ako_page", "ako_file")
