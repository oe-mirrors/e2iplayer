# -*- coding: utf-8 -*-
#
# Movie and series details (plot, poster, rating, cast...) for the info screen,
# looked up by title and year. The services switched on in the configuration are
# asked in the order TMDb, IMDb, TVmaze (series only), Cinemeta, OMDb until one
# knows the title. TMDb and OMDb need the user's own free API key; IMDb, TVmaze
# and Cinemeta need none. TMDb and IMDb have translated texts, the others English.
#
# Based on the TMDb/OMDb patch MOHAMED_OS posted for Bflix, whose tmdb.py was a
# port of cTMDb from Kodi-vStream (plugin.video.vstream/resources/lib/tmdb.py,
# GPLv3). Rewritten smaller: only the title search and the details call, and a
# JSON cache with expiry instead of the SQLite tables. The keyless TVmaze and
# Cinemeta fallbacks follow openATV's e2MDB plugin, the IMDb GraphQL request
# (anonymous, needs the referer) the oe-alliance IMDb plugin.
#
# A host puts meta_type ("movie" or "tv"), meta_title and meta_year into its
# items and returns getArticleContent(cItem) from its own getArticleContent().

import os
import re
import threading
import time
from html import unescape

from Components.config import config
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetCacheSubDir, GetDefaultLang, printDBG, printExc

TMDB_API_URL = "https://api.themoviedb.org/3/"
TMDB_POSTER_URL = "https://image.tmdb.org/t/p/w342"
IMDB_GRAPHQL_URL = "https://caching.graphql.imdb.com/"
TVMAZE_API_URL = "https://api.tvmaze.com/"
CINEMETA_API_URL = "https://v3-cinemeta.strem.io/"
OMDB_API_URL = "https://www.omdbapi.com/"

CACHE_TTL = 7 * 24 * 3600  # titles which were found
CACHE_TTL_MISS = 24 * 3600  # titles no service knows
CACHE_MAX_ENTRIES = 1000

# country of the age rating where it is not the language code itself
CERT_COUNTRY = {"en": "US", "ar": "EG", "cs": "CZ", "el": "GR", "uk": "UA"}


def _cleanTitle(title):
    return re.sub(r"[\W_]+", "", (title or "").lower(), flags=re.UNICODE)


def _names(items, limit=3, key="name"):
    # unique names in their order, at most limit of them
    names = []
    for item in items or []:
        name = item.get(key) if isinstance(item, dict) else item
        if name and name not in names:
            names.append(name)
            if len(names) >= limit:
                break
    return ", ".join(names)


def _formatDuration(minutes):
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return ""
    if minutes <= 0:
        return ""
    if minutes < 60:
        return "%dmin" % minutes
    return "%dh %02dmin" % (minutes // 60, minutes % 60)


def _minutes(text):
    # "136 min" -> 136
    found = re.search(r"\d+", text or "")
    return int(found.group(0)) if found else 0


def _pickResult(results, title, year, titleKeys, dateKey, strict=False):
    # the service's order is its relevance; a result with the same title wins,
    # then the one from the given year. strict: only results whose title is the
    # same or contains the other one (for the fuzzy keyless searches, which
    # always return something)
    wanted = _cleanTitle(title)
    best, bestScore = None, -1
    for item in results[:20]:
        titles = [_cleanTitle(item.get(k)) for k in titleKeys]
        score = 0
        if wanted in titles:
            score += 2
        elif strict and not any(t and (wanted in t or t in wanted) for t in titles):
            continue
        if year and (item.get(dateKey) or "")[:4] == year:
            score += 1
        if score > bestScore:
            best, bestScore = item, score
    return best


def _result(title, plot, poster, info, source):
    info = dict((k, str(v)) for k, v in info.items() if v)
    info["source"] = source
    return {"title": title or "", "plot": plot or "", "poster": poster or "", "info": info}


def _getJson(url, postData=None, headers=None):
    # None = no answer (network, wrong key, request limit), so the caller does not cache it
    params = {"timeout": 10}
    if headers:
        params["header"] = headers
    if postData is not None:
        params["raw_post_data"] = True
    sts, data = common().getPage(url, params, postData)
    if not sts:
        printDBG("moviemeta: request failed %s" % url.split("?")[0])
        return None
    try:
        return json_loads(data)
    except ValueError:
        printDBG("moviemeta: no JSON from %s" % url.split("?")[0])
        return None


def _getLanguage():
    lang = config.plugins.iptvplayer.meta_language.value
    if lang == "auto":
        lang = GetDefaultLang() or "en"
    return lang


def _getCountry(lang):
    return CERT_COUNTRY.get(lang, lang.upper())


class _MetaCache(object):
    # {key: [expiry time, result]} in CacheDir/moviemeta/moviemeta.json, read on first use

    def __init__(self):
        self.lock = threading.Lock()
        self.data = None

    def _load(self):
        if self.data is None:
            self.data = {}
            try:
                path = GetCacheSubDir("moviemeta", "moviemeta.json")
                if os.path.isfile(path):
                    with open(path, "r") as f:
                        data = json_loads(f.read())
                    if isinstance(data, dict):
                        self.data = data
            except Exception:
                printExc()
        return self.data

    def get(self, key):
        with self.lock:
            entry = self._load().get(key)
        if isinstance(entry, list) and len(entry) == 2 and entry[0] > time.time():
            return entry[1]
        return None

    def put(self, key, value, ttl):
        with self.lock:
            data = self._load()
            now = time.time()
            data[key] = [now + ttl, value]
            for k in [k for k, v in data.items() if not isinstance(v, list) or v[0] <= now]:
                del data[k]
            if len(data) > CACHE_MAX_ENTRIES:
                for k in sorted(data, key=lambda k: data[k][0])[:len(data) - CACHE_MAX_ENTRIES]:
                    del data[k]
            try:
                path = GetCacheSubDir("moviemeta", "moviemeta.json")
                with open(path + ".tmp", "w") as f:
                    f.write(json_dumps(data))
                os.replace(path + ".tmp", path)
            except Exception as e:
                printDBG("moviemeta: cache not written: %s" % e)


gCache = _MetaCache()


# Every provider has find(mediaType, title, year) which returns a _result() dict,
# {} when the service does not know the title, or None when it gave no answer.

class _TMDb(object):
    NAME = "TMDb"

    def __init__(self, key, lang):
        self.key = key
        self.lang = lang

    def _call(self, path, params):
        params = dict(params)
        params.setdefault("language", self.lang)
        params["api_key"] = self.key
        return _getJson(TMDB_API_URL + path + "?" + urllib_urlencode(params))

    def find(self, mediaType, title, year):
        movie = mediaType == "movie"
        path = "search/movie" if movie else "search/tv"
        params = {"query": title}
        if year:
            params["year" if movie else "first_air_date_year"] = year
        data = self._call(path, params)
        if data is not None and not data.get("results") and year:
            # the site's year can be off by one (other release date)
            data = self._call(path, {"query": title})
        if data is None:
            return None
        titleKeys = ("title", "original_title") if movie else ("name", "original_name")
        hit = _pickResult(data.get("results") or [], title, year, titleKeys, "release_date" if movie else "first_air_date")
        if not hit:
            return {}

        details = self._call("%s/%s" % (mediaType, hit["id"]), {"append_to_response": "credits,release_dates" if movie else "credits,content_ratings"})
        if details is None:
            return None
        if not details.get("overview") and self.lang != "en":
            # many titles have no translated plot yet
            english = self._call("%s/%s" % (mediaType, hit["id"]), {"language": "en"})
            if english:
                details["overview"] = english.get("overview") or ""
        return self._format(details, movie)

    def _certification(self, details, movie):
        country = _getCountry(self.lang)
        ratings = {}
        if movie:
            for entry in (details.get("release_dates") or {}).get("results") or []:
                certs = [r.get("certification") for r in entry.get("release_dates") or [] if r.get("certification")]
                if certs:
                    ratings[entry.get("iso_3166_1")] = certs[0]
        else:
            for entry in (details.get("content_ratings") or {}).get("results") or []:
                if entry.get("rating"):
                    ratings[entry.get("iso_3166_1")] = entry["rating"]
        return ratings.get(country) or ratings.get("US") or ""

    def _format(self, details, movie):
        info = {}
        title = details.get("title" if movie else "name") or ""
        original = details.get("original_title" if movie else "original_name") or ""
        if original and original != title:
            info["original_title"] = original
        date = details.get("release_date" if movie else "first_air_date") or ""
        if date:
            info["year"] = date[:4]
            info["released" if movie else "first_air_date"] = date
        if movie:
            info["duration"] = _formatDuration(details.get("runtime"))
        else:
            info["duration"] = _formatDuration((details.get("episode_run_time") or [0])[0])
            info["seasons"] = details.get("number_of_seasons") or ""
            info["episodes"] = details.get("number_of_episodes") or ""
            info["station"] = _names(details.get("networks"))
            info["creators"] = _names(details.get("created_by"))
        info["genres"] = _names(details.get("genres"), 5)
        if details.get("vote_count"):
            info["tmdb_rating"] = "%.1f/10" % details.get("vote_average", 0)
        info["status"] = details.get("status") or ""
        info["age_limit"] = self._certification(details, movie)
        info["country"] = _names(details.get("production_countries"))
        info["production"] = _names(details.get("production_companies"))

        credits = details.get("credits") or {}
        crew = credits.get("crew") or []
        info["directors"] = _names([c for c in crew if c.get("job") == "Director"])
        info["writers"] = _names([c for c in crew if c.get("department") == "Writing"])
        info["cast"] = _names(sorted(credits.get("cast") or [], key=lambda c: c.get("order", 999)), 5)

        poster = details.get("poster_path") or ""
        return _result(title, details.get("overview"), TMDB_POSTER_URL + poster if poster else "", info, "TMDb (themoviedb.org)")


class _IMDb(object):
    # IMDb's own GraphQL API as its website uses it: no key, but it only answers with
    # the imdb.com referer. Texts, genres and the age rating come in the language of
    # the X-Imdb-User-Language header where IMDb has them, else in English.
    NAME = "IMDb"

    SEARCH_QUERY = """query { mainSearch(first: 10, options: {searchTerm: %s, type: TITLE, titleSearchOptions: {type: [%s]}}) {
 edges { node { entity { ... on Title { id titleText { text } originalTitleText { text } releaseYear { year } } } } } } }"""
    TITLE_QUERY = """query { title(id: %s) { titleText { text } originalTitleText { text } releaseYear { year }
 releaseDate { day month year } ratingsSummary { aggregateRating } metacritic { metascore { score } }
 certificate { rating } runtime { seconds } genres { genres { text } } primaryImage { url } plot { plotText { plainText } }
 countriesOfOrigin { countries { text } } episodes { seasons { number } }
 directors: credits(first: 3, filter: {categories: ["director"]}) { edges { node { name { nameText { text } } } } }
 writers: credits(first: 3, filter: {categories: ["writer"]}) { edges { node { name { nameText { text } } } } }
 cast: credits(first: 5, filter: {categories: ["actor", "actress"]}) { edges { node { name { nameText { text } } } } } } }"""

    def __init__(self, lang):
        self.lang = lang

    def _call(self, query):
        locale = "%s-%s" % (self.lang, _getCountry(self.lang))
        headers = {"Content-Type": "application/json", "Referer": "https://www.imdb.com/",
                   "X-Imdb-User-Language": locale, "X-Imdb-User-Country": _getCountry(self.lang)}
        data = _getJson(IMDB_GRAPHQL_URL, json_dumps({"query": query}), headers)
        if data is None or not isinstance(data.get("data"), dict):
            return None
        return data["data"]

    def find(self, mediaType, title, year):
        movie = mediaType == "movie"
        data = self._call(self.SEARCH_QUERY % (json_dumps(title), "MOVIE" if movie else "TV"))
        if data is None:
            return None
        results = []
        for edge in (data.get("mainSearch") or {}).get("edges") or []:
            entity = (edge.get("node") or {}).get("entity") or {}
            if entity.get("id"):
                results.append({"id": entity["id"], "title": (entity.get("titleText") or {}).get("text"),
                                "original": (entity.get("originalTitleText") or {}).get("text"),
                                "year": str((entity.get("releaseYear") or {}).get("year") or "")})
        hit = _pickResult(results, title, year, ("original", "title"), "year", strict=True)
        if not hit:
            return {}
        return self.findById(mediaType, hit["id"])

    def findById(self, mediaType, imdbId):
        data = self._call(self.TITLE_QUERY % json_dumps(imdbId))
        if data is None:
            return None
        return self._format(data["title"], mediaType == "movie") if data.get("title") else {}

    def _format(self, t, movie):
        def text(key):
            return (t.get(key) or {}).get("text") or ""

        def credits(key):
            return _names([((e.get("node") or {}).get("name") or {}).get("nameText") for e in (t.get(key) or {}).get("edges") or []], 5 if key == "cast" else 3, "text")

        date = t.get("releaseDate") or {}
        released = "%04d-%02d-%02d" % (date["year"], date["month"], date["day"]) if date.get("year") and date.get("month") and date.get("day") else ""
        rating = (t.get("ratingsSummary") or {}).get("aggregateRating")
        metascore = ((t.get("metacritic") or {}).get("metascore") or {}).get("score")
        info = {
            "original_title": text("originalTitleText") if text("originalTitleText") != text("titleText") else "",
            "year": (t.get("releaseYear") or {}).get("year") or "",
            "released" if movie else "first_air_date": released,
            "duration": _formatDuration(((t.get("runtime") or {}).get("seconds") or 0) // 60),
            "seasons": "" if movie else len((t.get("episodes") or {}).get("seasons") or []),
            "genres": _names((t.get("genres") or {}).get("genres"), 5, "text"),
            "imdb_rating": "%.1f/10" % rating if rating else "",
            "rating": "Metacritic %s/100" % metascore if metascore else "",
            "age_limit": (t.get("certificate") or {}).get("rating") or "",
            "country": _names((t.get("countriesOfOrigin") or {}).get("countries"), 3, "text"),
            "directors": credits("directors"),
            "writers": credits("writers"),
            "cast": credits("cast"),
        }
        # the full size picture is several MB, the CDN scales it on request
        poster = re.sub(r"\._V1_.*\.jpg$", "._V1_SX342.jpg", (t.get("primaryImage") or {}).get("url") or "")
        return _result(text("titleText"), ((t.get("plot") or {}).get("plotText") or {}).get("plainText"), poster, info, "IMDb (imdb.com)")


class _TVmaze(object):
    NAME = "TVmaze"

    def find(self, mediaType, title, year):
        data = _getJson(TVMAZE_API_URL + "search/shows?" + urllib_urlencode({"q": title}))
        if data is None:
            return None
        shows = [r.get("show") for r in data if isinstance(r, dict) and r.get("show")] if isinstance(data, list) else []
        hit = _pickResult(shows, title, year, ("name",), "premiered", strict=True)
        if not hit:
            return {}
        show = _getJson(TVMAZE_API_URL + "shows/%s?embed[]=cast&embed[]=crew&embed[]=seasons" % hit["id"])
        if show is None:
            return None
        embedded = show.get("_embedded") or {}
        network = show.get("network") or show.get("webChannel") or {}
        info = {
            "year": (show.get("premiered") or "")[:4],
            "first_air_date": show.get("premiered") or "",
            "duration": _formatDuration(show.get("averageRuntime") or show.get("runtime")),
            "seasons": len(embedded.get("seasons") or []),
            "station": network.get("name") or "",
            "creators": _names([c.get("person") for c in embedded.get("crew") or [] if c.get("type") == "Creator"]),
            "genres": _names(show.get("genres"), 5),
            "rating": "%s/10" % (show.get("rating") or {}).get("average") if (show.get("rating") or {}).get("average") else "",
            "status": show.get("status") or "",
            "country": ((network.get("country") or {}).get("name")) or "",
            "cast": _names([c.get("person") for c in embedded.get("cast") or []], 5),
        }
        plot = unescape(re.sub(r"<[^>]+>", "", show.get("summary") or "")).strip()
        return _result(show.get("name"), plot, (show.get("image") or {}).get("medium"), info, "TVmaze (tvmaze.com)")


class _Cinemeta(object):
    # the public catalogue of the Stremio media center, keyed by IMDb id
    NAME = "Cinemeta"

    def find(self, mediaType, title, year):
        kind = "movie" if mediaType == "movie" else "series"
        data = _getJson(CINEMETA_API_URL + "catalog/%s/top/search=%s.json" % (kind, urllib_quote(title)))
        if data is None:
            return None
        hit = _pickResult(data.get("metas") or [], title, year, ("name",), "releaseInfo", strict=True)
        if not hit or not hit.get("imdb_id"):
            return {}
        return self.findById(mediaType, hit["imdb_id"])

    def findById(self, mediaType, imdbId):
        kind = "movie" if mediaType == "movie" else "series"
        data = _getJson(CINEMETA_API_URL + "meta/%s/%s.json" % (kind, imdbId))
        if data is None:
            return None
        meta = data.get("meta") or {}
        if not meta:
            return {}
        info = {
            "year": (meta.get("releaseInfo") or "")[:4],
            "released": (meta.get("released") or "")[:10] if kind == "movie" else "",
            "first_air_date": (meta.get("released") or "")[:10] if kind == "series" else "",
            # series only have a placeholder runtime there
            "duration": _formatDuration(_minutes(meta.get("runtime"))) if kind == "movie" else "",
            "seasons": len(set(v.get("season") for v in meta.get("videos") or [] if v.get("season"))) if kind == "series" else "",
            "genres": _names(meta.get("genres") or meta.get("genre"), 5),
            "imdb_rating": "%s/10" % meta["imdbRating"] if meta.get("imdbRating") else "",
            "status": meta.get("status") or "",
            "country": meta.get("country") or "",
            "directors": _names(meta.get("director")),
            "writers": _names(meta.get("writer")),
            "cast": _names(meta.get("cast"), 5),
            "awards": meta.get("awards") or "",
        }
        poster = (meta.get("poster") or "").replace("/poster/small/", "/poster/medium/")
        return _result(meta.get("name"), meta.get("description"), poster, info, "Cinemeta (strem.io)")


class _OMDb(object):
    NAME = "OMDb"

    def __init__(self, key):
        self.key = key

    def find(self, mediaType, title, year):
        params = {"t": title, "type": "movie" if mediaType == "movie" else "series", "plot": "full", "apikey": self.key}
        if year:
            params["y"] = year
        data = _getJson(OMDB_API_URL + "?" + urllib_urlencode(params))
        if data is not None and data.get("Response") != "True" and year:
            del params["y"]
            data = _getJson(OMDB_API_URL + "?" + urllib_urlencode(params))
        if data is None:
            return None
        return self._answer(data)

    def findById(self, mediaType, imdbId):
        return self._answer(_getJson(OMDB_API_URL + "?" + urllib_urlencode({"i": imdbId, "plot": "full", "apikey": self.key})))

    def _answer(self, data):
        if data is None:
            return None
        if data.get("Response") != "True":
            # "Movie not found!" / "Incorrect IMDb ID." are answers; "Invalid API key!" or "Request limit reached!" are not
            error = (data.get("Error") or "").lower()
            return {} if "not found" in error or "incorrect imdb id" in error else None
        return self._format(data)

    def _format(self, data):
        def value(key):
            v = data.get(key) or ""
            return "" if v == "N/A" else v

        # IMDb is shown on its own, the others (Rotten Tomatoes, Metacritic) as "Rating:"
        ratings = ["%s %s" % (r.get("Source"), r.get("Value")) for r in data.get("Ratings") or []
                   if r.get("Source") and r.get("Value") and r.get("Source") != "Internet Movie Database"]
        info = {
            "year": value("Year"),
            "released": value("Released"),
            "duration": _formatDuration(_minutes(value("Runtime"))),
            "genres": value("Genre"),
            "imdb_rating": "%s/10" % value("imdbRating") if value("imdbRating") else "",
            "rating": ", ".join(ratings),
            "rated": value("Rated"),
            "seasons": value("totalSeasons"),
            "country": value("Country"),
            "production": value("Production"),
            "directors": value("Director"),
            "writers": value("Writer"),
            "cast": value("Actors"),
            "awards": value("Awards"),
        }
        return _result(value("Title"), value("Plot"), value("Poster"), info, "OMDb (omdbapi.com)")


def _getProviders(mediaType):
    cp = config.plugins.iptvplayer
    providers = []
    if cp.meta_tmdb.value and cp.meta_tmdb_apikey.value.strip():
        providers.append(_TMDb(cp.meta_tmdb_apikey.value.strip(), _getLanguage()))
    if cp.meta_imdb.value:
        providers.append(_IMDb(_getLanguage()))
    if cp.meta_tvmaze.value and mediaType == "tv":
        providers.append(_TVmaze())
    if cp.meta_cinemeta.value:
        providers.append(_Cinemeta())
    if cp.meta_omdb.value and cp.meta_omdb_apikey.value.strip():
        providers.append(_OMDb(cp.meta_omdb_apikey.value.strip()))
    return providers


def getMeta(mediaType, title, year=""):
    # {"title", "plot", "poster", "info": {ArticleContent.RICH_DESC_PARAMS key: text}} or {}
    title = (title or "").strip()
    year = str(year or "").strip()[:4]
    if mediaType not in ("movie", "tv") or not title:
        return {}
    providers = _getProviders(mediaType)
    if not providers:
        return {}  # all switched off or no API keys
    if not year.isdigit():
        year = ""
    return _lookup(providers, "|".join((mediaType, _cleanTitle(title), year)), lambda p: p.find(mediaType, title, year))


def getMetaByImdbId(mediaType, imdbId):
    # the same for a known IMDb id ("tt..."), from the services keyed by it: IMDb, Cinemeta, OMDb
    imdbId = (imdbId or "").strip()
    if mediaType not in ("movie", "tv") or not re.match(r"^tt\d+$", imdbId):
        return {}
    providers = [p for p in _getProviders(mediaType) if hasattr(p, "findById")]
    if not providers:
        return {}
    return _lookup(providers, "|".join((mediaType, imdbId)), lambda p: p.findById(mediaType, imdbId))


def _lookup(providers, what, find):
    # first non-empty answer of the providers, cached; the cache key holds the provider
    # chain, so other settings do not get old answers
    chain = ",".join(p.NAME + (":" + p.lang if hasattr(p, "lang") else "") for p in providers)
    key = chain + "|" + what
    meta = gCache.get(key)
    if meta is not None:
        return meta
    answered = True
    for provider in providers:
        try:
            meta = find(provider)
        except Exception:
            printExc()
            meta = None
        if meta:
            gCache.put(key, meta, CACHE_TTL)
            return meta
        if meta is None:
            answered = False
    if answered:
        gCache.put(key, {}, CACHE_TTL_MISS)
    return {}  # a service gave no answer: not cached, tried again next time


def getArticleContent(cItem):
    # info screen content of an item with meta_type/meta_title/meta_year; the site's
    # description and icon stay when no service knows the title
    meta = getMeta(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""))
    icon = meta.get("poster") or cItem.get("icon", "")
    return [{"title": cItem.get("title", ""),
             "text": meta.get("plot") or cItem.get("desc", ""),
             "images": [{"title": "", "url": icon}] if icon else [],
             "other_info": meta.get("info", {})}]
