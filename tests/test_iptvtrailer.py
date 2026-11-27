# Offline test of the trailer search (components/iptvtrailer.py): the pure functions - title of a row, YouTube id,
# the host's own trailer, the order / dedup / early stop of the sources. Enigma2 and the network are stubbed.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Value(object):
    def __init__(self, value):
        self.value = value


@pytest.fixture
def trailer():
    settings = types.SimpleNamespace(trailer_language=_Value('de'), trailer_search_suffix=_Value(''),
                                     trailer_autoplay=_Value(False), meta_tmdb=_Value(False), meta_tmdb_apikey=_Value(''))
    saved = {}

    def stub(name, **attrs):
        saved[name] = sys.modules.get(name)
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod

    base = "Plugins.Extensions.IPTVPlayer"
    for name in ("Plugins", "Plugins.Extensions", base, base + ".components", base + ".libs", base + ".tools", base + ".p2p3",
                 "Components", "Screens"):
        stub(name)
    stub(base + ".components.asynccall", AsyncMethod=object)
    stub(base + ".components.iptvchoicebox", IPTVChoiceBoxItem=object, openChoiceBox=lambda *a, **k: None)
    stub(base + ".components.iptvplayerinit", TranslateTXT=lambda t: t)
    stub(base + ".libs.moviemeta", _getLanguage=lambda: 'de')
    stub(base + ".p2p3.UrlLib", urllib_quote_plus=lambda t: t.replace(' ', '+'))
    stub(base + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, eConnectCallback=object,
         StripColorCodes=lambda t: t)
    stub("Components.config", config=types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=settings)))
    stub("Screens.MessageBox", MessageBox=object)
    stub("enigma", eTimer=object)
    spec = importlib.util.spec_from_file_location("iptvtrailer_test", os.path.join(ROOT, "components", "iptvtrailer.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.test_settings = settings
    yield module
    for name, mod in saved.items():
        if mod is None:
            del sys.modules[name]
        else:
            sys.modules[name] = mod


@pytest.mark.parametrize("name,expected", [
    ("Eclipse - Kampf der Magier", ("Eclipse - Kampf der Magier", "")),
    ("Steps (2026)", ("Steps", "2026")),
    ("Blade Runner 2099 - Staffel 1", ("Blade Runner 2099", "")),
    ("The Office S02E05 Halloween", ("The Office", "")),
    ("Dune: Part Two [2024] 4K HDR", ("Dune: Part Two", "2024")),
])
def test_clean_title(trailer, name, expected):
    assert trailer.cleanTitle(name) == expected


def test_row_query_prefers_the_hosts_meta_fields(trailer):
    raw = {'meta_title': 'Steps', 'meta_year': '2026-11-20', 'meta_type': 'movie'}
    assert trailer.rowQuery('Steps (2026) [HD]', raw) == ('Steps', '2026', 'movie')
    assert trailer.rowQuery('Steps', {'meta_year': 'n/a'}) == ('Steps', '', '')


@pytest.mark.parametrize("value,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://example.com/trailer.mp4", ""),
    ("", ""),
])
def test_youtube_id(trailer, value, expected):
    assert trailer.youtubeId(value) == expected


def test_host_trailers_youtube_and_direct_url(trailer):
    hits = trailer.hostTrailers({'youtube_trailer': 'dQw4w9WgXcQ', 'trailer_url': 'https://cdn.example/t.mp4'}, 'Steps')
    assert [h['source'] for h in hits] == ['host', 'host']
    assert hits[0]['url'].endswith('v=dQw4w9WgXcQ') and not hits[0].get('direct')
    assert hits[1]['direct'] and hits[1]['url'] == 'https://cdn.example/t.mp4'
    # a direct url is played as it is, without the YouTube resolver
    assert trailer.resolveTrailer(hits[1]) == ['https://cdn.example/t.mp4']


def test_find_trailers_dedup_and_first_only(trailer, monkeypatch):
    calls = []
    monkeypatch.setattr(trailer, 'tmdbTrailers', lambda *a: calls.append('tmdb') or [trailer._hit('aaaaaaaaaaa', 'A')])
    monkeypatch.setattr(trailer, 'youtubeTrailers', lambda *a: calls.append('yt') or [trailer._hit('aaaaaaaaaaa', 'A again'),
                                                                                      trailer._hit('bbbbbbbbbbb', 'B')])
    hits = trailer.findTrailers('Steps', '2026', 'movie', {})
    assert [h['video_id'] for h in hits] == ['aaaaaaaaaaa', 'bbbbbbbbbbb'] and calls == ['tmdb', 'yt']
    # "Play the first trailer at once": the YouTube search is not made when TMDb had one
    del calls[:]
    hits = trailer.findTrailers('Steps', '2026', 'movie', {}, True)
    assert [h['video_id'] for h in hits] == ['aaaaaaaaaaa'] and calls == ['tmdb']


def test_search_suffix(trailer):
    assert trailer.searchSuffix('de') == 'Trailer Deutsch'
    assert trailer.searchSuffix('xx') == 'Trailer'
    trailer.test_settings.trailer_search_suffix.value = ' Kinotrailer HD '
    assert trailer.searchSuffix('de') == 'Kinotrailer HD'
