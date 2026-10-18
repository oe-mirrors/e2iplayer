# -*- coding: utf-8 -*-
LAST_MODIFIED = "17.10.2026"
# 17.10.2026 - new host for geoarabic.com (Blogger: Arabic dubbed and subtitled documentaries of National Geographic
#   Abu Dhabi, Al Jazeera Documentary, Nat Geo Wild, Nat Geo Kids ...)
#   - lists from the blog's JSON feed (per label, search), First page / Jump / Next page from the feed's total;
#     topics = the blog's labels (local pages); article posts without a video are left out
#   - every post is a VIDEO row keyed on its page url; its servers come from the post's source table
#     (Google Drive, ok.ru, YouTube, Dailymotion, VK) and are resolved through urlparser;
#     YouTube videos the channel has removed are left out
#   - watched flag, downloaded flag, favourites, name normalisation ("Show - SxxExx" for episodes), sidecar,
#     INFO from the post (story, labels, date) + moviemeta
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.geoarabic.com/"


PAGE_SIZE = 25
LABELS_PAGE_SIZE = 100
# channel labels of the blog (site names, not translated)
CHANNELS = ("افلام ناشيونال جيوغرافيك", "افلام الجزيرة الوثائقية", "افلام نات جيو وايلد", "ناشيونال جيوغرافيك كيدز",
            "افلام كويست عربية", "افلام مترجمة")
# labels of the text articles - no videos behind them
ARTICLE_LABEL_RE = re.compile(r"مقالات|معلومات")
# "وثائقي | X", "ناشيونال للأطفال | X", "مباشر | X" -> X; "X | مترجم", "X | الجزيرة الوثائقية" -> X
# (only these words: other titles have a "|" inside the name)
PREFIX_RE = re.compile(r"^\s*(?:وثائقي|وثاتقي|ناشيونال للأطفال|مباشر|مقال)\s*\|\s*")
SUFFIX_RE = re.compile(r"\s*\|\s*(?:مترجم|مترجمة|مدبلج|مدبلجة|الجزيرة الوثائقية)\s*$")
ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثالثة", 3), ("الثالث", 3),
    ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7),
    ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
_ORD = "|".join(o[0] for o in ORDINALS)
# "الحلقة 9", "حلقة رقم 9", "العرض السادس" (the sixth show of a series)
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(?:رقم\s*)?(\d+|%s)|العرض\s+(\d+|%s)" % (_ORD, _ORD))
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % _ORD)
# the post's source table: <td id="tdvideoIDOk">774954093307</td>
SOURCE_RE = re.compile(r'<td id="tdvideo([A-Za-z0-9]+)">([^<]*)</td>')
# source id -> (server name, url template); IDGoogle (old Blogger video) and IDGoogleReserve (Google Photos) do not
# play, IDRutube has no resolver in urlparser
SOURCES = (
    ("IDGoogleDrive", "Google Drive", "https://drive.google.com/file/d/%s/view"),
    ("IDOk", "ok.ru", "https://ok.ru/videoembed/%s"),
    ("2IDOk", "ok.ru 2", "https://ok.ru/videoembed/%s"),
    ("ID", "YouTube", "https://www.youtube.com/watch?v=%s"),
    ("2ID", "YouTube 2", "https://www.youtube.com/watch?v=%s"),
    ("IDDaily", "Dailymotion", "https://www.dailymotion.com/embed/video/%s"),
    ("2IDDaily", "Dailymotion 2", "https://www.dailymotion.com/embed/video/%s"),
    ("IDVk", "VK", "https://vk.com/video_ext.php?%s"),
    ("IDiframelink", "", "%s"),
)


def _num(val):
    if not val:
        return 0
    return int(val) if val.isdigit() else dict(ORDINALS).get(val, 0)


def _cleanName(title):
    # -> (name without the channel prefix, show, season (0 = none), episode ("" = none))
    name = re.sub(r"\s+", " ", SUFFIX_RE.sub("", PREFIX_RE.sub("", title or ""))).strip()
    episode = EPISODE_RE.search(name)
    season = SEASON_RE.search(name)
    if not episode:
        return name or title, "", 0, ""
    cut = min(m.start() for m in (episode, season) if m)
    show = name[:cut].strip(" -:|،")
    return name, show or name, _num(season.group(1)) if season else 0, str(_num(episode.group(1) or episode.group(2)) or "")


def _sources(html):
    # {source id: value} of the post's table, without the empty "no_video" cells
    found = {}
    for key, val in SOURCE_RE.findall(html or ""):
        val = val.strip().replace("&amp;", "&")
        if val and val != "no_video" and key not in found:
            found[key] = val
    return found


class GeoArabic(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "labels", "date", "s_title", "s_season",
                  "s_episode", "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "geoarabic", "cookie": "geoarabic.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/geoarabic135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Documentaries"), "label": "وثائقي"},
            {"category": "list_items", "title": _("Kids"), "label": "أطفال"},
            {"category": "ga_channels", "title": _("Channels")},
            {"category": "ga_labels", "title": _("Topics")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("geoarabic")
        self.wfInitFolderCache()
        self.labelsCache = []

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _feedUrl(self, label="", query="", start=1, count=PAGE_SIZE, kind="default"):
        url = self.getFullUrl("/feeds/posts/%s" % kind)
        if label:
            url += "/-/" + urllib_quote(label, safe="")
        url += "?alt=json&start-index=%d&max-results=%d" % (start, count)
        if query:
            url += "&q=" + urllib_quote_plus(query)
        return url

    def _feed(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return {}
        try:
            return json_loads(data).get("feed", {}) or {}
        except Exception:
            printDBG("GeoArabic._feed no JSON from [%s]" % url)
        return {}

    def _canonUrl(self, url):
        # posts are linked as http://www.geoarabic.com/... in the feed
        url = (url or "").strip()
        if url.startswith("//"):
            url = "https:" + url
        elif url and not url.startswith("http"):
            url = self.getFullUrl(url)
        return re.sub(r"^https?://(?:www\.)?geoarabic\.com/", self.MAIN_URL, url)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(self._canonUrl(url))).rstrip("/").lower()

    @staticmethod
    def _bigImage(url):
        # Blogger thumbnails (/s72-c/, /w20-h17-c/, /s200/) -> a 400 px wide picture
        return re.sub(r"/(?:s\d+(?:-c)?|w\d+-h\d+(?:-[a-z]+)*)/", "/w400/", url or "", count=1)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "ga_video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _title(self, rawTitle):
        # -> (display title, show, season, episode); "Show - SxxExx" only with the naming option
        name, show, season, episode = _cleanName(rawTitle)
        if not IsMediaNamingNormalized():
            return rawTitle, show, season, episode
        if episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode)), show, season, episode
        return name, show, season, episode

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("category") == "ga_video":
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
            if cItem.get("category") == "list_items" and cItem.get("label") and not cItem.get("query"):
                return "label:%s" % cItem["label"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listChannels(self, cItem):
        for label in CHANNELS:
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": label, "label": label,
                         "icon": self.DEFAULT_ICON_URL})

    def listLabels(self, cItem):
        if not self.labelsCache:
            feed = self._feed(self._feedUrl(count=1, kind="summary"))
            labels = [c.get("term", "") for c in feed.get("category", []) or []]
            self.labelsCache = sorted(set(t for t in labels if t and t not in CHANNELS and not ARTICLE_LABEL_RE.search(t)))
        labels = self.labelsCache
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(labels) + LABELS_PAGE_SIZE - 1) // LABELS_PAGE_SIZE
        for label in labels[(page - 1) * LABELS_PAGE_SIZE:page * LABELS_PAGE_SIZE]:
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": label, "label": label,
                         "icon": self.DEFAULT_ICON_URL})
        if lastPage > 1:
            addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, "geoarabic-labels")

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        label, query = cItem.get("label", ""), cItem.get("query", "")
        url = self._feedUrl(label, query, (page - 1) * PAGE_SIZE + 1)
        printDBG("GeoArabic.listItems [%s]" % url)
        feed = self._feed(url)
        entries = feed.get("entry", []) or []
        for entry in entries:
            self._addEntry(entry)
        try:
            total = int(feed.get("openSearch$totalResults", {}).get("$t", 0))
        except (TypeError, ValueError):
            total = 0
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        # paged by feed entries: a page of text articles only still leads on to the next one
        listItem = dict(cItem)
        listItem.update({"category": "list_items"})
        addPagingItems(self, listItem, page, bool(entries) and lastPage > page, lastPage, "geoarabic-feed")

    def _addEntry(self, entry):
        content = (entry.get("content", {}) or {}).get("$t", "") or (entry.get("summary", {}) or {}).get("$t", "")
        if not self._linkUrls(_sources(content)):
            return False
        url = ""
        for link in entry.get("link", []) or []:
            if link.get("rel") == "alternate":
                url = self._canonUrl(link.get("href", ""))
        rawTitle = self.cleanHtmlStr((entry.get("title", {}) or {}).get("$t", ""))
        if not url or not rawTitle:
            return False
        title, show, season, episode = self._title(rawTitle)
        icon = (entry.get("media$thumbnail", {}) or {}).get("url", "") or self.cm.ph.getSearchGroups(content, r'<img[^>]+src="([^"]+)"')[0]
        labels = [c.get("term", "") for c in entry.get("category", []) or [] if c.get("term")]
        date = ((entry.get("published", {}) or {}).get("$t", "") or "")[:10]
        story = self._story(content)
        desc = " | ".join(x for x in (", ".join(labels), date) if x)
        if story:
            desc = "%s[/br]%s" % (desc, story[:300]) if desc else story[:300]
        params = {"name": "category", "category": "ga_video", "good_for_fav": True, "url": url, "title": title,
                  "icon": self._bigImage(icon), "desc": desc, "labels": ", ".join(labels), "date": date,
                  "meta_title": show if episode else _cleanName(rawTitle)[0], "meta_type": "tv" if episode else "movie"}
        if episode:
            params.update({"s_title": show, "s_season": season or 1, "s_episode": episode})
        self.addVideo(params)
        return True

    def _story(self, content):
        # the post text after the source table
        text = re.sub(r"(?s)<table.*?</table>", "", content or "")
        text = re.sub(r"(?s)<script.*?</script>", "", text)
        return self.cleanHtmlStr(text)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GeoArabic.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "query": searchPattern.strip(), "label": ""})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _youtubeAlive(self, videoId):
        # the channel removed many of its uploads: oEmbed answers 404 (400 for a broken id) for them. Any other
        # answer keeps the link - 401 is only "embedding disabled", a network error says nothing about the video
        url = "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=%s" % videoId
        params = {"header": {"User-Agent": self.HEADER.get("User-Agent")}, "ignore_http_code_ranges": [(400, 499)]}
        self.cm.getPage(url, params)
        return self.cm.meta.get("status_code") not in (400, 404)

    def _linkUrls(self, sources, check=False):
        # [(server name, url)] in the order of SOURCES
        links = []
        for key, name, tpl in SOURCES:
            val = sources.get(key, "")
            if not val:
                continue
            if key == "IDiframelink":
                if not val.startswith("http") or "facebook.com" in val:
                    continue
                name = self.up.getDomain(val, onlyDomain=True)
            elif check and key in ("ID", "2ID") and not self._youtubeAlive(val):
                continue
            links.append((name, tpl % val))
        return links

    def getLinksForVideo(self, cItem):
        printDBG("GeoArabic.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(self._canonUrl(cItem.get("url", "")))
        if not sts:
            return []
        urltab = []
        for name, url in self._linkUrls(_sources(data), True):
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), "", skip=() if isLatinTitle(cItem.get("meta_title", "")) else LATIN_ONLY)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("GeoArabic.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("GeoArabic.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        url = self._canonUrl(cItem.get("url", ""))
        labels = cItem.get("labels", "")
        sts, data = self.getPage(url)
        if sts:
            body = self.cm.ph.getDataBeetwenMarkers(data, "post-body entry-content", "<div id='share-this'>", False)[1]
            story = self._story(body.split(">", 1)[-1])
            poster = self.cm.ph.getSearchGroups(data, r"""<meta content=['"]([^'"]+)['"] property=['"]og:image['"]""")[0]
            # the page draws its labels by script: setlink(' label', true, ...)
            labels = labels or ", ".join(x.strip() for x in re.findall(r"setlink\('([^']+)',\s*true", data))
        if labels:
            info["genres"] = labels
        # the feed's date, else year / month of the post url (/2019/10/...)
        date = cItem.get("date", "") or "-".join(self.cm.ph.getSearchGroups(url, r"/(\d{4})/(\d\d)/", 2))
        if date.strip("-"):
            info["released"] = date
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                title = cItem["meta_title"]
                meta = getMeta(cItem["meta_type"], title, "", () if isLatinTitle(title) else LATIN_ONLY)
            except Exception:
                printExc()
        # the post's own story and picture first: a documentary title often finds an unrelated film
        for key, val in (meta.get("info", {}) or {}).items():
            info.setdefault(key, val)
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = poster or cItem.get("icon", "") or meta.get("poster", "")
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
        printDBG("GeoArabic.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ga_channels":
            self.listChannels(self.currItem)
        elif category == "ga_labels":
            self.listLabels(self.currItem)
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
        CHostBase.__init__(self, GeoArabic(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("geoarabic")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "ga_video"
