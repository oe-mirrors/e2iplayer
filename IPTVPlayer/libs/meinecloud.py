# -*- coding: utf-8 -*-
# meinecloud.click ("DeVideoSRC") embed player, shared by the German hosts that iframe it
# (hdfilme, topstreamfilm, kinoking, kkiste, hdfilme-tv). 01.10.2026 - the sites now embed it as
# devideosrc.co (same player and API); both domains are accepted, the API is asked on devideosrc.co.
# The player pages no longer carry data-link lists; the
# page ships a signed token and its JS asks the API for the hoster embeds:
#   /movie/<imdb>              -> POST /api/embed-links {type:movie, id, token} -> {sources:[{name,url}]}
#   /serial/<imdb>             -> POST /api/embed-links {type:tv, id, token}    -> {tv:{seasons:[{season_number, episodes:[{episode_number,title,description,url}]}]}}
#   /serial/<imdb>/<s>/<e>     -> POST /api/resolve {type,id,season,episode,mode,token} -> {sources:[...]}
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

###################################################
# FOREIGN import
###################################################
import re

###################################################

MAIN_URL = "https://devideosrc.co/"
DOMAINS = ("devideosrc.co", "meinecloud.click")
# <iframe src="..."> of a movie player page, on either domain
MOVIE_IFRAME_RE = r'<iframe[^>]+src="(https://(?:devideosrc\.co|meinecloud\.click)/movie/[^"]+)"'


def isPlayerUrl(url):
    return any(domain in (url or "") for domain in DOMAINS)


class MeineCloud(object):

    def __init__(self, cm, params, referer):
        self.cm = cm
        self.params = dict(params or {})
        self.referer = referer

    def _getPage(self, url):
        params = dict(self.params)
        params["header"] = dict(params.get("header") or {}, Referer=self.referer)
        return self.cm.getPage(url, params)

    def _postJson(self, url, pageUrl, body):
        params = dict(self.params)
        params["header"] = dict(params.get("header") or {})
        params["header"].update({"Referer": pageUrl, "Origin": MAIN_URL.rstrip("/"), "Content-Type": "application/json", "Accept": "application/json"})
        params["raw_post_data"] = True
        sts, data = self.cm.getPage(url, params, json_dumps(body))
        # a title without an active source answers 404 with {"ok": false, "error": "source_not_found"}
        try:
            data = json_loads(data) if data else {}
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def imdbFromUrl(url):
        m = re.search(r"(tt\d+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _sources(data):
        out = []
        for src in data.get("sources") or []:
            url = (src or {}).get("url", "") if isinstance(src, dict) else ""
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("http") and not isPlayerUrl(url) and url not in out:
                out.append(url)
        return out

    def _embedLinks(self, kind, imdb):
        pageUrl = MAIN_URL + ("movie/" if kind == "movie" else "serial/") + imdb
        sts, data = self._getPage(pageUrl)
        if not sts or not data:
            return {}
        token = re.search(r"""token:\s*["']([^"']+)""", data)
        if not token:
            printDBG("MeineCloud: no embed-links token on %s" % pageUrl)
            return {}
        return self._postJson(MAIN_URL + "api/embed-links", pageUrl, {"type": kind, "id": imdb, "token": token.group(1)})

    def movieLinks(self, imdb):
        """hoster embed urls of a movie"""
        return self._sources(self._embedLinks("movie", imdb)) if imdb else []

    def seriesEpisodes(self, imdb):
        """[(seasonNum, [{episode, title, desc, url}, ...]), ...] - url is the first hoster embed of that episode"""
        seasons = []
        tv = self._embedLinks("tv", imdb).get("tv") if imdb else None
        for season in (tv or {}).get("seasons") or []:
            try:
                seasonNum = int(season.get("season_number"))
            except Exception:
                continue
            episodes = []
            for ep in season.get("episodes") or []:
                try:
                    episodes.append({"episode": int(ep.get("episode_number")), "title": ep.get("title") or "", "desc": ep.get("description") or "", "url": ep.get("url") or ""})
                except Exception:
                    printExc()
            if episodes:
                seasons.append((seasonNum, episodes))
        return seasons

    def episodeLinks(self, imdb, season, episode):
        """all hoster embed urls of one episode"""
        pageUrl = "%sserial/%s/%s/%s" % (MAIN_URL, imdb, season, episode)
        sts, data = self._getPage(pageUrl)
        if not sts or not data:
            return []

        def attr(name, default=""):
            m = re.search(r'%s="([^"]*)"' % name, data)
            return m.group(1) if m else default

        token = attr("data-resolve-token")
        if not token:
            printDBG("MeineCloud: no resolve token on %s" % pageUrl)
            return []
        endpoint = attr("data-resolve-endpoint", "/api/resolve")
        body = {"type": attr("data-type", "tv"), "id": attr("data-id", imdb), "season": attr("data-season", str(season)),
                "episode": attr("data-episode", str(episode)), "mode": attr("data-mode", "custom"), "token": token}
        if not endpoint.startswith("http"):
            endpoint = MAIN_URL + endpoint.lstrip("/")
        return self._sources(self._postJson(endpoint, pageUrl, body))
