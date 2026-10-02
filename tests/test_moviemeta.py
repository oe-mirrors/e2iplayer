# Offline tests for IPTVPlayer/libs/moviemeta.py: the enigma2 / E2iPlayer imports are
# stubbed and the TMDb / TVmaze / Cinemeta / OMDb answers are small hand-made dicts, no network.
import importlib.util
import json
import os
import re
import sys
import types
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Value(object):
    def __init__(self, value):
        self.value = value


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


@pytest.fixture
def mm(tmp_path):
    saved = dict(sys.modules)
    # only TMDb on by default, the tests switch the others on where they need them
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
        meta_tmdb=_Value(True), meta_imdb=_Value(False), meta_tvmaze=_Value(False), meta_cinemeta=_Value(False), meta_omdb=_Value(False),
        meta_language=_Value("de"), meta_tmdb_apikey=_Value("tmdbkey"), meta_omdb_apikey=_Value("omdbkey"))))
    for pkg in ("Components", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                "Plugins.Extensions.IPTVPlayer.libs", "Plugins.Extensions.IPTVPlayer.p2p3", "Plugins.Extensions.IPTVPlayer.tools"):
        _stubModule(pkg)
    _stubModule("Components.config", config=cfg)
    _stubModule("Plugins.Extensions.IPTVPlayer.libs.e2ijson", loads=json.loads, dumps=json.dumps)
    _stubModule("Plugins.Extensions.IPTVPlayer.libs.pCommon", common=None)
    _stubModule("Plugins.Extensions.IPTVPlayer.p2p3.UrlLib", urllib_urlencode=urlencode, urllib_quote=quote)
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools",
                GetCacheSubDir=lambda d, f="": str(tmp_path / f), GetDefaultLang=lambda: "de",
                printDBG=lambda *a: None, printExc=lambda *a: None)
    spec = importlib.util.spec_from_file_location("moviemeta_under_test", os.path.join(ROOT, "libs", "moviemeta.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.cp = cfg.plugins.iptvplayer
    module.requests = []
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _serve(mm, answers):
    # answers: [(host+path substring, {query param: value}, response or None)], first match wins;
    # a POST is matched on the GraphQL query text as "host/<query>"
    def fakeGetJson(url, postData=None, headers=None):
        parts = urlsplit(url)
        where = parts.netloc + unquote(parts.path)
        query = dict((k, v[0]) for k, v in parse_qs(parts.query).items())
        if postData is not None:
            where += " ".join(json.loads(postData)["query"].split())
            query = dict(headers or {})
        mm.requests.append((where, query))
        for path, params, response in answers:
            if path in where and all(query.get(k) == v for k, v in params.items()):
                return response
        raise AssertionError("unexpected request %s %s" % (where, query))
    mm._getJson = fakeGetJson


MOVIE_SEARCH = {"results": [
    {"id": 1, "title": "The Wolf", "release_date": "2026-01-01"},
    {"id": 2, "title": "The Wolf and the Lamb", "release_date": "2019-05-05"},
    {"id": 3, "title": "The Wolf and the Lamb", "release_date": "2026-04-24"},
]}
MOVIE_DETAILS = {
    "id": 3, "title": "The Wolf and the Lamb", "original_title": "The Wolf and the Lamb", "overview": "",
    "release_date": "2026-04-24", "runtime": 96, "status": "Released", "vote_average": 6.04, "vote_count": 12,
    "poster_path": "/poster.jpg", "genres": [{"name": "Thriller"}, {"name": "Western"}],
    "production_countries": [{"name": "United States of America"}], "production_companies": [{"name": "Winter State"}],
    "credits": {"cast": [{"name": "B", "order": 1}, {"name": "A", "order": 0}],
                "crew": [{"name": "Michael Schiff", "job": "Director", "department": "Directing"},
                         {"name": "Writer One", "job": "Screenplay", "department": "Writing"},
                         {"name": "Writer One", "job": "Story", "department": "Writing"}]},
    "release_dates": {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "R"}]},
                                  {"iso_3166_1": "DE", "release_dates": [{"certification": ""}, {"certification": "16"}]}]},
}


def test_tmdb_movie_maps_fields_and_fetches_english_plot(mm):
    _serve(mm, [
        ("search/movie", {"query": "The Wolf and the Lamb", "year": "2026", "language": "de"}, MOVIE_SEARCH),
        ("movie/3", {"language": "en"}, {"overview": "A widowed teacher..."}),
        ("movie/3", {"language": "de", "append_to_response": "credits,release_dates"}, MOVIE_DETAILS),
    ])
    meta = mm.getMeta("movie", "The Wolf and the Lamb", "2026")
    assert meta["plot"] == "A widowed teacher..."
    assert meta["poster"] == "https://image.tmdb.org/t/p/w342/poster.jpg"
    assert meta["info"] == {
        "year": "2026", "released": "2026-04-24", "duration": "1h 36min", "genres": "Thriller, Western",
        "tmdb_rating": "6.0/10", "status": "Released", "age_limit": "16", "country": "United States of America",
        "production": "Winter State", "directors": "Michael Schiff", "writers": "Writer One", "cast": "A, B",
        "source": "TMDb (themoviedb.org)"}
    assert all(q["api_key"] == "tmdbkey" for _, q in mm.requests)


def test_tmdb_series(mm):
    _serve(mm, [
        ("search/tv", {"query": "Scrubs"}, {"results": [{"id": 9, "name": "Scrubs", "first_air_date": "2001-10-02"}]}),
        ("tv/9", {}, {"name": "Scrubs", "overview": "Ärzte", "first_air_date": "2001-10-02", "episode_run_time": [],
                      "number_of_seasons": 10, "number_of_episodes": 182, "networks": [{"name": "NBC"}, {"name": "ABC"}],
                      "created_by": [{"name": "Bill Lawrence"}], "genres": [{"name": "Komödie"}], "vote_count": 0,
                      "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-14"}]}}),
    ])
    meta = mm.getMeta("tv", "Scrubs")
    assert meta["plot"] == "Ärzte"
    assert meta["poster"] == ""
    assert meta["info"] == {"year": "2001", "first_air_date": "2001-10-02", "seasons": "10", "episodes": "182",
                            "station": "NBC, ABC", "creators": "Bill Lawrence", "genres": "Komödie", "age_limit": "TV-14",
                            "source": "TMDb (themoviedb.org)"}
    assert "first_air_date_year" not in mm.requests[0][1]


def test_year_mismatch_retries_without_year(mm):
    _serve(mm, [
        ("search/movie", {"year": "2025"}, {"results": []}),
        ("search/movie", {}, {"results": [{"id": 5, "title": "Film", "release_date": "2024-12-30"}]}),
        ("movie/5", {}, {"title": "Film", "overview": "x"}),
    ])
    assert mm.getMeta("movie", "Film", "2025")["plot"] == "x"


IMDB_TITLE = {"title": {
    "titleText": {"text": "Scrubs: Die Anfänger"}, "originalTitleText": {"text": "Scrubs"}, "releaseYear": {"year": 2001},
    "releaseDate": {"day": 2, "month": 9, "year": 2003}, "ratingsSummary": {"aggregateRating": 8.4}, "metacritic": None,
    "certificate": {"rating": "12"}, "runtime": {"seconds": 1800}, "genres": {"genres": [{"text": "Komödie"}, {"text": "Drama"}]},
    "primaryImage": {"url": "https://m.media-amazon.com/images/M/MV5Bxyz@._V1_.jpg"},
    "plot": {"plotText": {"plainText": "Im Sacred Heart..."}}, "countriesOfOrigin": {"countries": [{"text": "United States"}]},
    "episodes": {"seasons": [{"number": 1}, {"number": 2}, {"number": 3}]},
    "directors": {"edges": [{"node": {"name": {"nameText": {"text": "Michael Spiller"}}}}]},
    "writers": {"edges": [{"node": {"name": {"nameText": {"text": "Bill Lawrence"}}}}]},
    "cast": {"edges": [{"node": {"name": {"nameText": {"text": "Zach Braff"}}}}, {"node": {"name": None}}]}}}


def test_imdb(mm):
    mm.cp.meta_tmdb.value = False
    mm.cp.meta_imdb.value = True
    _serve(mm, [
        ('caching.graphql.imdb.com/query { mainSearch(first: 10, options: {searchTerm: "Scrubs", type: TITLE, titleSearchOptions: {type: [TV]}})', {},
         {"data": {"mainSearch": {"edges": [
             {"node": {"entity": {"id": "tt40197357", "titleText": {"text": "Scrubs"}, "originalTitleText": {"text": "Scrubs"}, "releaseYear": {"year": 2026}}}},
             {"node": {"entity": {"id": "tt0285403", "titleText": {"text": "Scrubs: Die Anfänger"}, "originalTitleText": {"text": "Scrubs"}, "releaseYear": {"year": 2001}}}},
             {"node": {"entity": {"id": "tt1350342", "titleText": {"text": "Scrubs: Interns"}, "releaseYear": {"year": 2009}}}}]}}}),
        ('caching.graphql.imdb.com/query { title(id: "tt0285403")', {}, {"data": IMDB_TITLE}),
        ('caching.graphql.imdb.com/query { mainSearch', {}, {"data": {"mainSearch": {"edges": []}}}),
        ('caching.graphql.imdb.com/query { title(', {}, {"errors": [{"message": "bad"}]}),
    ])
    meta = mm.getMeta("tv", "Scrubs", "2001")
    assert meta["title"] == "Scrubs: Die Anfänger"
    assert meta["plot"] == "Im Sacred Heart..."
    assert meta["poster"] == "https://m.media-amazon.com/images/M/MV5Bxyz@._V1_SX342.jpg"
    assert meta["info"] == {"original_title": "Scrubs", "year": "2001", "first_air_date": "2003-09-02", "duration": "30min",
                            "seasons": "3", "genres": "Komödie, Drama", "imdb_rating": "8.4/10", "age_limit": "12",
                            "country": "United States", "directors": "Michael Spiller", "writers": "Bill Lawrence",
                            "cast": "Zach Braff", "source": "IMDb (imdb.com)"}
    # the website referer and the language headers go with the request
    headers = mm.requests[0][1]
    assert headers["Referer"] == "https://www.imdb.com/"
    assert headers["X-Imdb-User-Language"] == "de-DE" and headers["X-Imdb-User-Country"] == "DE"
    # no hit is an answer and cached; a GraphQL error is not an answer
    assert mm.getMeta("movie", "Nothing") == {}
    assert mm.getMeta("movie", "Nothing") == {}
    assert len(mm.requests) == 3


def test_imdb_same_title_has_no_original_title(mm):
    meta = mm._IMDb("en")._format({"titleText": {"text": "The Matrix"}, "originalTitleText": {"text": "The Matrix"},
                                   "releaseYear": {"year": 1999}, "metacritic": {"metascore": {"score": 73}}}, True)
    assert meta["info"] == {"year": "1999", "rating": "Metacritic 73/100", "source": "IMDb (imdb.com)"}


def test_imdb_error_is_not_cached(mm):
    mm.cp.meta_tmdb.value = False
    mm.cp.meta_imdb.value = True
    _serve(mm, [("caching.graphql.imdb.com", {}, {"errors": [{"message": "PersistedQueryNotFound"}]})])
    assert mm.getMeta("movie", "Film") == {}
    assert mm.getMeta("movie", "Film") == {}
    assert len(mm.requests) == 2


def test_by_imdb_id(mm):
    # TMDb and TVmaze have no lookup by IMDb id; IMDb is asked first, then Cinemeta, then OMDb
    mm.cp.meta_imdb.value = True
    mm.cp.meta_tvmaze.value = True
    mm.cp.meta_cinemeta.value = True
    mm.cp.meta_omdb.value = True
    _serve(mm, [
        ('caching.graphql.imdb.com/query { title(id: "tt0285403")', {}, None),
        ("cinemeta.strem.io/meta/series/tt0285403.json", {}, {"meta": {"name": "Scrubs", "imdbRating": "8.4", "releaseInfo": "2001–"}}),
        ('caching.graphql.imdb.com/query { title(id: "tt0000001")', {}, {"data": {"title": None}}),
        ("cinemeta.strem.io/meta/movie/tt0000001.json", {}, {"meta": {}}),
        ("omdbapi.com", {"i": "tt0000001"}, {"Response": "False", "Error": "Incorrect IMDb ID."}),
    ])
    meta = mm.getMetaByImdbId("tv", "tt0285403")
    assert meta["info"] == {"year": "2001", "imdb_rating": "8.4/10", "source": "Cinemeta (strem.io)"}
    assert mm.getMetaByImdbId("tv", "tt0285403") == meta
    assert [w.split("/")[0] for w, _ in mm.requests] == ["caching.graphql.imdb.com", "v3-cinemeta.strem.io"]
    # unknown id: every service answered "not there", so that is cached
    assert mm.getMetaByImdbId("movie", "tt0000001") == {}
    assert mm.getMetaByImdbId("movie", "tt0000001") == {}
    assert len(mm.requests) == 5
    # no IMDb id, no request
    assert mm.getMetaByImdbId("tv", "0285403") == {}
    assert mm.getMetaByImdbId("tv", "tt12 or 1") == {}
    assert mm.getMetaByImdbId("episode", "tt0285403") == {}
    assert len(mm.requests) == 5


def test_by_imdb_id_without_id_services(mm):
    # only TMDb on: nothing can look up an IMDb id
    _serve(mm, [])
    assert mm.getMetaByImdbId("movie", "tt0133093") == {}
    assert mm.requests == []


def test_tvmaze(mm):
    mm.cp.meta_tmdb.value = False
    mm.cp.meta_tvmaze.value = True
    _serve(mm, [
        ("api.tvmaze.com/search/shows", {"q": "Scrubs"}, [
            {"score": 0.9, "show": {"id": 84836, "name": "Scrubs", "premiered": "2026-02-25"}},
            {"score": 0.9, "show": {"id": 532, "name": "Scrubs", "premiered": "2001-10-02"}}]),
        ("api.tvmaze.com/shows/532", {"embed[]": "cast"}, {
            "name": "Scrubs", "premiered": "2001-10-02", "averageRuntime": 22, "genres": ["Comedy"], "status": "Ended",
            "rating": {"average": 8.4}, "network": {"name": "NBC", "country": {"name": "United States"}},
            "summary": "<p><b>Scrubs</b> &amp; friends.</p>", "image": {"medium": "https://tvmaze/p.jpg"},
            "_embedded": {"seasons": [{}, {}], "cast": [{"person": {"name": "Zach Braff"}}],
                          "crew": [{"type": "Producer", "person": {"name": "X"}}, {"type": "Creator", "person": {"name": "Bill Lawrence"}}]}}),
    ])
    meta = mm.getMeta("tv", "Scrubs", "2001")
    assert meta["plot"] == "Scrubs & friends."
    assert meta["poster"] == "https://tvmaze/p.jpg"
    assert meta["info"] == {"year": "2001", "first_air_date": "2001-10-02", "duration": "22min", "seasons": "2",
                            "station": "NBC", "creators": "Bill Lawrence", "genres": "Comedy", "rating": "8.4/10",
                            "status": "Ended", "country": "United States", "cast": "Zach Braff", "source": "TVmaze (tvmaze.com)"}
    # TVmaze has no movies
    assert mm.getMeta("movie", "Scrubs") == {}
    assert len(mm.requests) == 2


def test_cinemeta(mm):
    mm.cp.meta_tmdb.value = False
    mm.cp.meta_cinemeta.value = True
    _serve(mm, [
        ("v3-cinemeta.strem.io/catalog/movie/top/search=The Matrix.json", {}, {"metas": [
            {"imdb_id": "tt0234215", "name": "The Matrix Reloaded", "releaseInfo": "2003"},
            {"imdb_id": "tt0133093", "name": "The Matrix", "releaseInfo": "1999"}]}),
        ("v3-cinemeta.strem.io/meta/movie/tt0133093.json", {}, {"meta": {
            "name": "The Matrix", "description": "Neo...", "releaseInfo": "1999", "released": "1999-03-31T00:00:00.000Z",
            "runtime": "136 min", "genres": ["Action", "Sci-Fi"], "imdbRating": "8.7", "country": "United States",
            "director": ["Lana Wachowski", "Lilly Wachowski"], "writer": ["Lilly Wachowski"], "cast": ["Keanu Reeves"],
            "awards": "Won 4 Oscars.", "poster": "https://images.metahub.space/poster/small/tt0133093/img"}}),
        ("v3-cinemeta.strem.io/catalog/series/top/search=Scrubs.json", {}, {"metas": [
            {"imdb_id": "tt0285403", "name": "Scrubs", "releaseInfo": "2001–"}]}),
        ("v3-cinemeta.strem.io/meta/series/tt0285403.json", {}, {"meta": {
            "name": "Scrubs", "releaseInfo": "2001–", "released": "2001-10-02T00:00:00.000Z", "runtime": "1 min",
            "status": "Ended", "videos": [{"season": 0}, {"season": 1}, {"season": 1}, {"season": 2}]}}),
    ])
    meta = mm.getMeta("movie", "The Matrix", "1999")
    assert meta["poster"] == "https://images.metahub.space/poster/medium/tt0133093/img"
    assert meta["info"] == {"year": "1999", "released": "1999-03-31", "duration": "2h 16min", "genres": "Action, Sci-Fi",
                            "imdb_rating": "8.7/10", "country": "United States", "directors": "Lana Wachowski, Lilly Wachowski",
                            "writers": "Lilly Wachowski", "cast": "Keanu Reeves", "awards": "Won 4 Oscars.",
                            "source": "Cinemeta (strem.io)"}
    # the series runtime is a placeholder there and season 0 holds the specials
    assert mm.getMeta("tv", "Scrubs")["info"] == {"year": "2001", "first_air_date": "2001-10-02", "seasons": "2",
                                                  "status": "Ended", "source": "Cinemeta (strem.io)"}


def test_keyless_searches_ignore_unrelated_titles(mm):
    # Cinemeta and TVmaze return something for any search text
    mm.cp.meta_tmdb.value = False
    mm.cp.meta_cinemeta.value = True
    mm.cp.meta_tvmaze.value = True
    _serve(mm, [
        ("cinemeta.strem.io/catalog/movie", {}, {"metas": [{"imdb_id": "tt1273235", "name": "A Serbian Film", "releaseInfo": "2010"}]}),
        ("cinemeta.strem.io/meta/movie/tt1273235.json", {}, {"meta": {"name": "A Serbian Film", "description": "wrong"}}),
        ("cinemeta.strem.io/catalog/series", {}, {"metas": [{"imdb_id": "tt9", "name": "Dark Matter", "releaseInfo": "2024"}]}),
        ("cinemeta.strem.io/meta/series/tt9.json", {}, {"meta": {"name": "Dark Matter", "description": "Jason..."}}),
        ("api.tvmaze.com/search/shows", {}, [{"show": {"id": 1, "name": "Darkwing Duck", "premiered": "1991-09-06"}}]),
        ("api.tvmaze.com/shows/1", {}, {"name": "Darkwing Duck", "summary": "wrong"}),
    ])
    assert mm.getMeta("movie", "Xyzzy Nonexistent Film", "2026") == {}
    # a title which contains the wanted one still counts
    assert mm.getMeta("tv", "Dark Matter (2024)")["plot"] == "Jason..."


def test_omdb_with_other_ratings(mm):
    mm.cp.meta_tmdb.value = False
    mm.cp.meta_omdb.value = True
    _serve(mm, [
        ("omdbapi.com", {"t": "Matrix", "y": "1999", "type": "movie", "apikey": "omdbkey"},
         {"Response": "True", "Title": "The Matrix", "Year": "1999", "Rated": "R", "Runtime": "136 min",
          "Genre": "Action, Sci-Fi", "Director": "Lana Wachowski, Lilly Wachowski", "Plot": "Neo...",
          "Poster": "https://m.media-amazon.com/p.jpg", "imdbRating": "8.7", "Awards": "N/A", "Production": "N/A",
          "Ratings": [{"Source": "Internet Movie Database", "Value": "8.7/10"}, {"Source": "Rotten Tomatoes", "Value": "83%"},
                      {"Source": "Metacritic", "Value": "73/100"}]}),
        ("omdbapi.com", {"t": "Nope"}, {"Response": "False", "Error": "Movie not found!"}),
        ("omdbapi.com", {"t": "Limit"}, {"Response": "False", "Error": "Request limit reached!"}),
    ])
    meta = mm.getMeta("movie", "Matrix", "1999")
    assert meta["plot"] == "Neo..."
    assert meta["info"] == {"year": "1999", "duration": "2h 16min", "genres": "Action, Sci-Fi", "imdb_rating": "8.7/10",
                            "rating": "Rotten Tomatoes 83%, Metacritic 73/100", "rated": "R",
                            "directors": "Lana Wachowski, Lilly Wachowski", "source": "OMDb (omdbapi.com)"}
    assert mm.getMeta("movie", "Nope") == {}
    assert mm.getMeta("movie", "Nope") == {}
    assert mm.getMeta("movie", "Limit") == {}
    assert mm.getMeta("movie", "Limit") == {}
    # "not found" is cached, the request limit is not
    assert [q["t"] for _, q in mm.requests] == ["Matrix", "Nope", "Limit", "Limit"]


def test_chain_falls_through_to_next_service(mm):
    mm.cp.meta_tvmaze.value = True
    mm.cp.meta_cinemeta.value = True
    _serve(mm, [
        ("search/tv", {}, {"results": []}),
        ("api.tvmaze.com/search/shows", {}, None),
        ("cinemeta.strem.io/catalog/series", {}, {"metas": [{"imdb_id": "tt1", "name": "Show", "releaseInfo": "2020"}]}),
        ("cinemeta.strem.io/meta/series/tt1.json", {}, {"meta": {"name": "Show", "description": "From Cinemeta"}}),
    ])
    assert mm.getMeta("tv", "Show")["plot"] == "From Cinemeta"
    assert mm.getMeta("tv", "Show")["plot"] == "From Cinemeta"
    # TMDb did not know it, TVmaze gave no answer, Cinemeta found it - and that is cached
    assert [w.split("/")[0] for w, _ in mm.requests] == ["api.themoviedb.org", "api.tvmaze.com", "v3-cinemeta.strem.io", "v3-cinemeta.strem.io"]


def test_cache_hits_misses_and_failures(mm):
    _serve(mm, [("search/movie", {"query": "Unknown"}, {"results": []}),
                ("search/movie", {"query": "Offline"}, None)])
    assert mm.getMeta("movie", "Unknown") == {}
    assert mm.getMeta("movie", "Unknown") == {}
    assert len(mm.requests) == 1  # "not found" is cached
    assert mm.getMeta("movie", "Offline") == {}
    assert mm.getMeta("movie", "Offline") == {}
    assert len(mm.requests) == 3  # no answer is not cached

    # the cache file is read back by a fresh cache object
    mm.gCache = mm._MetaCache()
    assert mm.getMeta("movie", "Unknown") == {}
    assert len(mm.requests) == 3

    # other settings are another provider chain, so the cached answer is not used
    mm.cp.meta_language.value = "en"
    _serve(mm, [("search/movie", {"query": "Unknown", "language": "en"}, {"results": []})])
    assert mm.getMeta("movie", "Unknown") == {}
    assert len(mm.requests) == 4


def test_without_keys_or_switched_off_makes_no_request(mm):
    _serve(mm, [])
    mm.cp.meta_tmdb_apikey.value = "  "
    mm.cp.meta_omdb.value = True
    mm.cp.meta_omdb_apikey.value = ""
    assert mm.getMeta("movie", "Film") == {}
    mm.cp.meta_tmdb_apikey.value = "tmdbkey"
    mm.cp.meta_tmdb.value = False
    assert mm.getMeta("movie", "Film") == {}
    mm.cp.meta_tmdb.value = True
    assert mm.getMeta("episode", "Film") == {}
    assert mm.getMeta("movie", "  ") == {}
    assert mm.requests == []


def test_article_falls_back_to_site_data(mm):
    _serve(mm, [("search/tv", {}, {"results": []})])
    item = {"title": "Show - Season 1", "desc": "SS 1 EP 3", "icon": "https://site/icon.jpg",
            "meta_type": "tv", "meta_title": "Show", "meta_year": ""}
    assert mm.getArticleContent(item) == [{"title": "Show - Season 1", "text": "SS 1 EP 3",
                                           "images": [{"title": "", "url": "https://site/icon.jpg"}], "other_info": {}}]


def test_helpers(mm):
    assert mm._formatDuration(45) == "45min"
    assert mm._formatDuration(125) == "2h 05min"
    assert mm._formatDuration(None) == ""
    assert mm._minutes("136 min") == 136
    assert mm._minutes("") == 0
    assert mm._cleanTitle("Amélie: Die fabelhafte Welt!") == "améliediefabelhaftewelt"
    assert mm._cleanTitle("Spider-Man: No Way Home") == "spidermannowayhome"
    assert mm._names([{"name": "a"}, {"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}]) == "a, b, c"


def test_source_is_a_known_info_field():
    with open(os.path.join(ROOT, "components", "ihost.py")) as f:
        src = f.read()
    assert '"source": "Source:"' in src
    assert re.search(r'RICH_DESC_PARAMS = \[[^\]]*"source"', src)


def test_bflix_year_pattern():
    # the expression hostbflix.listItems() uses on a list entry
    pattern = r'class="dot">\s*(\d{4})\s*<'
    movie = '<div class="start"> <span class="dot">2026</span> <span class="dot">96 min</span> </div>'
    series = '<div class="start"> <span class="dot">SS 2</span> <span class="dot">EP 2</span> </div>'
    assert re.search(pattern, movie).group(1) == "2026"
    assert re.search(pattern, series) is None
    with open(os.path.join(ROOT, "hosts", "hostbflix.py")) as f:
        assert pattern in f.read()
