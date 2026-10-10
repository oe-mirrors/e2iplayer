# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - host standard. TV Trwam: the site is an InsysGo app now (the old html lists and the "sources" of
#   the player are gone) - live stream, catch-up per day and shows -> episodes come from its api
#   (api-trwam.app.insysgo.pl, no account needed), streams from its Player/AcquireContent (HLS first, then DASH);
#   old recordings of the live channel (their time window of the live stream answers 404) are left out. Radio Maryja: live stream as an audio row, the audio / video sections as audio / video rows (the mp3
#   of the article page, YouTube videos through urlparser), First page / Jump / Next page with the last page,
#   search of both. Watched flag (show -> episode), downloaded marker, favourites, sidecar, INFO from the sites'
#   own data, "Show (YYYY-MM-DD)" naming, local icons, default user agent
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from datetime import datetime, timedelta
import re
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://luxveritatis.pl/"


TRWAM_URL = "https://tv-trwam.pl/"
TRWAM_API = "https://api-trwam.app.insysgo.pl/"
TRWAM_CHANNEL = "tv-trwam-cvk"
RADIO_URL = "https://www.radiomaryja.pl/"
CATCHUP_DAYS = 8  # the live stream window of the catch-up (the api offers 7 days back)


def _utcNow():
    # datetime.utcnow() is deprecated on Python 3.12+
    return datetime(1970, 1, 1) + timedelta(seconds=int(time.time()))


def _isoToUtc(value):
    # "2026-10-09T00:05:00+02:00" -> naive UTC datetime (None when it can not be read)
    try:
        value = ensure_str(value or "")
        base = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
        m = re.search(r"([+-])(\d\d):?(\d\d)$", value)
        if m:
            offset = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
            base = base - offset if m.group(1) == "+" else base + offset
        return base
    except Exception:
        return None


class LuxVeritatisPL(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a row
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "codename", "date", "live", "f_media")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "luxveritatis.pl", "cookie": "luxveritatis.pl.cookie"})
        self.MAIN_URL = RADIO_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/luxveritatis135.png")
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update({"Accept": "text/html"})
        self.API_HEADER = dict(self.HTTP_HEADER)
        self.API_HEADER.update({"Accept": "application/json", "Content-Type": "application/json", "X-Api-Date-Format": "iso", "X-Api-Camel-Case": "true",
                                "Accept-Language": "pl", "Origin": TRWAM_URL.rstrip("/"), "Referer": TRWAM_URL})
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("luxveritatis")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, curUrl=None):
        return CBaseHostClass.getFullUrl(self, url, curUrl).replace("&amp;", "&")

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            if cItem.get("type") in ("video", "audio"):
                if cItem.get("codename"):
                    return "video:trwam:%s" % cItem["codename"]
                url = re.sub(r"^https?://[^/]+", "", cItem.get("url", "")).rstrip("/")
                return "video:%s" % url if url else ""
            if cItem.get("category") == "trwam_episodes" and cItem.get("f_series"):
                return "folder:trwam:%s" % cItem["f_series"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") in ("video", "audio"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("LuxVeritatisPL.listMainMenu")
        MAIN_CAT_TAB = [{"category": "tv_trwam", "title": "TV Trwam", "url": TRWAM_URL, "icon": "file://" + GetIconDir("PlayerSelector/luxveritatis135.png")},
                        {"category": "radio", "title": "Radio Maryja", "url": RADIO_URL}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    # TV Trwam (InsysGo api)
    ###################################################
    def _api(self, path, post=None, version="v1"):
        params = dict(self.defaultParams)
        params["header"] = self.API_HEADER
        url = TRWAM_API + version + "/" + path
        if post is None:
            url += ("&" if "?" in url else "?") + "platformCodename=www"
        else:
            post = dict(post, platformCodename="www")
            params["raw_post_data"] = True
            post = json_dumps(post)
        sts, data = self.cm.getPage(url, params, post)
        if not sts:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    def _getTiles(self, ids):
        # id ("vod.123", "ser.4", "prg.5") -> full tile, in packets
        tiles = {}
        for idx in range(0, len(ids), 50):
            data = self._api("Tile/GetTiles", {"requestedTiles": [{"id": x} for x in ids[idx:idx + 50]]}, "v2")
            for tile in data.get("tiles", []) or []:
                tiles[ensure_str(tile.get("id", ""))] = tile
        return tiles

    def _tileIcon(self, tile):
        images = tile.get("images") or []
        if tile.get("image"):
            images = [tile["image"]] + images
        for role in ("thumbnail", "photo", "poster", "cover"):
            for img in images:
                if img.get("role") == role and img.get("url"):
                    return ensure_str(img["url"])
        return ensure_str(images[0].get("url", "")) if images else ""

    def _tileRow(self, tile):
        tileType = ensure_str(tile.get("type", ""))
        codename = ensure_str(tile.get("codename", ""))
        title = self.cleanHtmlStr(ensure_str(tile.get("title", "")))
        if not codename or not title:
            return None
        subtitle = self.cleanHtmlStr(ensure_str(tile.get("subtitle", "") or tile.get("subTitle", "") or ""))
        label = "%s - %s" % (title, subtitle) if subtitle and subtitle not in title else title
        # air time (catch-up: the programme's start) in the site's own local time, "2026-10-09T00:05:00+02:00"
        date = ensure_str((tile.get("catchupInfo") or {}).get("emissionDate", "") or tile.get("f_start", "") or tile.get("publishDate", "") or "")
        if re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d", date):
            dateTxt = "%s.%s.%s %s" % (date[8:10], date[5:7], date[:4], date[11:16])
            date = date[:10]
        else:
            dateTxt, date = "", ""
        try:
            seconds = int(tile.get("durationSeconds") or tile.get("episodeDurationInSeconds") or 0)
        except (TypeError, ValueError):
            seconds = 0
        duration = "%d:%02d" % (seconds // 60, seconds % 60) if seconds else ""
        plot = self.cleanHtmlStr(ensure_str(tile.get("description", "") or ""))
        short = self.cleanHtmlStr(ensure_str(tile.get("shortDescription", "") or ""))
        desc = [" | ".join([x for x in (dateTxt, duration, short if short != plot else "") if x]), plot]
        row = {"good_for_fav": True, "title": label, "raw_title": label, "icon": self._tileIcon(tile), "desc": "[/br]".join([x for x in desc if x]),
               "codename": codename, "date": date}
        if tileType == "ser":
            row.update({"category": "trwam_episodes", "url": TRWAM_URL + "series/" + codename, "f_series": ensure_str(tile.get("id", ""))})
        else:
            row["url"] = TRWAM_URL + ("programs/" if tileType == "prg" else "vods/") + codename
            row["title"] = normalizeMediathekTitle(label, date=date)
        return row

    def _isExpired(self, tile):
        # most videos of the api are recordings of the live channel ("catchupInfo"); their stream is a time window of
        # the live stream, which only reaches back the days of the catch-up (a year old one answers 404)
        emission = _isoToUtc((tile.get("catchupInfo") or {}).get("emissionDate", ""))
        return emission is not None and emission < _utcNow() - timedelta(days=CATCHUP_DAYS)

    def _addTileRows(self, ids, tiles=None):
        if tiles is None:
            tiles = self._getTiles(ids)
        count = 0
        for tileId in ids:
            row = self._tileRow(tiles[tileId]) if tileId in tiles and not self._isExpired(tiles[tileId]) else None
            if row is None:
                continue
            row["name"] = "category"
            if row.get("category") == "trwam_episodes":
                self.addDir(row)
            else:
                self.addVideo(row)
            count += 1
        return count

    def listTVTrwam(self, cItem):
        printDBG("LuxVeritatisPL.listTVTrwam")
        icon = "file://" + GetIconDir("PlayerSelector/luxveritatis135.png")
        self.addVideo({"name": "category", "good_for_fav": True, "title": "TV Trwam - %s" % _("Live"), "url": TRWAM_URL + "na-zywo", "codename": TRWAM_CHANNEL,
                       "live": True, "icon": icon, "desc": TRWAM_URL})
        for category, title in (("trwam_days", _("Catch-up")), ("trwam_series", _("Shows"))):
            self.addDir({"name": "category", "good_for_fav": True, "category": category, "title": title, "url": TRWAM_URL + category, "icon": icon})

    def listTVTrwamDays(self, cItem):
        # today (time of the box) back to the first day the api still has
        data = self._api("EpgTile/GetAvailableDays", {})
        first = ensure_str(data.get("from", ""))
        tz = first[19:] if re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", first) else "+02:00"
        day = datetime.now().date()
        last = day - timedelta(days=7)
        if re.match(r"\d{4}-\d\d-\d\d", first):
            last = datetime(int(first[:4]), int(first[5:7]), int(first[8:10])).date()
        while day >= last:
            self.addDir(dict(cItem, good_for_fav=False, category="trwam_day", title=day.strftime("%d.%m.%Y"), f_date=day.strftime("%Y-%m-%d"),
                             f_tz=tz, url=TRWAM_URL + "epg/" + day.strftime("%Y-%m-%d")))
            day -= timedelta(days=1)

    def listTVTrwamDay(self, cItem):
        day = cItem.get("f_date", "")
        if not re.match(r"\d{4}-\d\d-\d\d$", day):
            return
        tz = cItem.get("f_tz", "+02:00")
        nextDay = (datetime(int(day[:4]), int(day[5:7]), int(day[8:10])) + timedelta(days=1)).strftime("%Y-%m-%d")
        data = self._api("EpgTile/FilterProgramTiles", {"from": "%sT00:00:00%s" % (day, tz), "to": "%sT00:00:00%s" % (nextDay, tz), "orChannelCodenames": [TRWAM_CHANNEL]})
        now = _utcNow()
        ids = []
        starts = {}
        for item in (data.get("programs") or {}).get(TRWAM_CHANNEL, []):
            end = _isoToUtc(item.get("to", ""))
            if end is not None and end < now:  # only what was broadcast already
                tileId = ensure_str(item.get("id", ""))
                ids.append(tileId)
                starts[tileId] = ensure_str(item.get("from", ""))
        tiles = self._getTiles(ids)
        for tileId in ids:
            if tileId in tiles:
                tiles[tileId]["f_start"] = starts.get(tileId, "")
        self._addTileRows(ids, tiles)

    def listTVTrwamSeries(self, cItem):
        data = self._api("Tile/FilterTiles", {"page": 1, "limit": 100, "tileTypes": ["ser"]}, "v2")
        ids = [ensure_str(x.get("id", "")) for x in data.get("tiles", []) or []]
        self._addTileRows(ids)

    def listTVTrwamEpisodes(self, cItem):
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        data = self._api("Tile/GetSeriesDetails?id=%s" % cItem.get("f_series", ""))
        groups = data.get("episodeGroups") or []
        if not groups:
            return
        page = min(page, len(groups))
        show = self.cleanHtmlStr(ensure_str((data.get("series") or {}).get("title", "") or cItem.get("raw_title", "")))
        # the full tiles (description, catch-up date) of the episodes of a group (= page of the site); most old
        # episodes are expired recordings, so a page goes on with the next groups until it has some rows
        count = 0
        group = page
        while group <= len(groups) and group < page + 6 and count < 10:
            ids = [ensure_str(x.get("id", "")) for x in groups[group - 1].get("episodes", []) or [] if x.get("hasPlayableStream", True)]
            tiles = self._getTiles(ids)
            group += 1
            for tileId in ids:
                row = self._tileRow(tiles[tileId]) if tileId in tiles and not self._isExpired(tiles[tileId]) else None
                if row is None:
                    continue
                if show and not row["raw_title"].lower().startswith(show.lower()):
                    row["raw_title"] = "%s - %s" % (show, row["raw_title"])
                    row["title"] = normalizeMediathekTitle(row["raw_title"], date=row["date"])
                row["name"] = "category"
                self.addVideo(row)
                count += 1
        params = stripPagerKeys(dict(cItem))
        addPagingItems(self, params, page, group <= len(groups), len(groups), cItem["url"].split("?")[0] + "?page={page}", {"page": group})

    def _searchTVTrwam(self, pattern):
        data = self._api("Tile/Search", {"query": pattern, "page": 1, "limit": 50})
        ids = []
        for group in data.get("searchGroups", []) or []:
            if ensure_str(group.get("groupCodename", "")) in ("series", "vods", "programs-catchup"):
                ids.extend([ensure_str(x.get("id", "")) for x in group.get("tiles", []) or []])
        self._addTileRows(ids)

    def _getTrwamLinks(self, codename):
        data = self._api("Player/AcquireContent?codename=%s" % codename)
        hlsTab, dashTab = [], []
        for mediaFile in data.get("mediaFiles", []) or []:
            for fmt in mediaFile.get("formats", []) or []:
                url = ensure_str(fmt.get("url", ""))
                if not self.cm.isValidUrl(url) or fmt.get("protection"):
                    continue
                if fmt.get("type") == 2 or ".m3u8" in url:
                    hlsTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
                elif fmt.get("type") == 9 or ".mpd" in url:
                    dashTab.extend(getMPDLinksWithMeta(url, checkExt=False, sortWithMaxBandwidth=999999999))
        if not hlsTab and not dashTab:
            msg = ensure_str((data.get("result") or {}).get("messageCodename", ""))
            SetIPTVPlayerLastHostError(_("Content not available") + (" (%s)" % msg if msg else ""))
        return hlsTab + dashTab

    ###################################################
    # Radio Maryja (WordPress)
    ###################################################
    def listRadio(self, cItem):
        printDBG("LuxVeritatisPL.listRadio")
        desc = ""
        sts, data = self.getPage(RADIO_URL + "wp-admin/admin-ajax.php", post_data={"action": "terazNaAntenie"})
        if sts:
            try:
                data = json_loads(data)
                desc = "%s, %s[/br]%s" % (ensure_str(data.get("godz", "")), ensure_str(data.get("goscie", "")), ensure_str(data.get("opis", "")))
                desc = self.cleanHtmlStr(desc.replace("[/br]", "<br>")).strip(", ")
            except Exception:
                printExc()
        self.addAudio({"name": "category", "good_for_fav": True, "live": True, "title": "Radio Maryja - %s" % _("Live"), "desc": desc, "url": RADIO_URL + "live/", "icon": cItem.get("icon", "")})

        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenNodes(data, ("<section ", ">", "widget_nav_menu"), ("<footer", ">"))[1]
        for marker, media in (("Audio", "audio"), ("Video", "video")):
            section = self.cm.ph.getDataBeetwenNodes(data, ("<a", "<", marker), ("</ul", ">"))[1]
            idx = section.find("<ul")
            if idx == -1:
                continue
            tabItems = []
            for num, item in enumerate(self.cm.ph.getAllItemsBeetwenMarkers(section, "<a", "</a>")):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'"]+)['"]''')[0], RADIO_URL)
                title = _("All") if num == 0 else self.cleanHtmlStr(item)
                if url and title:
                    tabItems.append([title, url])
            if tabItems:
                self.addDir({"name": "category", "good_for_fav": False, "category": "list_radio_cats", "title": self.cleanHtmlStr(section[:idx]),
                             "f_items": tabItems, "f_media": media})

    def listRadioCats(self, cItem):
        for title, url in cItem.get("f_items", []):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_radio_items", "title": title, "url": url, "f_media": cItem.get("f_media", "audio")})

    def listRadioItems(self, cItem):
        printDBG("LuxVeritatisPL.listRadioItems [%s]" % cItem.get("url", ""))
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        # WordPress pages: <list>/page/N/ (search: /page/N/?s=...)
        base, sep, query = cItem["url"].replace("{", "%7B").replace("}", "%7D").partition("?")
        base = re.sub(r"/page/\d+/?$", "/", base)
        tpl = base.rstrip("/") + "/page/{page}/" + sep + query
        url = tpl.format(page=page) if page > 1 else cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, "<main", "</main>")[1]
        lastPage = self.cm.ph.getSearchGroups(data, r'''/page/(\d+)/[^'"]*['"]>&raquo;''')[0]
        lastPage = int(lastPage) if lastPage.isdigit() else 0
        hasNext = "&rsaquo;" in data
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>"):
            tmp = self.cm.ph.getDataBeetwenMarkers(item, "<header", "</header>")[1].split("</h2>", 1)
            title = self.cleanHtmlStr(tmp[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[0], r'''\shref=['"]([^'"]+)['"]''')[0], RADIO_URL)
            if not url or not title or (not cItem.get("f_media") and "/multimedia/" not in url):
                continue  # the search finds all articles of the site - only the audio / video ones are kept
            date = self.cm.ph.getSearchGroups(item, r'''datetime=['"](\d{4}-\d\d-\d\d)''')[0]
            desc = [self.cleanHtmlStr(tmp[-1]), self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "entry-content"), ("</div", ">"))[1])]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'''<img[^>]+?src=['"]([^'"]+)['"]''')[0], RADIO_URL)
            media = cItem.get("f_media", "")
            if not media:
                media = "video" if "category-video" in item.split(">", 1)[0] else "audio"
            params = {"name": "category", "good_for_fav": True, "title": normalizeMediathekTitle(title, date=date), "raw_title": title, "url": url,
                      "icon": icon, "desc": "[/br]".join([x for x in desc if x]), "date": date, "f_media": media}
            if media == "video":
                self.addVideo(params)
            else:
                self.addAudio(params)
            count += 1
        addPagingItems(self, stripPagerKeys(dict(cItem)), page, bool(count) and hasNext, lastPage, tpl)

    def _getRadioLinks(self, url):
        linksTab = []
        sts, data = self.getPage(url)
        if not sts:
            return linksTab
        content = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "entry-content"), ("<footer", ">"))[1] or data
        seen = set()
        audio = re.findall(r'''<source[^>]+src=['"]([^'"]+?\.mp3)(?:\?[^'"]*)?['"]''', content)
        audio += re.findall(r'''['"]?soundFile['"]?\s*:\s*['"]([^'"]+?\.mp3)''', content)
        audio += re.findall(r'''<a[^>]+href=['"]([^'"]+?\.mp3)(?:\?[^'"]*)?['"]''', content)
        for item in audio:
            item = self.getFullUrl(item, RADIO_URL)
            if item in seen:
                continue
            seen.add(item)
            # the mp3 host (Cloudflare) answers 403 to a player without a browser User-Agent
            linksTab.append({"name": "MP3 %s" % item.split("/")[-1], "url": strwithmeta(item, {"User-Agent": self.HTTP_HEADER["User-Agent"], "Referer": url}), "need_resolve": 0})
        videos = re.findall(r'''<iframe[^>]+src=['"]([^'"]+)['"]''', content)
        videos += re.findall(r'''href=['"](https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|live/)|youtu\.be/)[^'"]+)['"]''', content)
        for item in videos:
            item = self.getFullUrl(item.replace("&amp;", "&"), RADIO_URL)
            if item in seen or 1 != self.up.checkHostSupport(item):
                continue
            seen.add(item)
            linksTab.append({"name": self.up.getHostName(item), "url": item, "need_resolve": 1})
        return linksTab

    def _getRadioLiveLinks(self, url):
        linksTab = []
        sts, data = self.getPage(url)
        if not sts:
            return linksTab
        plsUrl = self.cm.ph.getSearchGroups(data, r'''<a[^>]+?href=['"](https?://[^'"]+?\.pls(?:\?[^'"]*?)?)['"]''')[0]
        if plsUrl:
            sts, tmp = self.getPage(plsUrl)
            if sts:
                for name, streamUrl in re.findall(r"(File[0-9]+)=(https?://\S+)", tmp):
                    linksTab.append({"name": "Radio Maryja %s" % name.replace("File", ""), "url": streamUrl.strip(), "need_resolve": 0})
        m3u8 = self.cm.ph.getSearchGroups(data, r'''<a[^>]+?href=['"](https?://[^'"]+?\.m3u8(?:\?[^'"]*?)?)['"]''')[0]
        if m3u8:
            linksTab.extend(getDirectM3U8Playlist(m3u8, checkContent=True))
        return linksTab

    ###################################################
    # search / links / INFO
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("LuxVeritatisPL.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        if searchType == "radio":
            self.listRadioItems({"name": "category", "category": "list_radio_items", "url": RADIO_URL + "?s=" + urllib_quote_plus(searchPattern)})
        else:
            self._searchTVTrwam(searchPattern)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    def getLinksForVideo(self, cItem):
        printDBG("LuxVeritatisPL.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if cItem.get("codename"):
            linksTab = self._getTrwamLinks(cItem["codename"])
        elif "radiomaryja.pl" in url and url.rstrip("/").endswith("/live"):
            linksTab = self._getRadioLiveLinks(url)
        elif "radiomaryja.pl" in url:
            linksTab = self._getRadioLinks(url)
        elif url.split("?", 1)[0].endswith(".mp3"):
            linksTab = [{"name": "MP3", "url": strwithmeta(url, {"User-Agent": self.HTTP_HEADER["User-Agent"], "Referer": RADIO_URL}), "need_resolve": 0}]  # rows of the old version
        elif 1 == self.up.checkHostSupport(url):
            linksTab = [{"name": self.up.getHostName(url), "url": url, "need_resolve": 1}]
        else:
            linksTab = []
        if not cItem.get("live"):
            linksTab = applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        return linksTab

    def getVideoLinks(self, url):
        printDBG("LuxVeritatisPL.getVideoLinks [%s]" % url)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("LuxVeritatisPL.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", cItem.get("title", ""))
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("date"):
            otherInfo["released"] = cItem["date"]
        url = cItem.get("url", "")
        if "radiomaryja.pl" in url and not cItem.get("live"):
            sts, data = self.getPage(url)
            if sts:
                def meta(name):
                    return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+property=['"]%s['"][^>]+content=['"]([^'"]*)['"]''' % name)[0])
                title = meta("og:title") or title
                text = meta("og:description") or text
                icon = meta("og:image") or icon
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("LuxVeritatisPL.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("LuxVeritatisPL.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        # RADIO MARYJA
        elif category == "radio":
            self.listRadio(self.currItem)
        elif category == "list_radio_cats":
            self.listRadioCats(self.currItem)
        elif category == "list_radio_items":
            self.listRadioItems(self.currItem)
        # TV TRWAM
        elif category == "tv_trwam":
            self.listTVTrwam(self.currItem)
        elif category == "trwam_days":
            self.listTVTrwamDays(self.currItem)
        elif category == "trwam_day":
            self.listTVTrwamDay(self.currItem)
        elif category == "trwam_series":
            self.listTVTrwamSeries(self.currItem)
        elif category == "trwam_episodes":
            self.listTVTrwamEpisodes(self.currItem)
        # SEARCH
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
        CHostBase.__init__(self, LuxVeritatisPL(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("luxveritatis")

    def withArticleContent(self, cItem):
        return cItem.get("type", "") in ("video", "audio")

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("TV Trwam", "tv"))
        searchTypesOptions.append(("Radio Maryja", "radio"))
        return searchTypesOptions
