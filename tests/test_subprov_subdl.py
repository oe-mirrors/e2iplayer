# -*- coding: utf-8 -*-
# Offline tests for subprov_subdlapi.py (season numbers, imdb id of the title page, archive file choice),
# subprov_subsourceapi.py (one entry per subtitle, one cached request for all languages) and
# subprov_subsro.py (season packs, language order). Imports stubbed, answers hand-made.
import importlib.util
import io
import os
import re
import sys
import types
import urllib.parse
import zipfile

import pytest

from test_isubprovider_files import _Meta, files  # noqa: F401 - base class with patched file helpers
from test_isubprovider_imdb import ROOT, provider  # noqa: F401

PKG = 'Plugins.Extensions.IPTVPlayer.subproviders.'


class _Val(object):
    def __init__(self, value):
        self.value = value


@pytest.fixture
def subprov(files, tmp_path):  # noqa: F811
    base, _tmp, _baseErrors = files
    errors = []
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(subdlapi=_Val(''), subsourceapi=_Val(''))))
    mods = {
        'Components.config': dict(config=cfg),
        'Plugins.Extensions.IPTVPlayer.components.isubprovider': dict(CBaseSubProviderClass=type(base), CSubProviderBase=object),
        'Plugins.Extensions.IPTVPlayer.components.iptvplayerinit': dict(TranslateTXT=lambda s: s, SetIPTVPlayerLastHostError=errors.append),
        'Plugins.Extensions.IPTVPlayer.p2p3.UrlLib': dict(urllib_urlencode=urllib.parse.urlencode, urllib_quote=urllib.parse.quote,
                                                          urllib_quote_plus=urllib.parse.quote_plus),
        'Plugins.Extensions.IPTVPlayer.tools.iptvtools': dict(printDBG=lambda *a: None, printExc=lambda *a: None, GetDefaultLang=lambda: 'de',
                                                              E2ColoR=lambda c: ''),
        'Plugins.Extensions.IPTVPlayer.subproviders': {},
    }
    for name, attrs in mods.items():
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod
    loaded = {}
    for name in ('subprov_subdlapi', 'subprov_subsourceapi', 'subprov_subsro'):
        spec = importlib.util.spec_from_file_location(PKG + name, os.path.join(ROOT, 'subproviders', name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # subsource imports the archive helper of subdl
        spec.loader.exec_module(module)
        loaded[name] = module
    type(base).converFileToUtf8.__globals__['SetIPTVPlayerLastHostError'] = errors.append

    def make(cls, params):
        p = cls.__new__(cls)
        p.__dict__.update(base.__dict__)
        p.params = params
        p.currList, p.currItem = [], {}
        p.HTTP_HEADER = {}
        p.MAIN_URL = 'https://example.org/'
        p.cleanHtmlStr = lambda s: re.sub(r'<[^>]+>', '', s).strip()
        p.getSupportedFormats = lambda all=False: ['srt', 'ass', 'txt', 'sub']
        p.searchTitle, p.searchYear, p.wantedSeason, p.wantedEpisode = p.wantedInfo()
        p.pageCache, p.apiCache, p.subsCache = {}, {}, {}
        return p
    return loaded, make, errors


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)
    return buf.getvalue()


def _srt(text):
    return ('1\n00:00:01,000 --> 00:00:02,000\n%s\n' % text).encode('utf-8')


def test_subdl_season_number_and_query(subprov):
    loaded, make, errors = subprov
    subdl = loaded['subprov_subdlapi']
    season = subdl.SubDLAPIProvider.seasonNumber
    # the season number, not the first digits of the show name
    assert season('9-1-1-season-3', '9-1-1 Season 3') == 3
    assert season('season-2', '24 - Season 2') == 2
    assert season('first-season', '1923 - First Season') == 1
    assert season('specials', 'Specials') == 0
    assert season('', '') == 9999
    assert subdl.searchQuery('Mission: Impossible - Fallout') == 'Mission Impossible Fallout'


def test_subdl_pick_archive_file(subprov, tmp_path):
    loaded, make, errors = subprov
    pick = loaded['subprov_subdlapi'].pickArchiveFile
    d = tmp_path / 'arch'
    (d / 'pack').mkdir(parents=True)
    for name in ('readme.txt', 'Show.S02E04.srt', 'pack/Show.S02E05.srt', 'notes.nfo'):
        (d / name).write_bytes(b'x')
    exts = ['srt', 'txt']
    assert pick(str(d), exts, 2, 5)['name'] == 'Show.S02E05.srt'
    # without an episode: real subtitle formats before .txt
    assert pick(str(d), exts, None, None)['name'] == 'Show.S02E04.srt'
    assert pick(str(d), ['ass'], 2, 5) is None


def test_subdl_download_takes_the_episode_file(subprov):
    loaded, make, errors = subprov
    p = make(loaded['subprov_subdlapi'].SubDLAPIProvider, {'confirmed_title': 'Breaking Bad S02E05'})
    p.cm = _Meta(_zip([('Breaking.Bad.S02E04.srt', _srt('four')), ('S2/Breaking.Bad.S02E05.srt', _srt('five'))]), {})
    ret = p.downloadSubtitleFile({'url': 'https://dl.subdl.com/subtitle/1-2.zip', 'release': 'Breaking.Bad.S02.720p', 'lang': 'en',
                                  'sub_id': '2', 'imdbid': '0903747', 'title': 'EN | x'})
    assert ret['path'].endswith('Breaking.Bad.S02.720p_en_0_2_0903747.srt')
    assert b'five' in open(ret['path'], 'rb').read() and ret['lang'] == 'en'


def test_subdl_imdb_id_of_the_title_link(subprov):
    loaded, make, errors = subprov
    p = make(loaded['subprov_subdlapi'].SubDLAPIProvider, {'confirmed_title': 'Inception (2010)'})
    html = ('<a href="/subtitle/sd1/other">related tt1111111</a><a href="https://www.imdb.com/title/tt1375666/">IMDb</a>'
            '<div data-language="german" data-language-name="German" style="--rows: 4"></div>'
            '<div data-language="english" data-language-name="English" style="--rows: 9"></div>'
            '<div data-language="arabic" data-language-name="Arabic"></div>')
    p._extractLanguagesFromHTML(html, {'sd_id': 'sd2', 'slug': 'inception'})
    assert [x['language_key'] for x in p.currList] == ['german', 'english', 'arabic']
    assert {x['imdbid'] for x in p.currList} == {'1375666'}


def test_subsource_api_one_entry_per_subtitle_and_one_request(subprov):
    loaded, make, errors = subprov
    p = make(loaded['subprov_subsourceapi'].SubsourceAPIProvider,
             {'confirmed_title': 'Inception (2010)', 'release_title': 'Inception.2010.1080p.BluRay.x264-SPARKS'})
    calls = []
    data = [{'subtitleId': 1, 'language': 'german', 'releaseInfo': ['Inception.2010.WEB-DL', 'Inception.2010.1080p.BluRay.x264-SPARKS'],
             'contributors': [{'displayname': 'me'}]},
            {'subtitleId': 2, 'language': 'english', 'releaseInfo': []},
            {'subtitleId': 3, 'language': 'german', 'releaseInfo': 'Inception.2010.DVDRip'}]

    def getJson(url, post_data=None, apiKey=''):
        calls.append(url)
        return {'success': True, 'data': data}
    p.getJson = getJson
    p.apiLanguages({'movieId': 7}, 'KEY')
    assert [x['language_key'] for x in p.currList] == ['german', 'english']
    assert 'language=' not in calls[0]
    p.currList = []
    p.apiSubtitlesList({'movieId': 7, 'language_key': 'german', 'lang': 'de', 'title': 'German [2]'}, 'KEY')
    assert len(calls) == 1
    # one entry per subtitle, the release of the video as its title, the other release in the description
    assert [(x['sub_id'], x['release']) for x in p.currList] == [('1', 'Inception.2010.1080p.BluRay.x264-SPARKS'), ('3', 'Inception.2010.DVDRip')]
    assert p.currList[0]['desc'] == 'Inception.2010.WEB-DL[/br]Author: me'
    # no release names: the searched title, not the language row
    p.currList = []
    p.apiSubtitlesList({'movieId': 7, 'language_key': 'english', 'lang': 'en', 'title': 'English [1]'}, 'KEY')
    assert p.currList[0]['release'] == 'Inception (2010)'


def test_subsource_web_seasons_skip_bad_numbers(subprov):
    loaded, make, errors = subprov
    p = make(loaded['subprov_subsourceapi'].SubsourceAPIProvider, {'confirmed_title': 'Breaking Bad S02E05'})
    p.webSeasons({'link': 'breaking-bad', 'seasons': [{'season': 1}, {'season': 'x'}, {'season': '2'}, {}]})
    assert [x['link'] for x in p.currList] == ['breaking-bad/season-2', 'breaking-bad/season-1']


def test_subsro_season_pack_and_language_order(subprov):
    loaded, make, errors = subprov
    cls = loaded['subprov_subsro'].SubsRoProvider
    # the season only in the movie name
    assert cls.releaseFits('Breaking Bad - Sezonul 2 WEB-DL', 2, 5)
    assert not cls.releaseFits('Breaking Bad - Sezonul 3 WEB-DL', 2, 5)
    assert cls.releaseFits('Breaking Bad - Sezoanele 1-3 ', 2, 5)
    assert sorted(['fr', 'en', 'ro', 'de'], key=cls.langOrder) == ['de', 'ro', 'en', 'fr']
