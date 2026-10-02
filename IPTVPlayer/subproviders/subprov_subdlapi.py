# -*- coding: utf-8 -*-
# subdl.com: the titles, seasons, languages and subtitle lists come from the website (no key needed),
# the official API (https://subdl.com/panel/api) is only asked with a key, when the website finds nothing.
import json
import os
import re
from Components.config import config
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import (
    CSubProviderBase,
    CBaseSubProviderClass,
)
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import (
    SEASONS,
    episodeFilters,
    langCode,
    langName,
    langSortKey,
    matchTitle,
    normalizeTitle,
    sortByEpisode,
    sortByRelease,
)
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    GetDefaultLang,
    E2ColoR,
)

Y = E2ColoR("yellow")
W = E2ColoR("white")
L = E2ColoR("lime")
C = E2ColoR("cyan")
G = E2ColoR("green")
API_URL = "https://api.subdl.com/api/v1/subtitles"
DOWNLOAD_BASE = "https://dl.subdl.com"
QUALITY_RE = re.compile(r"(BluRay|WEB-DL|WEBDL|HDTV|HDRip|DVDRip|BDRip|TVRip|CAM|WEBRip|REMUX)", re.I)
QUALITY_ORDER = ("bluray", "bdrip", "remux", "web-dl", "webdl", "webrip", "hdtv", "hdrip", "dvdrip")


def GetConfigList():
    # the API key is in the E2iPlayer settings (Subtitles)
    return []


def get_subdl_api():
    try:
        return config.plugins.iptvplayer.subdlapi.value.strip()
    except Exception:
        printExc()
        return ""


def stripColors(text):
    return re.sub(r"\\c[0-9A-Fa-f]{8}", "", text or "")


def searchQuery(title):
    # the sites' search does not like punctuation: "Mission: Impossible - Fallout" -> "Mission Impossible Fallout"
    return " ".join(re.sub(r"[^\w\s]", " ", title or "", flags=re.U).split())


def pickArchiveFile(path, exts, season, episode):
    """the subtitle file of an unpacked archive to use: the wanted episode, otherwise real subtitle formats
    before .txt / .sub; {'file_path', 'name', 'ext'} or None. Also used by subprov_subsourceapi."""
    files = []
    for root, _dirs, names in os.walk(path):
        for name in names:
            ext = name.rsplit(".", 1)[-1].lower()
            if ext in exts:
                files.append({"file_path": os.path.join(root, name), "name": name, "ext": ext})
    files.sort(key=lambda f: (f["ext"] in ("txt", "sub"), f["name"].lower()))
    files = sortByEpisode(files, season, episode, "name")
    return files[0] if files else None


def qualityOf(name):
    match = QUALITY_RE.search(name or "")
    if not match:
        return ""
    quality = match.group(1)
    return {"webdl": "WEB-DL", "bluray": "BluRay", "remux": "REMUX"}.get(quality.lower(), quality)


def qualityWeight(quality):
    quality = (quality or "").lower()
    return QUALITY_ORDER.index(quality) if quality in QUALITY_ORDER else len(QUALITY_ORDER)


class SubDLAPIProvider(CBaseSubProviderClass):
    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.MAIN_URL = "https://subdl.com/"
        self.HTTP_HEADER = self.cm.getDefaultHeader()
        self.HTTP_HEADER.update({"Referer": self.MAIN_URL})
        self.defaultParams = {"header": self.HTTP_HEADER}
        self.searchTitle, self.searchYear, self.wantedSeason, self.wantedEpisode = self.wantedInfo()
        self.pageCache = {}
        self.apiCache = {}

    def getPageData(self, url):
        if url in self.pageCache:
            return self.pageCache[url]
        sts, data = self.cm.getPage(url, dict(self.defaultParams))
        if not sts:
            return None
        self.pageCache = {url: data}
        return data

    def getApiJson(self, query):
        API_KEY = get_subdl_api()
        if not API_KEY:
            return None
        query = dict(query, api_key=API_KEY)
        sts, data = self.cm.getPage(API_URL + "?" + urllib_urlencode(query), dict(self.defaultParams))
        if not sts:
            return None
        try:
            data = json.loads(data)
        except Exception:
            printExc()
            return None
        if not data.get("status", True):
            printDBG("SubDL API error: %s" % data.get("error", data.get("message", "")))
            return None
        return data

    def addTitles(self, cItem, items):
        # the best match first, then the same title / year, titles with subtitles before empty ones
        # (subtitles_count None: not known, an API result)
        best = matchTitle(self.searchTitle, self.searchYear, [(x["name"], x["year"], x["sd_id"]) for x in items])
        wanted = normalizeTitle(self.searchTitle)
        wantTv = bool(self.wantedSeason)

        def key(x):
            return (x["sd_id"] != best, x["subtitles_count"] == 0, normalizeTitle(x["name"]) != wanted,
                    bool(self.searchYear) and x["year"] != str(self.searchYear), (x["media_type"] == "tv") != wantTv,
                    -(x["subtitles_count"] or 0))

        for item in sorted(items, key=key):
            tv = item["media_type"] == "tv"
            count = "?" if item["subtitles_count"] is None else item["subtitles_count"]
            display_title = "%s (%s%s%s) - [ %s%s%s ] - [ %s%s%s %s ]" % (
                item["name"], Y, item["year"] or "N/A", W, E2ColoR("orange" if tv else "cyan"), "TV" if tv else "MOVIE", W,
                L, count, W, _("subtitles"))
            params = dict(cItem)
            params.update({"title": display_title, "sd_id": item["sd_id"], "slug": item["slug"], "year": item["year"],
                           "media_type": item["media_type"], "category": "get_languages"})
            self.addDir(params)

    def getMovieID(self, cItem):
        printDBG("SubDLAPIProvider.getMovieID title[%s] year[%s]" % (self.searchTitle, self.searchYear))
        query = searchQuery(self.searchTitle)
        if not query:
            SetIPTVPlayerLastHostError(_("No title to search for."))
            return
        items = []
        data = self.getPageData(self.getFullUrl("/search/%s" % urllib_quote_plus(query)))
        if data:
            pattern = r'<a\s+href="/subtitle/(sd\d+)/([^"/]+)".*?<h3[^>]*>(.*?)</h3>.*?bg-(?:tvColor|movieColor)[^>]*>(tv|movie)</div>.*?(\d+)\s+subtitles'
            for sd_id, slug, title_raw, media_type, subs_count in re.findall(pattern, data, re.DOTALL | re.IGNORECASE):
                title_raw = self.cleanHtmlStr(title_raw)
                year_match = re.search(r"\((\d{4})\)", title_raw)
                items.append({"sd_id": sd_id, "slug": slug, "name": re.sub(r"\s*\(\d{4}\)\s*", "", title_raw).strip(),
                              "year": year_match.group(1) if year_match else "", "media_type": media_type.lower(),
                              "subtitles_count": int(subs_count)})
            printDBG("SubDLAPIProvider.getMovieID %d results from the website" % len(items))
        if not items:
            items = self._searchViaOfficialAPI(query)
        if items:
            self.addTitles(cItem, items)
        elif get_subdl_api():
            SetIPTVPlayerLastHostError(_("No subtitles found."))
        else:
            SetIPTVPlayerLastHostError(_("Nothing found on subdl.com.") + "\n" +
                                       _("With an API key from subdl.com (E2iPlayer settings, Subtitles) the official SubDL API is searched as well."))

    def _searchViaOfficialAPI(self, query):
        data = self.getApiJson({"film_name": query, "subs_per_page": "30"})
        if not data:
            return []
        items = []
        for res in data.get("results") or []:
            sd_id = str(res.get("sd_id") or "")
            if not sd_id or not res.get("name"):
                continue
            items.append({"sd_id": sd_id if sd_id.startswith("sd") else "sd" + sd_id,
                          "slug": res.get("slug") or re.sub(r"[^a-z0-9]+", "-", normalizeTitle(res["name"])).strip("-"),
                          "name": res["name"], "year": str(res.get("year") or ""),
                          "media_type": "tv" if res.get("type") == "tv" else "movie", "subtitles_count": None})
        printDBG("SubDLAPIProvider._searchViaOfficialAPI %d results" % len(items))
        return items

    def getPageUrl(self, cItem):
        url = self.getFullUrl("/subtitle/%s/%s" % (cItem["sd_id"], cItem["slug"]))
        if cItem.get("season_slug"):
            url += "/" + cItem["season_slug"]
        return url

    @staticmethod
    def seasonNumber(season_slug, season_name):
        # "Season 2" / "second-season" / "season-2" / "specials"; not the first digits of the name
        # ("9-1-1 Season 3", "1923 - Season 1")
        num = re.search(r"(?i)season\D*(\d+)", season_name or "") or re.search(r"(?i)season\D*(\d+)", season_slug or "")
        if num:
            return int(num.group(1))
        first = (season_slug or "").split("-")[0].lower()
        for idx, name in enumerate(SEASONS):
            if name.lower() == first:
                return idx
        num = re.search(r"(\d+)", season_slug or "")
        return int(num.group(1)) if num else 9999

    def getLanguages(self, cItem):
        printDBG("SubDLAPIProvider.getLanguages")
        if not cItem.get("sd_id") or not cItem.get("slug"):
            return
        data = self.getPageData(self.getPageUrl(cItem))
        if data and re.search(r'data-language="[^"]+"', data):
            self._extractLanguagesFromHTML(data, cItem)
            return
        if data and not cItem.get("season_slug"):
            season_pattern = r'<a\s+href="/subtitle/%s/%s/([^"]*(?:season|specials)[^"]*)"[^>]*>.*?<h3[^>]*>(.*?)</h3>' % (
                re.escape(cItem["sd_id"]), re.escape(cItem["slug"]))
            seasons = []
            for season_slug, season_name in re.findall(season_pattern, data, re.DOTALL | re.IGNORECASE):
                season_name = self.cleanHtmlStr(season_name)
                if season_slug not in [s[1] for s in seasons]:
                    seasons.append((self.seasonNumber(season_slug, season_name), season_slug, season_name))
            if seasons:
                # in season order, the season of the video first
                seasons.sort(key=lambda s: (s[0] != self.wantedSeason, s[0]))
                for _num, season_slug, season_name in seasons:
                    params = dict(cItem)
                    params.update({"season_slug": season_slug, "title": season_name, "category": "get_languages"})
                    self.addDir(params)
                return
        self._getLanguagesViaAPI(cItem)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No subtitles found."))

    def _extractLanguagesFromHTML(self, html, cItem):
        desc_parts = []
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        if h1_match:
            desc_parts.append("%s%s%s" % (Y, self.cleanHtmlStr(h1_match.group(1)), W))
        info_line_parts = []
        for label, regex in ((_("Released"), r"Released:\s*([\d\-]+)"), (_("IMDb"), r"IMDb:\s*([\d\.]+)"),
                             (_("Rated"), r"Rated:\s*([^<\n]+)"), (_("Network"), r"Network:\s*([^<\n]+)")):
            match = re.search(regex, html)
            if match:
                info_line_parts.append("%s%s:%s %s" % (Y, label, W, match.group(1).strip()))
        if info_line_parts:
            desc_parts.append(" | ".join(info_line_parts))
        story_match = re.search(r"Storyline.*?</h2>\s*(?:<div[^>]*>.*?</div>\s*)?<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
        if story_match:
            desc_parts.append("%s%s:%s %s" % (Y, _("Story"), W, self.cleanHtmlStr(story_match.group(1))))
        full_desc = "\n".join(desc_parts)
        poster_match = re.search(r'<img[^>]*src="(https://poster\.subdl\.com/poster/[^"]+)"', html)
        # the IMDb link of this title, not a "tt" number of a related title somewhere on the page
        imdb_match = re.search(r"imdb\.com/title/tt(\d+)", html)

        matches = re.findall(r'data-language="([^"]+)"[^>]*data-language-name="([^"]+)"(?:[^>]*--rows:\s*(\d+))?', html, re.IGNORECASE)
        langs = []
        for key, lang_name, rows_count in matches:
            key = key.lower()
            if key in [x[0] for x in langs]:
                continue
            lang_name = self.cleanHtmlStr(lang_name) or key.capitalize()
            langs.append((key, lang_name, langCode(lang_name) or langCode(key) or key, rows_count))
        # the user's language first, then English, then by name
        langs.sort(key=lambda x: langSortKey(x[2], GetDefaultLang()))
        for key, lang_name, lang, rows_count in langs:
            params = dict(cItem)
            params.update({"language": lang_name, "language_key": key, "lang": lang, "category": "get_subtitles",
                           "title": r"%s \c00FFFF00[ %s ]\c00FFFFFF" % (lang_name, rows_count or "?"), "desc": full_desc,
                           "icon": poster_match.group(1) if poster_match else "",
                           "imdbid": imdb_match.group(1) if imdb_match else ""})
            self.addDir(params)
        printDBG("SubDLAPIProvider._extractLanguagesFromHTML %d languages" % len(langs))

    def _apiQuery(self, cItem):
        query = {"sd_id": cItem["sd_id"].replace("sd", ""), "subs_per_page": "30"}
        season = self.seasonNumber(cItem["season_slug"], "") if cItem.get("season_slug") else 9999
        if season != 9999:
            query["season_number"] = str(season)
        return query

    def _apiSubLang(self, sub):
        return langCode(sub.get("language") or "") or langCode(sub.get("lang") or "")

    def _getLanguagesViaAPI(self, cItem):
        query = self._apiQuery(cItem)
        data = self.getApiJson(query)
        if not data:
            return
        # all languages in one answer: the subtitle list of a language is filtered from it
        subs = data.get("subtitles") or []
        self.apiCache[json.dumps(query, sort_keys=True)] = subs
        langs = {}
        for sub in subs:
            lang = self._apiSubLang(sub)
            if lang:
                langs[lang] = langs.get(lang, 0) + 1
        for lang in sorted(langs, key=lambda x: langSortKey(x, GetDefaultLang())):
            params = dict(cItem)
            params.update({"language": langName(lang), "language_key": "", "lang": lang, "category": "get_subtitles",
                           "title": r"%s \c00FFFF00[ %d ]\c00FFFFFF" % (langName(lang), langs[lang])})
            self.addDir(params)
        printDBG("SubDLAPIProvider._getLanguagesViaAPI %d languages" % len(langs))

    def getSubtitles(self, cItem):
        printDBG("SubDLAPIProvider.getSubtitles")
        subtitles = self._searchSubtitle(cItem)
        if not subtitles:
            SetIPTVPlayerLastHostError(_("No subtitles found."))
        for item in subtitles:
            self.addSubtitle(item)

    def _subtitleItem(self, cItem, sub_id, release, author, download_url):
        quality = qualityOf(release)
        display = [cItem["lang"].upper()]
        if quality:
            display.append(Y + quality + W)
        display.append(re.sub(r"(?i)\b(S\d{1,2}E\d{1,3}|season\s*\d+|episode\s*\d+)\b", lambda m: C + m.group(0) + W, release))
        if author:
            display.append(Y + "(%s)" % author + W)
        params = dict(cItem)
        params.update({"title": " | ".join(display), "release": release, "url": download_url, "sub_id": sub_id,
                       "quality": quality, "desc": (_("Author: %s") % author) if author else cItem.get("desc", "")})
        return params

    def _searchSubtitle(self, cItem):
        key = cItem.get("language_key", "")
        outList = []
        html = self.getPageData(self.getPageUrl(cItem)) if key else None
        if html:
            section = re.search(r'data-language="%s"[^>]*>(.*?)(?=data-language="|data-ai-language|$)' % re.escape(key), html, re.DOTALL | re.IGNORECASE)
            if section:
                for sub_id, block in re.findall(r'<li[^>]*data-row[^>]*data-id="(\d+)"[^>]*>(.*?)</li>', section.group(1), re.DOTALL | re.IGNORECASE):
                    dl_match = re.search(r'href="(https://dl\.subdl\.com/subtitle/[^"]+)"', block)
                    if not dl_match:
                        continue
                    title_match = re.search(r"<h4>(.*?)</h4>", block, re.DOTALL)
                    author_match = re.search(r'href="/u/([^"]+)"', block)
                    release = self.cleanHtmlStr(title_match.group(1)) if title_match else cItem["language"]
                    outList.append(self._subtitleItem(cItem, sub_id, release, author_match.group(1) if author_match else "", dl_match.group(1)))
            printDBG("SubDLAPIProvider._searchSubtitle %d subtitles from the website for [%s]" % (len(outList), key))
        if not outList:
            outList = self._searchSubtitleViaAPI(cItem)

        # the release of the video first, then the wanted episode and the season packs, then by source quality
        outList.sort(key=lambda x: qualityWeight(x.get("quality")))
        outList = sortByRelease(outList, self.releaseName(), "release")
        outList = sortByEpisode(outList, self.wantedSeason, self.wantedEpisode, "release")
        if self.wantedSeason and self.wantedEpisode:
            this_episode = episodeFilters(self.wantedSeason, self.wantedEpisode)[0]
            for item in outList:
                if this_episode.search(item["release"]):
                    item["title"] = G + "* " + W + item["title"]
        return outList

    def _searchSubtitleViaAPI(self, cItem):
        query = self._apiQuery(cItem)
        subs = self.apiCache.get(json.dumps(query, sort_keys=True))
        if subs is None:
            # NOTE: the API takes upper-case codes (EN, DE, ...); its code for pt-br could not be verified
            # (the language list is behind Cloudflare), so "pt-br" asks for "PT"
            query["languages"] = cItem["lang"].split("-")[0].upper()
            subs = (self.getApiJson(query) or {}).get("subtitles") or []
        outList = []
        for sub in subs:
            link = sub.get("url") or sub.get("link") or ""
            if self._apiSubLang(sub) != cItem["lang"] or not link:
                continue
            if not link.startswith("http"):
                link = DOWNLOAD_BASE + ("" if link.startswith("/") else "/subtitle/") + link
            sub_id = re.sub(r"\D", "", link.rsplit("/", 1)[-1].split("-")[-1])
            outList.append(self._subtitleItem(cItem, sub_id, sub.get("release_name") or sub.get("name") or cItem["language"],
                                              sub.get("author") or "", link))
        printDBG("SubDLAPIProvider._searchSubtitleViaAPI %d subtitles" % len(outList))
        return outList

    def downloadSubtitleFile(self, cItem):
        printDBG("SubDLAPIProvider.downloadSubtitleFile url[%s]" % cItem.get("url"))
        if not cItem.get("url"):
            return {}
        tmpDIR = self.downloadArchive(cItem["url"], {"header": dict(self.HTTP_HEADER)})
        if tmpDIR is None:
            return {}
        picked = pickArchiveFile(tmpDIR, self.getSupportedFormats(all=True), self.wantedSeason, self.wantedEpisode)
        if not picked:
            SetIPTVPlayerLastHostError(_("No subtitle file found in the archive."))
            return {}
        printDBG("SubDLAPIProvider.downloadSubtitleFile selected[%s]" % picked["name"])
        item = dict(cItem, file_path=picked["file_path"], ext=picked["ext"],
                    title=cItem.get("release") or stripColors(cItem.get("title", "subtitle")))
        return CBaseSubProviderClass.downloadSubtitleFile(self, item)

    def handleService(self, index, refresh=0):
        printDBG("SubDLAPIProvider.handleService start")
        CBaseSubProviderClass.handleService(self, index, refresh)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.getMovieID({"name": "category"})
        elif category == "get_languages":
            self.getLanguages(self.currItem)
        elif category == "get_subtitles":
            self.getSubtitles(self.currItem)
        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):
    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubDLAPIProvider(params))
