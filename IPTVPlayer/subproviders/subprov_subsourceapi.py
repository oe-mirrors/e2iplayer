# -*- coding: utf-8 -*-
#########################################################
# Subsource.net subtitle provider for e2iplayer
# Created By : popking (odem2014)
#
# With an API key (E2iPlayer settings) the official API (api.subsource.net/api/v1) is used, without one
# the JSON API of the website (api.subsource.net/v1): search, subtitle lists, download token, archive.
#########################################################
import json
import re
from Components.config import config
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import (
    TranslateTXT as _,
    SetIPTVPlayerLastHostError,
)
from Plugins.Extensions.IPTVPlayer.components.isubprovider import (
    CSubProviderBase,
    CBaseSubProviderClass,
)
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import (
    langCode,
    langSortKey,
    matchTitle,
    normalizeTitle,
    releaseScore,
    sortByEpisode,
    sortByRelease,
)
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.subproviders.subprov_subdlapi import pickArchiveFile, searchQuery
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    GetDefaultLang,
)


def GetConfigList():
    # the API key is in the E2iPlayer settings (Subtitles)
    return []


def get_subsource_api():
    """Return SubSource API key"""
    try:
        return config.plugins.iptvplayer.subsourceapi.value.strip()
    except Exception:
        printExc()
        return ""


API_URL = "https://api.subsource.net/api/v1/"  # official, with X-API-Key
WEB_API_URL = "https://api.subsource.net/v1/"  # the website's own API, no key


#########################################################
# PROVIDER IMPLEMENTATION
#########################################################


class SubsourceAPIProvider(CBaseSubProviderClass):
    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.MAIN_URL = "https://subsource.net/"
        self.HTTP_HEADER = self.cm.getDefaultHeader()
        self.HTTP_HEADER.update({"Accept": "application/json, text/plain, */*", "Origin": "https://subsource.net",
                                 "Referer": self.MAIN_URL})
        self.searchTitle, self.searchYear, self.wantedSeason, self.wantedEpisode = self.wantedInfo()
        self.subsCache = {}
        self.apiCache = {}

    def getJson(self, url, post_data=None, apiKey=""):
        params = {"header": dict(self.HTTP_HEADER)}
        if apiKey:
            params["header"]["X-API-Key"] = apiKey
        if post_data is not None:
            params["header"]["Content-Type"] = "application/json"
            params["raw_post_data"] = True
            post_data = json.dumps(post_data)
        sts, data = self.cm.getPage(url, params, post_data)
        if not sts:
            printDBG("SubsourceAPIProvider.getJson failed [%s]" % url)
            return None
        try:
            data = json.loads(data)
        except Exception:
            printExc()
            return None
        return data if isinstance(data, dict) else None

    def releaseOf(self, releases):
        """(title, other releases) of a subtitle: of several release names the one that fits the video best,
        without any the searched title"""
        if not isinstance(releases, (list, tuple)):
            releases = [releases]
        releases = [r.strip() for r in releases if isinstance(r, str) and r.strip()]
        if not releases:
            return ("%s (%s)" % (self.searchTitle, self.searchYear) if self.searchYear else self.searchTitle), []
        wanted = self.releaseName()
        best = max(releases, key=lambda r: releaseScore(r, wanted))  # the first one on a tie
        return best, [r for r in releases if r != best]

    def addTitles(self, cItem, items):
        # items: (title, year, is series, item params); the best match first, then exact titles / the same year
        best = matchTitle(self.searchTitle, self.searchYear, [(x[0], x[1], idx) for idx, x in enumerate(items)])
        wanted = normalizeTitle(self.searchTitle)
        order = sorted(range(len(items)), key=lambda idx: (idx != best, normalizeTitle(items[idx][0]) != wanted,
                                                           bool(self.searchYear) and items[idx][1] != str(self.searchYear),
                                                           items[idx][2] != bool(self.wantedSeason), idx))
        for idx in order:
            title, year, series, item = items[idx]
            params = dict(cItem)
            params.update(item)
            params["title"] = "%s (%s)%s" % (title, year or "N/A", " [%s]" % _("TV series") if series else "")
            self.addDir(params)

    #########################################################
    # without key: the website's API
    #########################################################
    def webSearch(self, cItem):
        query = searchQuery(self.searchTitle)
        if not query:
            return False
        data = self.getJson(WEB_API_URL + "movie/search", {"query": query, "includeSeasons": True, "limit": 50})
        if data is None:
            return False
        items = []
        for res in data.get("results") or []:
            link = (res.get("link") or "").strip("/")
            if not link or not res.get("title"):
                continue
            series = res.get("type") == "tvseries"
            item = {"web": True, "link": link.split("/", 1)[-1], "series": series, "seasons": res.get("seasons") or [],
                    "icon": res.get("poster") or "", "category": "web_seasons" if series else "web_languages"}
            items.append((res["title"], str(res.get("releaseYear") or ""), series, item))
        printDBG("SubsourceAPIProvider.webSearch %d results" % len(items))
        self.addTitles(cItem, items)
        return True

    def webSeasons(self, cItem):
        def collect(entries):
            # "/subtitles/breaking-bad/season=2" -> "breaking-bad/season-2"
            found = []
            for season in entries or []:
                num = season.get("season") if isinstance(season, dict) else None
                try:
                    found.append((int(num), "%s/season-%s" % (cItem["link"], num)))
                except (TypeError, ValueError):
                    continue
            return found

        seasons = collect(cItem.get("seasons"))
        if not seasons:
            data = self.getJson(WEB_API_URL + "series/" + urllib_quote(cItem["link"]))
            seasons = collect((data or {}).get("seasons"))
        seasons.sort(key=lambda s: (s[0] != self.wantedSeason, s[0]))
        for num, link in seasons:
            params = dict(cItem)
            params.update({"title": _("Season %s") % num if num else _("Specials"), "link": link, "category": "web_languages"})
            self.addDir(params)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No subtitles found."))

    def webSubtitles(self, link):
        if link not in self.subsCache:
            data = self.getJson(WEB_API_URL + "subtitles/" + urllib_quote(link))
            if data is None:
                return None
            self.subsCache = {link: data.get("subtitles") or []}
        return self.subsCache[link]

    def webLanguages(self, cItem):
        subs = self.webSubtitles(cItem["link"])
        langs = {}
        for sub in subs or []:
            key = sub.get("language") or ""
            if key:
                langs[key] = langs.get(key, 0) + 1
        items = []
        for key, count in langs.items():
            lang = langCode(key.replace("_", " ")) or key
            items.append((langSortKey(lang, GetDefaultLang()), -count, key, lang))
        for _o, count, key, lang in sorted(items):
            params = dict(cItem)
            params.update({"title": "%s [%d]" % (key.replace("_", " ").title(), -count), "language_key": key, "lang": lang,
                           "category": "web_subtitles"})
            self.addDir(params)
        if not items:
            SetIPTVPlayerLastHostError(_("No subtitles found."))

    def webSubtitlesList(self, cItem):
        outList = []
        for sub in self.webSubtitles(cItem["link"]) or []:
            if sub.get("language") != cItem["language_key"] or not sub.get("link"):
                continue
            release, others = self.releaseOf(sub.get("release_info"))
            desc = list(others)
            if sub.get("uploader_displayname"):
                desc.append(_("Author: %s") % sub["uploader_displayname"])
            if sub.get("hearing_impaired"):
                desc.append(_("Hearing impaired"))
            if sub.get("caption") and sub["caption"].strip().lower() != "no caption":
                desc.append(sub["caption"])
            params = dict(cItem)
            params.update({"title": "[%s] %s" % (cItem["lang"], release), "release": release, "sub_link": sub["link"],
                           "sub_id": str(sub.get("id") or ""), "desc": "[/br]".join(desc)})
            outList.append(params)
        self.addSubtitles(outList)

    def webDownloadUrl(self, cItem):
        data = self.getJson(WEB_API_URL + "subtitle/" + urllib_quote(cItem["sub_link"]))
        sub = (data or {}).get("subtitle") or {}
        if not sub.get("download_token"):
            return "", ""
        imdb = re.search(r"tt(\d+)", json.dumps((data.get("movie") or {}).get("source_data") or {}))
        return WEB_API_URL + "subtitle/download/" + sub["download_token"], imdb.group(1) if imdb else ""

    #########################################################
    # with key: the official API
    #########################################################
    def apiSearch(self, cItem, apiKey):
        query = searchQuery(self.searchTitle)
        data = None
        for year in ([self.searchYear, ""] if self.searchYear else [""]):
            query_params = {"searchType": "text", "q": query, "type": "all"}
            if year:
                query_params["year"] = year
            data = self.getJson(API_URL + "movies/search?" + urllib_urlencode(query_params), apiKey=apiKey)
            if data is None:
                printDBG("SubsourceAPIProvider.apiSearch: no answer / key not accepted, using the website's API")
                return False
            if data.get("success") and data.get("data"):
                break
        if data is None or not data.get("success"):
            return False
        items = []
        for res in data.get("data") or []:
            if not res.get("movieId"):
                continue
            item = {"web": False, "movieId": res["movieId"], "category": "api_languages"}
            items.append((res.get("title", ""), str(res.get("releaseYear") or ""), res.get("type") in ("tvseries", "series", "tv"), item))
        self.addTitles(cItem, items)
        return True

    def apiSubtitles(self, movieId, apiKey, language=""):
        # one request for all languages (cached), the list of one language is filtered from it
        if movieId not in self.apiCache:
            query = {"movieId": movieId, "limit": 500, "sort": "newest"}
            data = self.getJson(API_URL + "subtitles?" + urllib_urlencode(query), apiKey=apiKey)
            if not data or not data.get("success"):
                return []
            self.apiCache = {movieId: data.get("data") or []}
        subs = self.apiCache[movieId]
        if language:
            subs = [sub for sub in subs if (sub.get("language") or "").lower() == language]
        return subs

    def apiLanguages(self, cItem, apiKey):
        langs = {}
        for sub in self.apiSubtitles(cItem["movieId"], apiKey):
            key = (sub.get("language") or "").lower()
            if key:
                langs[key] = langs.get(key, 0) + 1
        for key in sorted(langs, key=lambda k: (langSortKey(langCode(k.replace("_", " ")) or k, GetDefaultLang()), -langs[k])):
            params = dict(cItem)
            params.update({"title": "%s [%d]" % (key.replace("_", " ").title(), langs[key]), "language_key": key,
                           "lang": langCode(key.replace("_", " ")) or key, "category": "api_subtitles"})
            self.addDir(params)
        if not langs:
            SetIPTVPlayerLastHostError(_("No subtitles found."))

    def apiSubtitlesList(self, cItem, apiKey):
        outList = []
        for sub in self.apiSubtitles(cItem["movieId"], apiKey, cItem["language_key"]):
            uploader = ((sub.get("contributors") or [{}])[0]).get("displayname", "")
            # one entry per subtitle: the release name that fits the video best, the others in the description
            release, others = self.releaseOf(sub.get("releaseInfo"))
            desc = list(others)
            if uploader:
                desc.append(_("Author: %s") % uploader)
            params = dict(cItem)
            params.update({"title": "[%s] %s" % (cItem["lang"], release), "release": release, "sub_id": str(sub.get("subtitleId") or ""),
                           "desc": "[/br]".join(desc)})
            outList.append(params)
        self.addSubtitles(outList)

    #########################################################
    # common
    #########################################################
    def addSubtitles(self, outList):
        outList = sortByRelease(outList, self.releaseName(), "release")
        outList = sortByEpisode(outList, self.wantedSeason, self.wantedEpisode, "release")
        for params in outList:
            self.addSubtitle(params)
        if not outList:
            SetIPTVPlayerLastHostError(_("No subtitles found."))

    def downloadSubtitleFile(self, cItem):
        printDBG("SubsourceAPIProvider.downloadSubtitleFile")
        imdbid = ""
        params = {"header": dict(self.HTTP_HEADER)}
        if cItem.get("web"):
            url, imdbid = self.webDownloadUrl(cItem)
        else:
            url = API_URL + "subtitles/%s/download" % cItem.get("sub_id")
            params["header"]["X-API-Key"] = get_subsource_api()
        if not url:
            SetIPTVPlayerLastHostError(_("Failed to get the download link."))
            return {}
        tmpDIR = self.downloadArchive(url, params)
        if tmpDIR is None:
            return {}
        picked = pickArchiveFile(tmpDIR, self.getSupportedFormats(all=True), self.wantedSeason, self.wantedEpisode)
        if not picked:
            SetIPTVPlayerLastHostError(_("No subtitle file found in the archive."))
            return {}
        printDBG("SubsourceAPIProvider.downloadSubtitleFile selected[%s]" % picked["name"])
        item = dict(cItem, file_path=picked["file_path"], ext=picked["ext"], imdbid=imdbid,
                    title=cItem.get("release") or cItem.get("title", "subtitle"))
        return CBaseSubProviderClass.downloadSubtitleFile(self, item)

    def handleService(self, index, refresh=0):
        printDBG("handleService start")

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        apiKey = get_subsource_api()

        if name is None:
            cItem = {"name": "category"}
            if not self.searchTitle:
                SetIPTVPlayerLastHostError(_("No title to search for."))
            # an invalid / expired key: the website's API
            elif not (apiKey and self.apiSearch(cItem, apiKey)) and not self.webSearch(cItem):
                SetIPTVPlayerLastHostError(_("subsource.net does not answer.") + "\n" +
                                           _("An API key from subsource.net can be entered in the E2iPlayer settings (Subtitles)."))
            elif not self.currList:
                SetIPTVPlayerLastHostError(_("No subtitles found."))
        elif category == "web_seasons":
            self.webSeasons(self.currItem)
        elif category == "web_languages":
            self.webLanguages(self.currItem)
        elif category == "web_subtitles":
            self.webSubtitlesList(self.currItem)
        elif category == "api_languages":
            self.apiLanguages(self.currItem, apiKey)
        elif category == "api_subtitles":
            self.apiSubtitlesList(self.currItem, apiKey)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


#########################################################
# ENTRY POINT FOR E2IPLAYER
#########################################################


class IPTVSubProvider(CSubProviderBase):
    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubsourceAPIProvider(params))
