# Offline tests for the IMDb helpers of IPTVPlayer/components/isubprovider.py (used by the
# OpenSubtitles, SubSource and Titlovi subtitle providers): imports stubbed, GraphQL answers hand-made.
import importlib.util
import json
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Anything(object):
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _Anything()

    def __getattr__(self, name):
        return _Anything()


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__getattr__ = lambda n: _Anything()
    mod.__dict__.update(attrs)
    sys.modules[name] = mod


class _FakeCommon(object):
    def __init__(self, answers):
        self.answers = answers  # [(text in the query, answer dict or None)]
        self.requests = []

    @staticmethod
    def getDefaultHeader(browser='firefox'):
        return {'User-Agent': 'UA'}

    def getPage(self, url, params={}, post=None):
        query = " ".join(json.loads(post)["query"].split())
        self.requests.append((url, params, query))
        for part, answer in self.answers:
            if part in query:
                return (False, '') if answer is None else (True, json.dumps(answer))
        raise AssertionError("unexpected query %s" % query)


@pytest.fixture
def provider():
    saved = dict(sys.modules)
    for name in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.components",
                 "Plugins.Extensions.IPTVPlayer.libs", "Plugins.Extensions.IPTVPlayer.tools",
                 "Plugins.Extensions.IPTVPlayer.p2p3", "Plugins.Extensions.IPTVPlayer.iptvdm",
                 "Plugins.Extensions.IPTVPlayer.components.asynccall", "Plugins.Extensions.IPTVPlayer.libs.pCommon",
                 "Plugins.Extensions.IPTVPlayer.tools.iptvsubtitles", "Plugins.Extensions.IPTVPlayer.components.ihost",
                 "Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings", "Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers"):
        _stub(name)
    _stub("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit", TranslateTXT=lambda s: s)
    _stub("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None)
    # the title helpers are plain Python - load the real ones
    smSpec = importlib.util.spec_from_file_location("Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch", os.path.join(ROOT, "libs", "subtitlesmatch.py"))
    sys.modules[smSpec.name] = importlib.util.module_from_spec(smSpec)
    smSpec.loader.exec_module(sys.modules[smSpec.name])
    spec = importlib.util.spec_from_file_location("isubprovider_under_test", os.path.join(ROOT, "components", "isubprovider.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def make(answers):
        p = module.CBaseSubProviderClass.__new__(module.CBaseSubProviderClass)
        p.cm = _FakeCommon(answers)
        return p
    yield make
    sys.modules.clear()
    sys.modules.update(saved)


def _title(**fields):
    return {"data": {"title": fields}}


def test_search_keeps_the_old_item_format(provider):
    p = provider([("mainSearch", {"data": {"mainSearch": {"edges": [
        {"node": {"entity": {"id": "tt0285403", "titleText": {"text": "Scrubs"}, "titleType": {"text": "TV Series"}, "releaseYear": {"year": 2001}}}},
        {"node": {"entity": {"id": "tt0133093", "titleText": {"text": "The Matrix"}, "titleType": {"text": "Movie"}, "releaseYear": {"year": 1999}}}},
        {"node": {"entity": {"id": "tt9", "titleText": {"text": "No Year"}}}},
        {"node": {"entity": {}}}]}}})])
    sts, items = p.imdbGetMoviesByTitle('Say "hi"')
    assert sts
    assert items == [
        {"title": "Scrubs 2001 (TV Series)", "base_title": "Scrubs", "year": "2001", "imdbid": "0285403"},
        {"title": "The Matrix 1999 (Movie)", "base_title": "The Matrix", "year": "1999", "imdbid": "0133093"},
        {"title": "No Year", "base_title": "No Year", "year": "", "imdbid": "9"}]
    url, params, query = p.cm.requests[0]
    assert url == "https://caching.graphql.imdb.com/"
    assert params["header"]["Referer"] == "https://www.imdb.com/" and params["raw_post_data"]
    assert 'searchTerm: "Say \\"hi\\""' in query  # the title is quoted for GraphQL


def test_search_without_episode(provider):
    p = provider([('mainSearch', {"data": {"mainSearch": {"edges": []}}})])
    p.imdbGetMoviesByTitle("Breaking Bad S02E05")
    assert 'searchTerm: "Breaking Bad"' in p.cm.requests[0][2]


def test_series_type(provider):
    p = provider([('title(id: "tt0285403")', _title(titleType={"canHaveEpisodes": True})),
                  ('title(id: "tt0133093")', _title(titleType={"canHaveEpisodes": False}))])
    assert p.getTypeFromThemoviedb("0285403", "Scrubs") == "series"
    assert p.getTypeFromThemoviedb("0133093", "The Matrix") == "movie"
    assert p.getTypeFromThemoviedb("1", "Show 2020 (TV Mini Series)") == "series"
    assert len(p.cm.requests) == 2  # the type in the title needs no request


def test_seasons_with_wanted_one_first(provider):
    p = provider([("seasons", _title(episodes={"seasons": [{"number": 1}, {"number": 2}, {"number": 3}, {"number": None}]}))])
    assert p.imdbGetSeasons("0285403", 2) == (True, ["2", "1", "3"])
    assert p.imdbGetSeasons("tt0285403") == (True, ["1", "2", "3"])


def test_episodes_sorted_wanted_first(provider):
    def ep(eid, num, name):
        return {"node": {"id": eid, "titleText": {"text": name}, "series": {"episodeNumber": {"episodeNumber": num}}}}
    p = provider([('includeSeasons: ["1"]', _title(episodes={"episodes": {"edges": [
        ep("tt9", None, "Unaired Pilot"), ep("tt3", 3, "C"), ep("tt1", 1, "A"), ep("tt2", 2, "B")]}}))])
    sts, eps = p.imdbGetEpisodesForSeason("0944947", 1, 2)
    assert sts
    assert [(e["episode"], e["episode_title"], e["eimdbid"]) for e in eps] == [("2", "B", "2"), ("1", "A", "1"), ("3", "C", "3"), ("", "Unaired Pilot", "9")]


def test_original_title(provider):
    p = provider([("titleText", _title(titleText={"text": "The Matrix"}))])
    assert p.imdbGetOrginalByTitle("0133093") == (True, {"title": "The Matrix"})


def test_failures(provider):
    p = provider([("mainSearch", None), ("seasons", {"errors": [{"message": "x"}]}), ("titleText", "not a dict")])
    assert p.imdbGetMoviesByTitle("x") == (False, [])
    assert p.imdbGetSeasons("1") == (False, [])
    assert p.imdbGetOrginalByTitle("1") == (False, {})
    # ids which are no IMDb ids are not sent at all
    assert p.imdbGetSeasons('1") { x } #') == (False, [])
    assert p.imdbGetEpisodesForSeason("abc", 1) == (False, [])
    assert len(p.cm.requests) == 3
