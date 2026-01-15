# -*- coding: utf-8 -*-
# Last modified: 29/12/2025
# goals Host (Created By Dr HYTHAM MAHMOUD)

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

import re

try:
    import json
except Exception:
    json = None


def gettytul():
    return "Goals.Zone (API) + Streamff(CDN mp4) + Reddit(HLS) + Streamain + Streamusk + Streamin"


class GoalsZoneAPI(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "goalszoneapi", "cookie": "goalszoneapi.cookie"})

        self.MAINURL = "https://gogz.meneses.pt/"
        self.API_BASE = "https://gogz.meneses.pt/api/"
        self.LIMIT = 50

        # url for default icon
        self.DEFAULT_ICON_URL = "https://h.top4top.io/p_3650w3uf91.png"

        self.UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        self.HEADER = {
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.7",
            "Connection": "keep-alive",
            "Referer": self.MAINURL,
        }
        self.defaultParams = {"header": self.HEADER}

        # Streamusk
        self.STREAMUSK_ORIGIN = "https://www.streamusk.com"
        self.STREAMUSK_CDN = "https://d3ctycp5ce1kgh.cloudfront.net"

        # Streamff (direct mp4 on CDN)
        self.STREAMFF_ORIGIN = "https://streamff.com"
        self.STREAMFF_CDN = "https://cdn.streamff.one"

        # Reddit
        self.REDDIT_ORIGIN = "https://www.reddit.com"
        self.REDDIT_REFERER = "https://www.reddit.com/"

        # Streamin
        self.STREAMIN_ORIGIN = "https://streamin.me"
        self.STREAMIN_REFERER = "https://streamin.me/"

        self.cacheLinks = {}

    # ---------- helpers ----------

    def safeUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        try:
            return self.cm.urlEncodeSafe(url)
        except Exception:
            return url

    def unescapeUrl(self, u):
        u = (u or "").strip()
        if not u:
            return u
        try:
            from html import unescape as htmlunescape

            u = htmlunescape(u)
        except Exception:
            pass
        u = u.replace("\\/", "/")
        u = u.replace("&amp;", "&")
        return u

    def getPage(self, url, addParams=None, postdata=None):
        params = dict(self.defaultParams)
        if addParams:
            try:
                params.update(addParams)
            except Exception:
                pass
        try:
            return self.cm.getPage(self.safeUrl(url), params, postdata)
        except Exception:
            printExc()
        return False, None

    def getJson(self, url):
        sts, data = self.getPage(url)
        if not sts or not data or json is None:
            return False, None
        try:
            return True, json.loads(data)
        except Exception:
            printExc()
        return False, None

    def _formatMatchTitle(self, it):
        home = (it.get("home_team") or {}).get("name") or ""
        away = (it.get("away_team") or {}).get("name") or ""
        score = it.get("score") or ""
        dt = it.get("datetime") or ""
        t = "%s vs %s" % (home, away)
        if score:
            t += " [%s]" % score
        if dt:
            t += " - %s" % dt
        return t.strip()

    # ---------- Streamff helpers ----------

    def _streamffIdFromUrl(self, url):
        m = re.search(r"https?://(?:www\.)?streamff\.(?:com|link)/v/([A-Za-z0-9]+)", url)
        return (m.group(1) if m else "").strip()

    # ---------- Reddit helpers ----------

    def _redditIdFromVReddit(self, url):
        m = re.search(r"https?://v\.redd\.it/([A-Za-z0-9]+)", url)
        return (m.group(1) if m else "").strip()

    def _redditExtractHlsFromHtml(self, html):
        html = html or ""
        m = re.search(r'(https?://v\.redd\.it/[A-Za-z0-9]+/HLSPlaylist\.m3u8[^"\']*)', html, re.IGNORECASE)
        if m:
            return self.safeUrl(self.unescapeUrl(m.group(1)))
        return ""

    # ---------- Streamin helpers ----------

    def _absStreaminUrl(self, u):
        u = (u or "").strip()
        if not u:
            return ""
        if u.startswith("http://") or u.startswith("https://"):
            return u
        if u.startswith("/"):
            try:
                from urllib.parse import urljoin

                return urljoin(self.STREAMIN_ORIGIN + "/", u)
            except Exception:
                return self.STREAMIN_ORIGIN + u
        return u

    def _extractStreaminMp4FromHtml(self, html):
        html = html or ""
        u = self.cm.ph.getSearchGroups(html, r"""<source[^>]+src=["']([^"']+\.mp4[^"']*)["']""")[0]
        if u:
            u = self.safeUrl(self.unescapeUrl(u)).split("#", 1)[0]
            return self._absStreaminUrl(u)

        u = self.cm.ph.getSearchGroups(html, r"""og:video:secure_url["']\s+content=["']([^"']+)["']""")[0]
        if u:
            u = self.safeUrl(self.unescapeUrl(u)).split("#", 1)[0]
            return self._absStreaminUrl(u)

        return ""

    def _extractStreaminMirrors(self, html):
        """
        Extract mirrors from <div data-src="...">NAME</div> and REMOVE Fire + Metal.
        Fire:  c-cdn.streamin.top
        Metal: downloader.disk.yandex.ru
        """
        html = html or ""
        it = re.finditer(r"""<div[^>]+data-src\s*=\s*["']([^"']+)["'][^>]*>([^<]+)</div>""", html, re.IGNORECASE)

        out = []
        seen = {}

        for m in it:
            url = self.safeUrl(self.unescapeUrl(m.group(1))).strip()
            name = (m.group(2) or "").strip()

            if not url:
                continue

            url = url.split("#", 1)[0]
            url = self._absStreaminUrl(url)

            # remove Fire + Metal
            if ("c-cdn.streamin.top/" in url) or ("downloader.disk.yandex.ru/" in url):
                continue

            if not name:
                name = "mirror"

            key = name + "||" + url
            if key in seen:
                continue
            seen[key] = True

            out.append({"name": name, "url": url})

        # fallback: data-src بدون أسماء (مع نفس الفلترة)
        if not out:
            urls = re.findall(r"""data-src\s*=\s*["']([^"']+)["']""", html, re.IGNORECASE)
            for idx, u in enumerate(urls):
                u = self.safeUrl(self.unescapeUrl(u)).strip()
                if not u:
                    continue
                u = u.split("#", 1)[0]
                u = self._absStreaminUrl(u)

                if ("c-cdn.streamin.top/" in u) or ("downloader.disk.yandex.ru/" in u):
                    continue

                if u in seen:
                    continue
                seen[u] = True
                out.append({"name": "mirror %d" % (idx + 1), "url": u})

        return out

    # ---------- main menu ----------

    def listMainMenu(self, cItem):
        tab = [
            {"name": "category", "category": "matches", "title": "Latest matches", "url": self.API_BASE + "matches/?limit=%d&offset=0&format=json" % self.LIMIT, "offset": 0, "icon": self.DEFAULT_ICON_URL},
            {"name": "category", "category": "teams", "title": "Teams", "url": self.API_BASE + "teams/?limit=%d&offset=0&format=json" % self.LIMIT, "offset": 0, "icon": self.DEFAULT_ICON_URL},
        ] + self.searchItems()
        self.listsTab(tab, cItem)

    # ---------- latest matches ----------

    def listLatestMatches(self, cItem):
        sts, j = self.getJson(cItem.get("url", ""))
        if not sts or not isinstance(j, list) or len(j) == 0:
            self.addDir({"name": "category", "category": "noop", "title": "No matches data", "icon": self.DEFAULT_ICON_URL})
            return

        for it in j:
            try:
                mslug = (it.get("slug") or "").strip()
                if not mslug:
                    continue
                icon = ((it.get("home_team") or {}).get("logo_file") or "").strip()
                icon = icon or self.DEFAULT_ICON_URL
                self.addDir({"name": "category", "category": "match_videos", "title": self._formatMatchTitle(it) or mslug, "match_slug": mslug, "icon": icon, "goodforfav": True})
            except Exception:
                printExc()

        offset = int(cItem.get("offset", 0) or 0)
        nextOffset = offset + self.LIMIT
        nextUrl = self.API_BASE + "matches/?limit=%d&offset=%d&format=json" % (self.LIMIT, nextOffset)
        self.addDir({"name": "category", "category": "matches_next", "title": "Next page", "url": nextUrl, "offset": nextOffset, "icon": self.DEFAULT_ICON_URL})

    # ---------- teams ----------

    def listTeams(self, cItem):
        sts, j = self.getJson(cItem.get("url", ""))
        if not sts or not isinstance(j, list):
            self.addDir({"name": "category", "category": "noop", "title": "No data received", "icon": self.DEFAULT_ICON_URL})
            return

        offset = int(cItem.get("offset", 0) or 0)
        nextOffset = offset + self.LIMIT

        for it in j:
            try:
                name = (it.get("name") or "").strip()
                slug = (it.get("slug") or "").strip()
                icon = (it.get("logo_file") or "").strip()
                icon = icon or self.DEFAULT_ICON_URL
                if not name or not slug:
                    continue
                self.addDir({"name": "category", "category": "team_matches", "title": name, "team_slug": slug, "icon": icon, "goodforfav": True})
            except Exception:
                printExc()

        nextUrl = self.API_BASE + "teams/?limit=%d&offset=%d&format=json" % (self.LIMIT, nextOffset)
        self.addDir({"name": "category", "category": "teams_next", "title": "Next page", "url": nextUrl, "offset": nextOffset, "icon": self.DEFAULT_ICON_URL})

    def listTeamMatches(self, cItem):
        slug = (cItem.get("team_slug") or "").strip()
        if not slug:
            self.addDir({"name": "category", "category": "noop", "title": "Missing team slug", "icon": self.DEFAULT_ICON_URL})
            return

        url = self.API_BASE + "teams/%s?format=json" % slug
        sts, teamObj = self.getJson(url)
        if not sts or not isinstance(teamObj, dict):
            self.addDir({"name": "category", "category": "noop", "title": "Failed to load team: %s" % slug, "icon": self.DEFAULT_ICON_URL})
            return

        matches = teamObj.get("matches") or []
        if not isinstance(matches, list) or len(matches) == 0:
            self.addDir({"name": "category", "category": "noop", "title": "No matches for this club", "icon": self.DEFAULT_ICON_URL})
            return

        def dt_key(x):
            return (x.get("datetime") or "").strip()

        try:
            matches = sorted(matches, key=dt_key, reverse=True)
        except Exception:
            pass

        teamIcon = (teamObj.get("logo_file") or "").strip()
        teamIcon = teamIcon or self.DEFAULT_ICON_URL

        for it in matches:
            try:
                mslug = (it.get("slug") or "").strip()
                if not mslug:
                    continue
                icon = ((it.get("home_team") or {}).get("logo_file") or teamIcon or "").strip()
                icon = icon or self.DEFAULT_ICON_URL
                self.addDir({"name": "category", "category": "match_videos", "title": self._formatMatchTitle(it) or mslug, "match_slug": mslug, "icon": icon, "goodforfav": True})
            except Exception:
                printExc()

    # ---------- search ----------

    def listSearchResult(self, cItem, searchPattern, searchType):
        q = (searchPattern or "").strip()
        if not q:
            self.addDir({"name": "category", "category": "noop", "title": "Empty search", "icon": self.DEFAULT_ICON_URL})
            return

        qlow = q.lower()
        maxPages = 12
        offset = 0
        found = 0

        for _ in range(maxPages):
            url = self.API_BASE + "teams/?limit=%d&offset=%d&format=json" % (self.LIMIT, offset)
            sts, j = self.getJson(url)
            if not sts or not isinstance(j, list) or len(j) == 0:
                break

            for it in j:
                try:
                    name = (it.get("name") or "").strip()
                    slug = (it.get("slug") or "").strip()
                    icon = (it.get("logo_file") or "").strip()
                    icon = icon or self.DEFAULT_ICON_URL
                    if not name or not slug:
                        continue
                    if qlow in name.lower():
                        found += 1
                        self.addDir({"name": "category", "category": "team_matches", "title": name, "team_slug": slug, "icon": icon, "goodforfav": True})
                except Exception:
                    printExc()

            offset += self.LIMIT

        if found == 0:
            self.addDir({"name": "category", "category": "noop", "title": "No clubs found for: %s" % q, "icon": self.DEFAULT_ICON_URL})

    # ---------- match videos ----------

    def _getMatchDetailsUrl(self, matchSlug):
        return self.API_BASE + "matches/%s?format=json" % matchSlug

    def listMatchVideos(self, cItem):
        matchSlug = (cItem.get("match_slug") or "").strip()
        if not matchSlug:
            self.addDir({"name": "category", "category": "noop", "title": "Missing match slug", "icon": self.DEFAULT_ICON_URL})
            return

        sts, details = self.getJson(self._getMatchDetailsUrl(matchSlug))
        if not sts or not isinstance(details, dict):
            self.addDir({"name": "category", "category": "noop", "title": "Failed to load match details", "icon": self.DEFAULT_ICON_URL})
            return

        videos = details.get("videos") or []
        if not isinstance(videos, list) or len(videos) == 0:
            self.addDir({"name": "category", "category": "noop", "title": "No videos for this match", "icon": self.DEFAULT_ICON_URL})
            return

        for v in videos:
            try:
                title = (v.get("title") or "Video").strip()
                mirrors = v.get("mirrors") or []
                self.addDir({"name": "category", "category": "video_mirrors", "title": title, "mirrors": mirrors, "icon": cItem.get("icon", "") or self.DEFAULT_ICON_URL})
            except Exception:
                printExc()

    def listVideoMirrors(self, cItem):
        mirrors = cItem.get("mirrors") or []
        if not isinstance(mirrors, list) or len(mirrors) == 0:
            self.addDir({"name": "category", "category": "noop", "title": "No mirrors", "icon": cItem.get("icon", "") or self.DEFAULT_ICON_URL})
            return

        for m in mirrors:
            try:
                title = (m.get("title") or "Mirror").strip()
                url = (m.get("url") or m.get("src") or m.get("link") or m.get("file") or "").strip()
                if not url:
                    continue

                params = {"name": "category", "title": title, "url": url, "icon": cItem.get("icon", "") or self.DEFAULT_ICON_URL, "goodforfav": True, "need_resolve": 1}

                if "streamusk.com/" in url:
                    params["referer"] = url
                    params["title"] = "StreaMusk Mirror"

                self.addVideo(params)
            except Exception:
                printExc()

    # ---------- resolvers ----------

    def _extractStreamainMp4FromHtml(self, html):
        html = html or ""
        u = self.cm.ph.getSearchGroups(html, r"""data-link=["']([^"']+\.mp4[^"']*)["']""")[0]
        if u:
            return self.safeUrl(self.unescapeUrl(u))
        m = re.search(r'(https?://[^"\']+\.mp4[^"\']*)', html, re.IGNORECASE)
        if m:
            return self.safeUrl(self.unescapeUrl(m.group(1)))
        return ""

    def _streamuskSlugFromUrl(self, url):
        m = re.search(r"https?://(?:www\.)?streamusk\.com/([A-Za-z0-9_-]+)", url)
        return (m.group(1) if m else "").strip()

    def _buildStreamuskM3U8(self, slug):
        if not slug:
            return ""
        return "%s/videos/%s/video.m3u8" % (self.STREAMUSK_CDN, slug)

    def getLinksForVideo(self, cItem):
        url = (cItem.get("url") or "").strip()
        if not url:
            return []

        cacheKey = "L|" + url
        if cacheKey in self.cacheLinks:
            return self.cacheLinks[cacheKey]

        # 0) Streamff page -> direct CDN mp4
        if ("streamff.link/v/" in url) or ("streamff.com/v/" in url):
            vid = self._streamffIdFromUrl(url)
            if vid:
                mp4 = "%s/%s.mp4" % (self.STREAMFF_CDN, vid)
                meta = {"User-Agent": self.UA, "Referer": self.STREAMFF_ORIGIN + "/", "Origin": self.STREAMFF_ORIGIN}
                out = [{"name": "direct", "url": strwithmeta(mp4, meta)}]
                self.cacheLinks[cacheKey] = out
                return out
            self.cacheLinks[cacheKey] = []
            return []

        # X) Streamin.me / streamin.link -> extract mirrors (Fire+Metal removed)
        if ("streamin.me/" in url) or ("streamin.link/" in url):
            hdr = {
                "User-Agent": self.UA,
                "Accept": "text/html,*/*",
                "Connection": "keep-alive",
                "Referer": self.STREAMIN_REFERER,
                "Origin": self.STREAMIN_ORIGIN,
            }
            sts, data = self.getPage(url, addParams={"header": hdr})
            if sts and data:
                mirrors = self._extractStreaminMirrors(data)

                # fallback: لو لم نجد data-src استخدم <source src=...> أو og:video
                if not mirrors:
                    mp4 = self._extractStreaminMp4FromHtml(data)
                    if mp4:
                        mirrors = [{"name": "default", "url": mp4}]

                if mirrors:
                    meta = {"User-Agent": self.UA, "Referer": self.STREAMIN_REFERER, "Origin": self.STREAMIN_ORIGIN}
                    out = []
                    for item in mirrors:
                        mname = (item.get("name") or "mirror").strip()
                        murl = (item.get("url") or "").strip()
                        if not murl:
                            continue
                        out.append({"name": mname, "url": strwithmeta(murl, meta)})
                    self.cacheLinks[cacheKey] = out
                    return out

            self.cacheLinks[cacheKey] = []
            return []

        # 1) Reddit post page -> extract HLSPlaylist.m3u8 from HTML
        if "reddit.com/" in url:
            hdr = {"User-Agent": self.UA, "Accept": "text/html,*/*", "Connection": "keep-alive", "Referer": self.REDDIT_REFERER, "Origin": self.REDDIT_ORIGIN}
            sts, data = self.getPage(url, addParams={"header": hdr})
            if sts and data:
                hls = self._redditExtractHlsFromHtml(data)
                if hls and self.cm.isValidUrl(hls):
                    meta = {"User-Agent": self.UA, "Referer": self.REDDIT_REFERER}
                    out = [{"name": "hls", "url": strwithmeta(hls, meta)}]
                    self.cacheLinks[cacheKey] = out
                    return out
            self.cacheLinks[cacheKey] = []
            return []

        # 2) v.redd.it direct -> build HLSPlaylist.m3u8
        if "v.redd.it/" in url:
            rid = self._redditIdFromVReddit(url)
            if rid:
                hls = "https://v.redd.it/%s/HLSPlaylist.m3u8" % rid
                meta = {"User-Agent": self.UA, "Referer": self.REDDIT_REFERER}
                out = [{"name": "hls", "url": strwithmeta(hls, meta)}]
                self.cacheLinks[cacheKey] = out
                return out
            self.cacheLinks[cacheKey] = []
            return []

        # 3) Streamusk page -> build CloudFront m3u8
        if "streamusk.com/" in url:
            slug = self._streamuskSlugFromUrl(url)
            m3u8 = self._buildStreamuskM3U8(slug)
            if m3u8:
                referer = (cItem.get("referer") or "").strip() or url
                meta = {"User-Agent": self.UA, "Referer": referer, "Origin": self.STREAMUSK_ORIGIN}
                out = [{"name": "hls", "url": strwithmeta(m3u8, meta)}]
                self.cacheLinks[cacheKey] = out
                return out
            self.cacheLinks[cacheKey] = []
            return []

        # 4) Streamain watch -> extract mp4
        if "streamain.com" in url and "/watch" in url:
            hdr = {"User-Agent": self.UA, "Accept": "text/html,*/*", "Connection": "keep-alive", "Referer": "https://streamain.com/", "Origin": "https://streamain.com"}
            sts, data = self.getPage(url, addParams={"header": hdr})
            if sts and data:
                mp4 = self._extractStreamainMp4FromHtml(data)
                if mp4 and self.cm.isValidUrl(mp4):
                    meta = {"User-Agent": self.UA, "Referer": url, "Origin": "https://streamain.com"}
                    out = [{"name": "direct", "url": strwithmeta(mp4, meta)}]
                    self.cacheLinks[cacheKey] = out
                    return out
            self.cacheLinks[cacheKey] = []
            return []

        # 5) direct m3u8
        if ".m3u8" in url and self.cm.isValidUrl(url):
            meta = {"User-Agent": self.UA, "Referer": (cItem.get("referer") or "").strip() or self.MAINURL}
            out = [{"name": "hls", "url": strwithmeta(url, meta)}]
            self.cacheLinks[cacheKey] = out
            return out

        out = [{"name": "link", "url": url}]
        self.cacheLinks[cacheKey] = out
        return out

    # ---------- dispatcher ----------

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("GoalsZoneAPI.handleService start")
        try:
            CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        except TypeError:
            try:
                CBaseHostClass.handleService(self, index, refresh, searchPattern)
            except TypeError:
                CBaseHostClass.handleService(self, index, refresh)

        self.currList = []
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")

        try:
            if name is None:
                self.listMainMenu({"name": "category"})
            elif category in ("matches", "matches_next"):
                self.listLatestMatches(self.currItem)
            elif category in ("teams", "teams_next"):
                self.listTeams(self.currItem)
            elif category == "team_matches":
                self.listTeamMatches(self.currItem)
            elif category == "match_videos":
                self.listMatchVideos(self.currItem)
            elif category == "video_mirrors":
                self.listVideoMirrors(self.currItem)
            elif category in ("search", "search_next_page"):
                cItem = dict(self.currItem)
                cItem.update({"search_item": False, "name": "category"})
                self.listSearchResult(cItem, searchPattern, searchType)
            elif category == "search_history":
                self.listsHistory({"name": "history", "category": "search"}, "desc", "Type")
            elif category == "noop":
                pass
            else:
                self.addDir({"name": "category", "category": "noop", "title": "Unhandled category: %s" % category, "icon": self.DEFAULT_ICON_URL})
        except Exception:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, GoalsZoneAPI(), True)

    def getSearchTypes(self):
        return [("Clubs", "clubs")]
