# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - Mixcloud (mixcloud.com), new host
#   DJ mixes / radio shows from the public API (api.mixcloud.com): categories -> popular / latest,
#   search for mixes, users (their uploads) and tags. Stream urls like yt-dlp's mixcloud extractor:
#   app.mixcloud.com/graphql cloudcastLookup -> streamInfo url/hlsUrl, base64 + XOR with the public key.
#   On-demand audio: watched flag + downloaded marker (row url = the mix page), sidecar, INFO = description,
#   paging (First / Jump / Next, limit/offset of the API).
import itertools
import re
from binascii import a2b_base64

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.mixcloud.com/"


class Mixcloud(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = "https://api.mixcloud.com"
    GRAPHQL = "https://app.mixcloud.com/graphql"
    # the stream urls in streamInfo are XOR-ed with this public key (see yt-dlp MixcloudIE)
    XOR_KEY = "IFYOUWANTTHEARTISTSTOGETPAIDDONOTDOWNLOADFROMMIXCLOUD"
    LIMIT = 30
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "mc_key", "api_url")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "mixcloud", "cookie": "mixcloud.cookie"})
        self.MAIN_URL = "https://www.mixcloud.com/"
        self.DEFAULT_ICON_URL = "https://thumbnailer.mixcloud.com/unsafe/300x300/profile/c/7/f/e/b5b7-2c90-4198-8347-cccfb3964d26"
        # Cloudflare in front of app.mixcloud.com rejects a browser User-Agent that does not come with a browser TLS
        # fingerprint, a plain "Mozilla/5.0" passes (as on the api host)
        self.HEADER = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": self.MAIN_URL}
        self.defaultParams = {"header": self.HEADER}
        self.MENU = [{"category": "list_categories", "title": _("Categories")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("mixcloud")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type") == "audio":
                key = cItem.get("mc_key") or self.wfNormalizeUrlKey(cItem.get("url", ""))
                return "audio:%s" % key if key else ""
            if cItem.get("category") == "list_user" and cItem.get("url"):
                return "folder:%s" % self.wfNormalizeUrlKey(cItem["url"])
        except Exception:
            printExc()
        return ""

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, url, post=None):
        params = dict(self.defaultParams)
        if post is not None:
            params = {"header": dict(self.HEADER, **{"Content-Type": "application/json"}), "raw_post_data": True}
        sts, data = self.getPage(url, params, post)
        if not sts or not data:
            return None
        try:
            return ensure_str_deep(json_loads(data))
        except Exception:
            printExc()
        return None

    @staticmethod
    def _picture(obj):
        pics = (obj or {}).get("pictures") or {}
        return pics.get("extra_large") or pics.get("large") or pics.get("medium") or ""

    @staticmethod
    def _duration(secs):
        try:
            secs = int(secs or 0)
        except Exception:
            secs = 0
        if secs <= 0:
            return ""
        return "%d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60, secs % 60)

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        data = self._json(self.API + "/categories/")
        for cat in ((data or {}).get("data") or []):
            slug = cat.get("slug") or ""
            name = self.cleanHtmlStr(cat.get("name") or "")
            if not slug or not name:
                continue
            params = dict(cItem)
            params.update({"category": "list_category", "title": name, "slug": slug, "good_for_fav": True})
            self.addDir(params)

    def listCategory(self, cItem):
        for sort, title in (("popular", _("Popular")), ("latest", _("Latest"))):
            params = dict(cItem)
            params.update({"category": "list_sub", "title": title, "good_for_fav": False, "api_kind": "cloudcast", "page": 1,
                           "api_url": "%s/discover/%s/%s/" % (self.API, cItem.get("slug", ""), sort),
                           "url": "https://www.mixcloud.com/discover/%s/?order=%s" % (cItem.get("slug", ""), sort)})
            self.addDir(params)

    def _addCloudcast(self, cItem, cc):
        key = cc.get("key") or ""
        name = self.cleanHtmlStr(cc.get("name") or "")
        if not key or not name:
            return
        user = cc.get("user") or {}
        owner = self.cleanHtmlStr(user.get("name") or user.get("username") or "")
        date = (cc.get("created_time") or "")[:10]
        title = name
        if IsMediaNamingNormalized():
            title = normalizeMediathekTitle("%s - %s" % (owner, name) if owner and owner.lower() not in name.lower() else name, date=date)
        tags = ", ".join([self.cleanHtmlStr(t.get("name") or "") for t in (cc.get("tags") or []) if isinstance(t, dict)])
        info = [x for x in (owner, date, self._duration(cc.get("audio_length")),
                            _("%s plays") % cc.get("play_count") if cc.get("play_count") else "") if x]
        desc = " | ".join(info) + ("[/br]" + tags if tags else "")
        self.addAudio({"good_for_fav": True, "title": title, "url": cc.get("url") or ("https://www.mixcloud.com" + key),
                       "mc_key": key, "icon": self._picture(cc), "desc": desc})

    def _addUser(self, cItem, user):
        username = user.get("username") or ""
        if not username:
            return
        name = self.cleanHtmlStr(user.get("name") or username)
        count = user.get("cloudcast_count")
        params = stripPagerKeys(dict(cItem))
        params.update({"category": "list_user", "api_kind": "cloudcast", "page": 1, "title": name, "url": "https://www.mixcloud.com/%s/" % username,
                       "api_url": "%s/%s/cloudcasts/" % (self.API, urllib_quote_plus(username)),
                       "icon": self._picture(user), "good_for_fav": True,
                       "desc": (_("%s uploads") % count + "[/br]" if count else "") + self.cleanHtmlStr(user.get("biog") or "")})
        self.addDir(params)

    def _addTag(self, cItem, tag):
        key = tag.get("key") or ""
        slug = key.strip("/").split("/")[-1] if key else ""
        name = self.cleanHtmlStr(tag.get("name") or slug)
        if not slug:
            return
        params = stripPagerKeys(dict(cItem))
        params.update({"category": "list_category", "title": name, "slug": slug, "good_for_fav": True})
        self.addDir(params)

    def listApi(self, cItem):
        # every list of the API pages with limit/offset; the page number drives the request, the row url (the
        # matching mixcloud.com page + "page=N", dropped again from the watched key) is the Jump template
        page = int(cItem.get("page", 1) or 1)
        url = re.sub(r"[?&](?:limit|offset)=[^&]*", "", cItem.get("api_url", ""))
        url += "%slimit=%d&offset=%d" % ("&" if "?" in url else "?", self.LIMIT, (page - 1) * self.LIMIT)
        data = self._json(url)
        if not isinstance(data, dict):
            return
        kind = cItem.get("api_kind", "cloudcast")
        for obj in (data.get("data") or []):
            if not isinstance(obj, dict):
                continue
            if kind == "user":
                self._addUser(cItem, obj)
            elif kind == "tag":
                self._addTag(cItem, obj)
            else:
                self._addCloudcast(cItem, obj)
        base = re.sub(r"[?&]page=\d+", "", cItem.get("url", "") or self.MAIN_URL)
        tpl = base + ("&" if "?" in base else "?") + "page={page}"
        addPagingItems(self, cItem, page, bool((data.get("paging") or {}).get("next") and data.get("data")), 0, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        kind = searchType if searchType in ("cloudcast", "user", "tag") else "cloudcast"
        params = dict(cItem)
        query = urllib_quote_plus(searchPattern)
        params.update({"api_kind": kind, "api_url": "%s/search/?q=%s&type=%s" % (self.API, query, kind), "page": 1,
                       "url": "https://www.mixcloud.com/search/?q=%s&type=%s" % (query, kind)})
        self.listApi(params)

    ###################################################
    # links
    ###################################################
    def _decode(self, value):
        try:
            raw = bytearray(a2b_base64(value))
            return ensure_str(bytes(bytearray(c ^ ord(k) for c, k in zip(raw, itertools.cycle(self.XOR_KEY)))), errors="ignore")
        except Exception:
            printExc()
        return ""

    def getLinksForVideo(self, cItem):
        printDBG("Mixcloud.getLinksForVideo [%s]" % cItem.get("url", ""))
        key = cItem.get("mc_key") or re.sub(r"^https?://[^/]+", "", cItem.get("url", ""))
        parts = [urllib_unquote(p) for p in key.strip("/").split("/") if p]
        if len(parts) < 2:
            return []
        query = '{ cloudcastLookup(lookup: {username: %s, slug: %s}) { name isExclusive restrictedReason streamInfo { url hlsUrl } } }' % (
            json_dumps(parts[0]), json_dumps(parts[1]))
        data = self._json(self.GRAPHQL, json_dumps({"query": query}))
        cc = (((data or {}).get("data") or {}).get("cloudcastLookup")) if isinstance(data, dict) else None
        if not isinstance(cc, dict):
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        reason = cc.get("restrictedReason") or ""
        if reason:
            msg = {"tracklist": _("This content is not available in your region."),
                   "repeat_play": _("You have reached the play limit for this mix.")}.get(reason, _("Content not available") + " (%s)" % reason)
            SetIPTVPlayerLastHostError(msg)
            return []
        info = cc.get("streamInfo") or {}
        urlTab = []
        progressive = self._decode(info["url"]) if info.get("url") else ""
        if self.cm.isValidUrl(progressive):
            urlTab.append({"name": "M4A", "url": self.up.decorateUrl(progressive, {"User-Agent": self.HEADER["User-Agent"]}), "need_resolve": 0})
        hls = self._decode(info["hlsUrl"]) if info.get("hlsUrl") else ""
        if self.cm.isValidUrl(hls):
            urlTab.append({"name": "HLS", "url": self.up.decorateUrl(hls, {"iptv_proto": "m3u8", "User-Agent": self.HEADER["User-Agent"]}), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("This mix is only available with a Mixcloud Select subscription.") if cc.get("isExclusive") else _("No stream available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get("desc", ""))))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        key = cItem.get("mc_key", "")
        if key:
            data = self._json(self.API + key)
            if isinstance(data, dict) and data.get("name"):
                title = self.cleanHtmlStr(data.get("name"))
                text = self.cleanHtmlStr(data.get("description") or "") or text
                user = data.get("user") or {}
                if user.get("name"):
                    otherInfo["creator"] = self.cleanHtmlStr(user["name"])
                if data.get("created_time"):
                    otherInfo["released"] = data["created_time"][:10]
                dur = self._duration(data.get("audio_length"))
                if dur:
                    otherInfo["duration"] = dur
                tags = ", ".join([self.cleanHtmlStr(t.get("name") or "") for t in (data.get("tags") or []) if isinstance(t, dict)])
                if tags:
                    otherInfo["genres"] = tags
                if data.get("play_count"):
                    otherInfo["views"] = str(data["play_count"])
                icon = self._picture(data) or icon
        elif cItem.get("category") == "list_user":
            text = cItem.get("desc", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "audio" or cItem.get("category") in ("list_user", "list_category"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS + ("slug",) if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Mixcloud.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_categories":
            self.listCategories(self.currItem)
        elif category == "list_category":
            self.listCategory(self.currItem)
        elif category in ("list_sub", "list_user"):
            cItem = dict(self.currItem)
            cItem.setdefault("api_kind", "cloudcast")
            self.listApi(cItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category", "category": "list_sub"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Mixcloud(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("mixcloud")

    def getSearchTypes(self):
        # translated when asked, not at import time
        return [(_("Mixes"), "cloudcast"), (_("Users"), "user"), (_("Tags"), "tag")]

    def withArticleContent(self, cItem):
        return cItem.get("type") == "audio" or cItem.get("category") == "list_user"
