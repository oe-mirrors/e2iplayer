# -*- coding: utf-8 -*-
LAST_MODIFIED = "13.11.2026"
# BBC iPlayer: lists from the iPlayer JSON API (ibl.api.bbc.co.uk) and the page data
# (__IPLAYER_REDUX_STATE__) for series / episodes / search; streams through urlparser parserBBC
# (mediaselector, UK only). Watched flag / favourites / name normalisation / sidecar / INFO.
import calendar
import re
import time

from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
# defines the bbc_* options below
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.bbc import BBCCoUkIE  # noqa: F401
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.bbc_default_quality))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.bbc_use_default_quality))
    optionList.append(getConfigListEntry(_("Preferred streaming protocol") + ":", config.plugins.iptvplayer.bbc_prefered_format))
    return optionList


def gettytul():
    return "https://www.bbc.co.uk/iplayer"


MAIN_URL = "https://www.bbc.co.uk/"
IBL_URL = "https://ibl.api.bbc.co.uk/ibl/v1/"
EPISODE_URL = MAIN_URL + "iplayer/episode/%s"
PROGRAMME_URL = MAIN_URL + "iplayer/episodes/%s"
VPID_URL = MAIN_URL + "iplayer/vpid/%s/"
IMAGE_RECIPE = "640x360"
PAGE_SIZE = 50

# (stream id for the mediaselector, name, channel id of the schedule) - regional BBC One/Two share the national schedule
LIVE_CHANNELS = (
    ("bbc_one_hd", "BBC One", "bbc_one_london"),
    ("bbc_two_england", "BBC Two", "bbc_two_england"),
    ("bbc_three_hd", "BBC Three", "bbc_three"),
    ("bbc_four_hd", "BBC Four", "bbc_four"),
    ("cbbc_hd", "CBBC", "cbbc"),
    ("cbeebies_hd", "CBeebies", "cbeebies"),
    ("bbc_news24", "BBC News", "bbc_news24"),
    ("bbc_parliament", "BBC Parliament", "bbc_parliament"),
    ("bbc_alba", "BBC ALBA", "bbc_alba"),
    ("bbc_scotland_hd", "BBC Scotland", "bbc_scotland"),
    ("s4cpbs", "S4C", "s4cpbs"),
)
REGIONAL_CHANNELS = (
    ("bbc_one_london", "BBC One London"),
    ("bbc_one_scotland_hd", "BBC One Scotland"),
    ("bbc_one_northern_ireland_hd", "BBC One Northern Ireland"),
    ("bbc_one_wales_hd", "BBC One Wales"),
    ("bbc_two_scotland", "BBC Two Scotland"),
    ("bbc_two_northern_ireland_digital", "BBC Two Northern Ireland"),
    ("bbc_two_wales_digital", "BBC Two Wales"),
    ("bbc_one_cambridge", "BBC One Cambridge"),
    ("bbc_one_channel_islands", "BBC One Channel Islands"),
    ("bbc_one_east", "BBC One East"),
    ("bbc_one_east_midlands", "BBC One East Midlands"),
    ("bbc_one_east_yorkshire", "BBC One East Yorkshire"),
    ("bbc_one_north_east", "BBC One North East"),
    ("bbc_one_north_west", "BBC One North West"),
    ("bbc_one_oxford", "BBC One Oxford"),
    ("bbc_one_south", "BBC One South"),
    ("bbc_one_south_east", "BBC One South East"),
    ("bbc_one_south_west", "BBC One South West"),
    ("bbc_one_west", "BBC One West"),
    ("bbc_one_west_midlands", "BBC One West Midlands"),
    ("bbc_one_yorks", "BBC One Yorks"),
)
AZ_LETTERS = ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "0-9")
# categories whose programmes moviemeta knows as TV series (news, sport, documentaries ... would only find wrong matches)
TV_META_CATEGORIES = ("drama-and-soaps", "comedy", "cbbc", "cbeebies")
# search results carry no categories, only the genre label: the labels of those categories' programmes
TV_META_LABELS = ("Drama", "Crime Drama", "Period Drama", "Comedy Drama", "Comedy", "Sci-Fi", "Fantasy", "CBBC", "CBeebies")
# "Series 2: 5. The Name" / "Series 11: Episode 1"
SXE_RE = re.compile(r'^Series\s+(\d+)\s*:\s*(?:Episode\s+)?(\d+)\b\.?\s*(.*)$', re.I)
SERIES_RE = re.compile(r'^Series\s+(\d+)$', re.I)


class BBCiPlayer(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # every field a list function needs to open the item again from the favourites
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "prog_id", "slice_id", "ep_id", "tleo_id", "stream_id",
                  "sched_id", "group_id", "cat_id", "ch_id", "letter", "s_title", "season", "episode", "live",
                  "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "bbciplayer", "cookie": "bbciplayer.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = MAIN_URL
        self.MENU = [{"category": "bbc_live", "title": _("Live channels")},
                     {"category": "bbc_home", "title": _("Home page")},
                     {"category": "bbc_group", "title": _("Most popular"), "group_id": "popular", "url": MAIN_URL + "iplayer/group/popular"},
                     {"category": "bbc_channels", "title": _("Channels")},
                     {"category": "bbc_categories", "title": _("Categories")},
                     {"category": "bbc_az_letters", "title": _("A-Z")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("bbciplayer")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") == "video" and cItem.get("ep_id"):
                return "video:%s" % (EPISODE_URL % cItem["ep_id"])
            if category == "bbc_programme" and cItem.get("prog_id"):
                return "programme:%s" % cItem["prog_id"]
            if category == "bbc_series" and cItem.get("prog_id") and cItem.get("slice_id"):
                return "series:%s|%s" % (cItem["prog_id"], cItem["slice_id"])
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _getJson(self, url):
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return {}
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return {}

    def _ibl(self, path):
        return self._getJson(IBL_URL + path)

    def _pageState(self, url):
        # the JSON the iPlayer pages are rendered from
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return {}
        match = re.search(r'window\.__IPLAYER_REDUX_STATE__\s*=\s*(\{.*?\});?\s*</script>', data, re.S)
        if not match:
            printDBG("BBCiPlayer._pageState no page data [%s]" % url)
            return {}
        try:
            return json_loads(match.group(1))
        except Exception:
            printExc()
        return {}

    def _text(self, value):
        # titles / subtitles are plain strings in the API and {"default": ...} on the pages
        if isinstance(value, dict):
            value = value.get("default") or value.get("slice") or ""
        return self.cleanHtmlStr(value or "")

    def _synopsis(self, synopses, folder=False):
        if not isinstance(synopses, dict):
            return self.cleanHtmlStr(synopses or "")
        keys = ("programme_small", "editorial", "medium", "large", "small") if folder else ("medium", "large", "small", "editorial")
        for key in keys:
            if synopses.get(key):
                return self.cleanHtmlStr(synopses[key])
        return ""

    def _image(self, images, folder=False):
        if not isinstance(images, dict):
            return ""
        keys = ("promotional", "standard", "default", "portrait") if folder else ("standard", "default", "promotional", "portrait")
        for key in keys:
            if images.get(key):
                return images[key].replace("{recipe}", IMAGE_RECIPE)
        return ""

    def _localTime(self, isoTime):
        try:
            return time.strftime("%H:%M", time.localtime(calendar.timegm(time.strptime(isoTime[:19], "%Y-%m-%dT%H:%M:%S"))))
        except Exception:
            return ""

    def _isFilm(self, item):
        labels = item.get("labels") or {}
        label = labels.get("category") or ""
        return "films" in (item.get("categories") or []) or label in ("Films", "Film") or label.startswith("Film - ")

    def _metaType(self, item):
        if self._isFilm(item):
            return "movie"
        categories = item.get("categories")
        if categories:
            return "tv" if set(categories) & set(TV_META_CATEGORIES) else ""
        return "tv" if (item.get("labels") or {}).get("category") in TV_META_LABELS else ""

    def _episodeTitle(self, show, subtitle):
        subtitle = (subtitle or "").strip()
        match = SXE_RE.match(subtitle)
        season = match.group(1) if match else ""
        episode = match.group(2) if match else ""
        if IsMediaNamingNormalized() and season and episode:
            title = "%s - %s" % (show, formatSxxExx(season, episode))
            name = match.group(3).strip()
            return ("%s - %s" % (title, name) if name else title), season, episode
        if not subtitle or subtitle == show:
            return show, season, episode
        if not show:
            return subtitle, season, episode
        return "%s - %s" % (show, subtitle), season, episode

    ###################################################
    # rows
    ###################################################
    def _addEpisode(self, cItem, ep, show=""):
        epId = ep.get("id", "")
        if not epId or ep.get("type", "episode") != "episode":
            return False
        show = show or self._text(ep.get("title"))
        title, season, episode = self._episodeTitle(show, self._text(ep.get("subtitle")))
        desc = []
        labels = ep.get("labels") or {}
        versions = ep.get("versions") or []
        if versions:
            duration = (versions[0].get("duration") or {}).get("text", "")
            remaining = (versions[0].get("availability") or {}).get("remaining", "")
            if isinstance(remaining, dict):
                remaining = remaining.get("text", "")
            desc.extend([t for t in (duration, remaining) if t])
        if labels.get("category"):
            desc.append(labels["category"])
        descText = " | ".join(desc)
        synopsis = self._synopsis(ep.get("synopses") or ep.get("synopsis"))
        if synopsis:
            descText = "%s\n%s" % (descText, synopsis) if descText else synopsis
        isFilm = self._isFilm(ep) and ep.get("programme_type") == "one-off"
        metaType = metaTitle = ""
        if isFilm:
            metaType, metaTitle = "movie", show
        elif cItem.get("meta_type") == "tv" and show and show == cItem.get("s_title"):
            # an episode of a drama / comedy programme opened from it: moviemeta of the series (INFO, sidecar)
            metaType, metaTitle = "tv", cItem.get("meta_title") or show
        params = stripPagerKeys(dict(cItem), ("slice_id", "group_id", "cat_id", "ch_id", "letter", "stream_id", "sched_id"))
        params.update({"good_for_fav": True, "category": "bbc_video", "title": title, "url": EPISODE_URL % epId, "ep_id": epId,
                       "tleo_id": ep.get("tleo_id") or ep.get("tleoId") or "", "icon": self._image(ep.get("images") or ep.get("image")),
                       "desc": descText, "s_title": show, "season": season, "episode": episode, "live": False,
                       "meta_type": metaType, "meta_title": metaTitle, "meta_year": "",
                       "meta_season": season if metaType == "tv" else "", "meta_episode": episode if metaType == "tv" else ""})
        self.addVideo(params)
        return True

    def _addProgramme(self, cItem, item):
        progId = item.get("id", "")
        if not progId:
            return False
        if item.get("type") == "episode":
            return self._addEpisode(cItem, item)
        title = self._text(item.get("title"))
        children = item.get("initial_children") or []
        count = item.get("count")
        if children and (item.get("programme_type") == "one-off" or count == 1):
            child = dict(children[0])
            child.setdefault("categories", item.get("categories"))
            # a single programme (film, one-off): the episode itself, under the programme's title
            return self._addEpisode(cItem, child, title)
        desc = []
        if count:
            desc.append("%s %s" % (_("Episodes:"), count))
        category = (item.get("labels") or {}).get("category", "")
        if category:
            desc.append(category)
        descText = " | ".join(desc)
        synopsis = self._synopsis(item.get("synopses"), True)
        if synopsis:
            descText = "%s\n%s" % (descText, synopsis) if descText else synopsis
        metaType = self._metaType(item)
        params = stripPagerKeys(dict(cItem), ("slice_id", "group_id", "cat_id", "ch_id", "letter", "ep_id", "stream_id", "sched_id"))
        params.update({"good_for_fav": True, "category": "bbc_programme", "title": title, "url": PROGRAMME_URL % progId, "prog_id": progId,
                       "icon": self._image(item.get("images"), True), "desc": descText, "s_title": title, "live": False,
                       "meta_type": "tv" if metaType == "tv" else "", "meta_title": title, "meta_year": ""})
        self.addDir(params)
        return True

    def _addGroup(self, cItem, groupId, title, desc=""):
        params = stripPagerKeys(dict(cItem), ("slice_id", "cat_id", "ch_id", "letter", "prog_id", "ep_id"))
        params.update({"good_for_fav": True, "category": "bbc_group", "title": self.cleanHtmlStr(title), "group_id": groupId,
                       "url": MAIN_URL + "iplayer/group/" + groupId, "desc": desc})
        self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listLive(self, cItem):
        printDBG("BBCiPlayer.listLive")
        for streamId, name, schedId in LIVE_CHANNELS:
            self._addLive(cItem, streamId, name, schedId)
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "bbc_live_regional", "title": _("Regions"), "desc": ""})
        self.addDir(params)

    def listLiveRegional(self, cItem):
        # the regions only differ in their local news: the national schedule (asked for once per list)
        cache = {}
        for streamId, name in REGIONAL_CHANNELS:
            self._addLive(cItem, streamId, name, "bbc_two_england" if streamId.startswith("bbc_two") else "bbc_one_london", cache)

    def _schedule(self, schedId):
        # now / next of a channel
        if not schedId:
            return ""
        data = self._ibl("channels/%s/broadcasts?per_page=2" % schedId)
        lines = []
        for broadcast in ((data.get("broadcasts") or {}).get("elements") or [])[:2]:
            episode = broadcast.get("episode") or {}
            title = self._text(episode.get("title"))
            subtitle = self._text(episode.get("subtitle"))
            if subtitle:
                title = "%s - %s" % (title, subtitle)
            start = self._localTime(broadcast.get("scheduled_start", ""))
            end = self._localTime(broadcast.get("scheduled_end", ""))
            label = _("Now") if not lines else _("Next")
            lines.append("%s %s-%s %s" % (label, start, end, title))
        return "\n".join(lines)

    def _addLive(self, cItem, streamId, name, schedId, cache=None):
        if cache is None:
            cache = {}
        if schedId not in cache:
            cache[schedId] = self._schedule(schedId)
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "bbc_live_channel", "title": name, "url": VPID_URL % streamId, "stream_id": streamId,
                       "sched_id": schedId, "live": True, "desc": cache[schedId]})
        self.addVideo(params)

    def listHome(self, cItem):
        printDBG("BBCiPlayer.listHome")
        state = self._pageState(MAIN_URL + "iplayer")
        for bundle in state.get("bundles") or []:
            journey = bundle.get("journey") or {}
            title = self._text(bundle.get("title"))
            if not title or not journey.get("id"):
                continue
            if journey.get("type") == "group":
                self._addGroup(cItem, journey["id"], title)
            elif journey.get("type") == "category":
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "bbc_category", "title": title, "cat_id": journey["id"], "desc": ""})
                self.addDir(params)

    def listGroup(self, cItem):
        groupId = cItem.get("group_id", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        printDBG("BBCiPlayer.listGroup [%s] page %s" % (groupId, page))
        data = (self._ibl("groups/%s/episodes?per_page=%d&page=%d" % (groupId, PAGE_SIZE, page)).get("group_episodes")) or {}
        curated = (data.get("group") or {}).get("group_type") == "curated"
        seen = set()
        for ep in data.get("elements") or []:
            tleoId = ep.get("tleo_id", "")
            if curated and tleoId and tleoId != ep.get("id") and ep.get("programme_type") != "one-off":
                # curated collections present whole programmes: open the programme, once
                if tleoId in seen:
                    continue
                seen.add(tleoId)
                self._addProgramme(cItem, {"id": tleoId, "title": ep.get("title"), "images": ep.get("images"), "labels": ep.get("labels"),
                                           "synopses": ep.get("synopses"), "categories": ep.get("categories"), "programme_type": ep.get("programme_type")})
            else:
                self._addEpisode(cItem, ep)
        lastPage = (int(data.get("count", 0) or 0) + PAGE_SIZE - 1) // PAGE_SIZE
        addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, IBL_URL + "groups/%s/episodes?page={page}" % groupId)

    def listChannels(self, cItem):
        printDBG("BBCiPlayer.listChannels")
        for channel in self._ibl("channels").get("channels") or []:
            if not channel.get("id"):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "bbc_channel", "title": self.cleanHtmlStr(channel.get("title") or channel["id"]),
                           "ch_id": channel["id"], "desc": ""})
            self.addDir(params)

    def listChannel(self, cItem):
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "bbc_channel_highlights", "title": "%s - %s" % (cItem.get("title", ""), _("Highlights"))})
        self.addDir(params)
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "bbc_channel_az", "title": "%s - %s" % (cItem.get("title", ""), _("All programmes"))})
        self.addDir(params)

    def listChannelHighlights(self, cItem):
        data = self._ibl("channels/%s/highlights" % cItem.get("ch_id", "")).get("channel_highlights") or {}
        for item in data.get("elements") or []:
            if item.get("type") == "group" and item.get("id"):
                self._addGroup(cItem, item["id"], self._text(item.get("title")))
            else:
                self._addProgramme(cItem, item)

    def _listProgrammes(self, cItem, path, key):
        page = max(1, int(cItem.get("page", 1) or 1))
        sep = "&" if "?" in path else "?"
        data = self._ibl("%s%sper_page=%d&page=%d" % (path, sep, PAGE_SIZE, page)).get(key) or {}
        for item in data.get("elements") or []:
            self._addProgramme(cItem, item)
        lastPage = (int(data.get("count", 0) or 0) + PAGE_SIZE - 1) // PAGE_SIZE
        addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, IBL_URL + path + sep + "page={page}")

    def listChannelAZ(self, cItem):
        self._listProgrammes(cItem, "channels/%s/programmes" % cItem.get("ch_id", ""), "channel_programmes")

    def listCategories(self, cItem):
        printDBG("BBCiPlayer.listCategories")
        for cat in self._ibl("categories").get("categories") or []:
            if not cat.get("id"):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "bbc_category", "title": self.cleanHtmlStr(cat.get("title") or cat["id"]),
                           "cat_id": cat["id"], "desc": ""})
            self.addDir(params)

    def listCategory(self, cItem):
        # all programmes A-Z, then the collections the category page shows
        catId = cItem.get("cat_id", "")
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "bbc_category_az", "title": "%s - %s" % (cItem.get("title", ""), _("All programmes"))})
        self.addDir(params)
        sts, data = self.cm.getPage(MAIN_URL + "iplayer/browse/" + catId, self.defaultParams)
        if not sts:
            return
        match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(".*?"|\{.*?\});?\s*</script>', data, re.S)
        if not match:
            return
        try:
            state = json_loads(match.group(1))
            if not isinstance(state, dict):
                state = json_loads(state)
            for rail in (state.get("data") or {}).values():
                railData = rail.get("data") or {}
                if (rail.get("props") or {}).get("dataType") == "contentCollectionData" and railData.get("urn") and railData.get("title"):
                    self._addGroup(cItem, railData["urn"], railData["title"])
        except Exception:
            printExc()

    def listCategoryAZ(self, cItem):
        self._listProgrammes(cItem, "categories/%s/programmes?sort=title" % cItem.get("cat_id", ""), "category_programmes")

    def listAZLetters(self, cItem):
        for letter in AZ_LETTERS:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "bbc_az", "title": letter.upper(), "letter": letter, "desc": ""})
            self.addDir(params)

    def listAZ(self, cItem):
        self._listProgrammes(cItem, "atoz/%s/programmes" % cItem.get("letter", "a"), "atoz_programmes")

    def listProgramme(self, cItem):
        # the series of a programme, or its episodes when it has only one
        progId = cItem.get("prog_id", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        printDBG("BBCiPlayer.listProgramme [%s] page %s" % (progId, page))
        state = self._pageState(PROGRAMME_URL % progId + ("?page=%d" % page if page > 1 else ""))
        header = state.get("header") or {}
        show = cItem.get("s_title", "") or self._text(header.get("title"))
        if page > 1:
            # further pages of a programme with a single series
            self._listEpisodes(cItem, state, show)
            return
        slices = [s for s in header.get("availableSlices") or [] if s.get("id") and s.get("id") != "more-like-this"]
        if len(slices) > 1:
            for item in slices:
                sliceTitle = self.cleanHtmlStr(item.get("title") or "")
                match = SERIES_RE.match(sliceTitle)
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "bbc_series", "title": "%s - %s" % (show, sliceTitle), "s_title": show,
                               "slice_id": item["id"], "season": match.group(1) if match else "", "url": "%s?seriesId=%s" % (PROGRAMME_URL % progId, item["id"])})
                self.addDir(params)
        else:
            self._listEpisodes(cItem, state, show)
        if any(s.get("id") == "more-like-this" for s in header.get("availableSlices") or []):
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "bbc_series", "title": "%s - More Like This" % show, "s_title": show,
                           "slice_id": "more-like-this", "season": "", "url": "%s?seriesId=more-like-this" % (PROGRAMME_URL % progId),
                           "meta_type": "", "desc": ""})
            self.addDir(params)

    def listSeries(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        url = "%s?seriesId=%s" % (PROGRAMME_URL % cItem.get("prog_id", ""), cItem.get("slice_id", ""))
        if page > 1:
            url += "&page=%d" % page
        self._listEpisodes(cItem, self._pageState(url), cItem.get("s_title", ""))

    def _listEpisodes(self, cItem, state, show):
        page = max(1, int(cItem.get("page", 1) or 1))
        mlt = cItem.get("slice_id") == "more-like-this"
        for result in (state.get("entities") or {}).get("results") or []:
            episode = result.get("episode") or {}
            # "More Like This" lists other programmes: their own title
            self._addEpisode(cItem, episode, "" if mlt else show)
        lastPage = int((state.get("pagination") or {}).get("totalPages", 0) or 0)
        if cItem.get("slice_id"):
            tpl = "%s?seriesId=%s&page={page}" % (PROGRAMME_URL % cItem.get("prog_id", ""), cItem["slice_id"])
        else:
            tpl = "%s?page={page}" % (PROGRAMME_URL % cItem.get("prog_id", ""))
        addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        # iPlayer answers the best 24 matches; page=2 repeats them, so there is no paging
        printDBG("BBCiPlayer.listSearchResult [%s]" % searchPattern)
        state = self._pageState(MAIN_URL + "iplayer/search?q=" + urllib_quote_plus(searchPattern))
        for item in (state.get("entities") or {}).get("results") or []:
            self._addProgramme(cItem, item)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("BBCiPlayer.getLinksForVideo [%s]" % cItem.get("url", ""))
        sidecar = buildSidecarFromItem(cItem, IsSidecarEnabled())
        if cItem.get("stream_id"):
            return applySidecarToLinks([{"name": cItem.get("title", ""), "url": VPID_URL % cItem["stream_id"], "need_resolve": 1}], sidecar)
        epId = cItem.get("ep_id", "")
        if not epId:
            return []
        episodes = self._ibl("episodes/%s" % epId).get("episodes") or []
        if not episodes:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        episode = episodes[0]
        versions = [v for v in episode.get("versions") or [] if v.get("id")]
        if not versions:
            SetIPTVPlayerLastHostError(_("Not available yet") if episode.get("status") == "unavailable" else _("Content not available"))
            return []
        main = BBCCoUkIE.pickVersion(versions)
        ordered = ([main] if main else []) + [v for v in versions if v is not main]
        urlTab = []
        for version in ordered:
            kind = version.get("kind", "")
            if kind == "audio-described":
                name = _("Audio description")
            elif kind == "signed":
                name = "Sign language"
            else:
                name = (version.get("duration") or {}).get("text", "") or kind
            if version.get("hd"):
                name += " HD"
            urlTab.append({"name": name, "url": VPID_URL % version["id"], "need_resolve": 1})
        return applySidecarToLinks(urlTab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("BBCiPlayer.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("BBCiPlayer.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        category = cItem.get("category", "")
        try:
            if category == "bbc_video" and cItem.get("ep_id"):
                episodes = self._ibl("episodes/%s" % cItem["ep_id"]).get("episodes") or []
                if episodes:
                    info = episodes[0]
                    synopses = info.get("synopses") or {}
                    # the longest text first, then the short ones
                    text = self.cleanHtmlStr(synopses.get("large") or "") or self._synopsis(synopses) or text
                    icon = self._image(info.get("images")) or icon
                    if (info.get("labels") or {}).get("category"):
                        otherInfo["genre"] = info["labels"]["category"]
                    if (info.get("master_brand") or {}).get("titles"):
                        otherInfo["station"] = info["master_brand"]["titles"].get("large", "")
                    if info.get("release_date"):
                        otherInfo["released"] = info["release_date"]
                    version = BBCCoUkIE.pickVersion(info.get("versions"))
                    if version:
                        if (version.get("duration") or {}).get("text"):
                            otherInfo["duration"] = version["duration"]["text"]
                        if version.get("first_broadcast"):
                            otherInfo["broadcast"] = version["first_broadcast"]
                        remaining = (version.get("availability") or {}).get("remaining")
                        if isinstance(remaining, dict):
                            remaining = remaining.get("text", "")
                        if remaining:
                            otherInfo["remaining"] = remaining
                    otherInfo["status"] = _("Only available in %s") % "UK"
            elif category in ("bbc_programme", "bbc_series") and cItem.get("prog_id"):
                programmes = self._ibl("programmes/%s" % cItem["prog_id"]).get("programmes") or []
                if programmes:
                    info = programmes[0]
                    synopses = info.get("synopses") or {}
                    text = self.cleanHtmlStr(synopses.get("large") or synopses.get("medium") or "") or text
                    icon = self._image(info.get("images"), True) or icon
                    if (info.get("labels") or {}).get("category"):
                        otherInfo["genre"] = info["labels"]["category"]
                    if (info.get("master_brand") or {}).get("titles"):
                        otherInfo["station"] = info["master_brand"]["titles"].get("large", "")
                    if info.get("count"):
                        otherInfo["episodes"] = str(info["count"])
                    otherInfo["status"] = _("Only available in %s") % "UK"
            elif category == "bbc_live_channel":
                otherInfo["status"] = _("Only available in %s") % "UK"
        except Exception:
            printExc()

        if cItem.get("meta_type") in ("movie", "tv") and cItem.get("meta_title"):
            # films and drama / comedy series: the BBC text stays, moviemeta adds rating / cast / director
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
                meta = {}
            for key, value in (meta.get("info", {}) or {}).items():
                if value:
                    otherInfo.setdefault(key, value)
            if not icon:
                icon = meta.get("poster", "")
            if not text:
                text = meta.get("plot", "")
        return [{"title": title, "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("bbc_"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("BBCiPlayer.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.informAboutGeoBlockingIfNeeded("GB")
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "bbc_live":
            self.listLive(self.currItem)
        elif category == "bbc_live_regional":
            self.listLiveRegional(self.currItem)
        elif category == "bbc_home":
            self.listHome(self.currItem)
        elif category == "bbc_group":
            self.listGroup(self.currItem)
        elif category == "bbc_channels":
            self.listChannels(self.currItem)
        elif category == "bbc_channel":
            self.listChannel(self.currItem)
        elif category == "bbc_channel_highlights":
            self.listChannelHighlights(self.currItem)
        elif category == "bbc_channel_az":
            self.listChannelAZ(self.currItem)
        elif category == "bbc_categories":
            self.listCategories(self.currItem)
        elif category == "bbc_category":
            self.listCategory(self.currItem)
        elif category == "bbc_category_az":
            self.listCategoryAZ(self.currItem)
        elif category == "bbc_az_letters":
            self.listAZLetters(self.currItem)
        elif category == "bbc_az":
            self.listAZ(self.currItem)
        elif category == "bbc_programme":
            self.listProgramme(self.currItem)
        elif category == "bbc_series":
            self.listSeries(self.currItem)
        elif category == "search":
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
        CHostBase.__init__(self, BBCiPlayer(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("bbciplayer")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("bbc_video", "bbc_programme", "bbc_series", "bbc_live_channel")
