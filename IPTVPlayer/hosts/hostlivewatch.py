# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - LiveWatch (livewatch.top, live TV in many countries, React app on a JSON API): countries
#     (/api/countries) -> the categories that country has (with counts) -> channels (/api/channels,
#     local paging); the site lists a channel once per source (basic / cable / satellite): one row per
#     channel name here, every source is a server of it
#   - links: since 10.2026 the stream API needs a play grant: POST /api/play/ticket -> wait the
#     ticket's min_wait (the API answers 425 "too_early" before) -> POST /api/play/grant -> header
#     X-Play-Grant (valid 3 h, kept for the session); /api/stream/<id> -> proxy_url (HLS through the
#     site's proxy); only the servers whose playlist answers now are offered (the Vavoo nodes behind the
#     proxy are often down: timeouts, 502 "Erreur amont")
#   - "Arabia" is not listed: no channel played in two samples of 30 (08.10.2026: 502 / timeouts only)
#   - removed: the proxy / alternative domain options, cu.Cleantitlename, the remote mohamed_os icon
# 09.10.2026 - the site moved to livewatch.icu (livewatch.top answers every path with a 301 to the bare new
#     domain, i.e. the HTML start page instead of JSON): new domain; a redirect to another domain is
#     followed once (API path kept), any other non-JSON answer gives a clear message instead of a traceback
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://livewatch.icu/"


PAGE_SIZE = 100
SKIP_COUNTRIES = ("Arabia",)
CHECK_TIMEOUT = 10  # seconds for the playlist check of a server (a dead node does not answer at all)
GRANT_TRIES = 4


def _naturalKey(name):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


class LiveWatch(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "livewatch", "cookie": "livewatch.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/livewatch135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.channelCache = {}
        self.grant = ("", 0)

    ###################################################
    # helpers
    ###################################################
    def _params(self, **header):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="application/json, text/plain, */*", Referer=self.MAIN_URL, Origin=self.MAIN_URL[:-1])
        params["header"].update(header)
        return params

    def _api(self, path, post=None, **header):
        params = self._params(**header)
        if post is not None:
            params["raw_post_data"] = True
            params["header"]["Content-Type"] = "application/json"
            post = json_dumps(post)
        for _try in range(2):
            data = self.cm.getPage(self.getFullUrl("/api/" + path), params, post)[1]
            code = self.cm.meta.get("status_code", 0)
            data = (data or "").strip()
            if data[:1] in ("{", "["):
                try:
                    return code, json_loads(data)
                except Exception:
                    printExc()
                    break
            # domain move: the old domain redirects every path to the bare new domain (HTML start page)
            finalUrl = self.cm.meta.get("url", "") or ""
            newDomain = self.cm.getBaseUrl(finalUrl) if finalUrl.startswith("http") else ""
            if _try or not newDomain or self.cm.getBaseUrl(self.MAIN_URL) == newDomain:
                break
            printDBG("LiveWatch: site moved to %s" % newDomain)
            self.MAIN_URL = newDomain
            params = self._params(**header)
            if post is not None:
                params["raw_post_data"] = True
                params["header"]["Content-Type"] = "application/json"
        if data or code:
            printDBG("LiveWatch: no JSON from /api/%s (HTTP %s): %s" % (path, code, data[:200]))
            SetIPTVPlayerLastHostError(_("The site did not answer with data (HTTP %s). It may be down or have moved.") % code)
        return code, {}

    def _getGrant(self):
        # play grant of the site (anonymous "ad" tier): ticket -> min_wait -> grant, valid expires_in seconds
        value, expires = self.grant
        if value and expires - time.time() > 120:
            return value
        ticket = self._api("play/ticket", {})[1]
        if not ticket.get("ticket"):
            return ""
        wait = float(ticket.get("min_wait", 2))
        for _try in range(GRANT_TRIES):
            time.sleep(min(wait, 5))  # the API refuses the grant before min_wait / retry_after (425 too_early)
            code, data = self._api("play/grant", {"ticket": ticket["ticket"]})
            if data.get("grant"):
                self.grant = (data["grant"], time.time() + int(data.get("expires_in", 3600)))
                return data["grant"]
            if code != 425:
                break
            wait = float(data.get("retry_after", 1)) + 0.2
        return ""

    def _channels(self, country):
        if country not in self.channelCache:
            data = self._api("channels?country=%s&category=&limit=0" % urllib_quote(country))[1]
            self.channelCache[country] = [c for c in data.get("channels") or [] if isinstance(c, dict) and c.get("id") and c.get("name")]
        return self.channelCache[country]

    def _icon(self, logo):
        logo = (logo or "").strip()
        if logo.startswith("http"):
            return logo
        return self.getFullIconUrl(logo) if logo else self.DEFAULT_ICON_URL

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        data = self._api("countries")[1]
        for country in sorted(data.get("countries") or []):
            if country in SKIP_COUNTRIES:
                continue
            self.addDir({"name": "category", "category": "lw_country", "title": country, "country": country, "good_for_fav": True})

    def listCategories(self, cItem):
        channels = self._channels(cItem["country"])
        names = set(c["name"] for c in channels)
        self.addDir({"name": "category", "category": "lw_list", "title": "%s (%d)" % (_("All"), len(names)), "country": cItem["country"], "genre": "", "good_for_fav": True})
        counts = {}
        for channel in channels:
            for genre in channel.get("categories") or []:
                counts.setdefault(genre, set()).add(channel["name"])
        for genre in sorted(counts):
            self.addDir({"name": "category", "category": "lw_list", "title": "%s (%d)" % (genre, len(counts[genre])), "country": cItem["country"], "genre": genre, "good_for_fav": True})

    def listChannels(self, cItem):
        page = cItem.get("page", 1)
        genre = cItem.get("genre", "")
        rows = {}
        for channel in self._channels(cItem["country"]):
            if genre and genre not in (channel.get("categories") or []):
                continue
            row = rows.setdefault(channel["name"], {"name": "category", "category": "lw_channel", "good_for_fav": True, "title": channel["name"],
                                                    "country": cItem["country"], "icon": "", "sources": [], "genres": []})
            row["sources"].append({"id": channel["id"], "source": channel.get("source") or "", "quality": channel.get("quality") or ""})
            row["genres"] = sorted(set(row["genres"]) | set(channel.get("categories") or []))
            if not row["icon"] and channel.get("logo"):
                row["icon"] = self._icon(channel["logo"])
        names = sorted(rows, key=_naturalKey)
        lastPage = max(1, (len(names) + PAGE_SIZE - 1) // PAGE_SIZE)
        for name in names[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
            row = rows[name]
            row["icon"] = row["icon"] or self.DEFAULT_ICON_URL
            row["desc"] = " | ".join("%s%s:%s %s" % (E2ColoR("yellow"), label, E2ColoR("white"), value) for label, value in self._info(row))
            self.addVideo(row)
        addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def _info(self, row):
        servers = ", ".join(" ".join(x for x in (s["source"], s["quality"]) if x) for s in row.get("sources", []))
        return [(label, value) for label, value in ((_("Country"), row.get("country", "")), (_("Genre"), ", ".join(row.get("genres", []))),
                                                    (_("Server"), servers)) if value]

    ###################################################
    # links
    ###################################################
    def _streamUrl(self, channelId, grant):
        data = self._api("stream/%s?embed=1" % channelId, None, **{"X-Play-Grant": grant, "Referer": self.getFullUrl("/embed/" + channelId)})[1]
        return self.getFullUrl(data["proxy_url"]) if data.get("proxy_url") else ""

    def _hlsMeta(self, url):
        return strwithmeta(url, {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER["User-Agent"],
                                 "Referer": self.MAIN_URL, "Origin": self.MAIN_URL[:-1]})

    def getLinksForVideo(self, cItem):
        printDBG("LiveWatch.getLinksForVideo [%s]" % cItem.get("title", ""))
        grant = self._getGrant()
        urltab = []
        for source in cItem.get("sources", []) if grant else []:
            url = self._streamUrl(source["id"], grant)
            if not url:
                continue
            # dead Vavoo node: no answer / 502 / a bare url instead of a playlist
            params = self._params()
            params["timeout"] = CHECK_TIMEOUT
            sts, data = self.cm.getPage(url, params)
            if not sts or "#EXTM3U" not in data:
                printDBG("LiveWatch: %s not answering" % source["id"])
                continue
            name = " ".join(x for x in (source.get("source", "").capitalize(), source.get("quality", "")) if x) or _("Server")
            urltab.append({"name": "%d. %s" % (len(urltab) + 1, name), "url": strwithmeta(url, {"channel_id": source["id"]}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def getVideoLinks(self, videoUrl):
        printDBG("LiveWatch.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = getDirectM3U8Playlist(self._hlsMeta(str(videoUrl)), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        channelId = videoUrl.meta.get("channel_id", "") if hasattr(videoUrl, "meta") else ""
        if not links and channelId:
            # the proxy token of the link list has expired: a fresh one
            url = self._streamUrl(channelId, self._getGrant())
            links = getDirectM3U8Playlist(self._hlsMeta(url), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999) if url else []
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        lines = [cItem.get("title", "")] + ["%s: %s" % row for row in self._info(cItem)]
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": "[/br]".join(lines), "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("LiveWatch.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if refresh or name is None:
            self.channelCache = {}
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "lw_country":
            self.listCategories(self.currItem)
        elif category == "lw_list":
            self.listChannels(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, LiveWatch(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "lw_channel"
