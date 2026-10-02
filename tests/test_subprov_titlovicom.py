# -*- coding: utf-8 -*-
# Offline tests for IPTVPlayer/subproviders/subprov_titlovicom.py (titlovi.com via the API of the Kodi add-on
# service.subtitles.titlovi): login / token cache / 401 re-login, search parameters, result list, download.
# The API answers are hand-made in the shape the add-on reads (gettoken: Token/UserId/ExpirationDate/UserName,
# search: SubtitleResults[] with Id/Type/Title/Year/Season/Episode/Release/Lang/DownloadCount/Rating/Date).
import importlib.util
import io
import json
import os
import sys
import types
import urllib.parse
import zipfile

import pytest

from test_isubprovider_files import files  # noqa: F401 - base class with patched file helpers
from test_isubprovider_imdb import ROOT, provider  # noqa: F401

SRT = u'1\n00:00:01,000 --> 00:00:02,000\nŽivjeli, čaša!\n'


class _Val(object):
    def __init__(self, value):
        self.value = value


class _Ph(object):
    @staticmethod
    def getSearchGroups(data, pattern, grupsNum=1, ignoreCase=False):
        import re
        m = re.search(pattern, data)
        return [m.group(1) if m else '']


class _FakeApi(object):
    """pCommon stand-in: getPage for the API (answers per URL path, in order), saveWebFile for the download"""
    ph = _Ph

    def __init__(self, answers, download=None):
        self.answers = answers  # {'gettoken': [(code, body)], 'search': [(code, body)]}
        self.download = download
        self.requests = []
        self.meta = {}

    def getPage(self, url, params={}, post=None):
        self.requests.append((url, dict(params), post))
        path = urllib.parse.urlparse(url).path.rsplit('/', 1)[-1]
        code, body = self.answers[path].pop(0)
        self.meta = {'status_code': code}
        ignored = any(a <= code <= b for a, b in params.get('ignore_http_code_ranges', []))
        return (code == 200 or ignored), body

    def saveWebFile(self, filePath, url, params={}, post=None):
        self.requests.append((url, dict(params), post))
        self.meta = {'content-disposition': 'attachment; filename=123-breaking.bad.s02e05.zip', 'url': url, 'status_code': 200}
        with open(filePath, 'wb') as f:
            f.write(self.download)
        return {'sts': True, 'fsize': len(self.download)}


def _query(url):
    return urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)


def _token(token='TOK', userid=42):
    return 200, json.dumps({'ExpirationDate': '2099-01-01T00:00:00.000', 'Token': token, 'UserId': userid, 'UserName': 'me'})


def _results(*items):
    return 200, json.dumps({'ResultsFound': len(items), 'SubtitleResults': list(items)})


def _sub(id, lang, release, type=2, season=2, episode=5):
    return {'Id': id, 'Type': type, 'Title': 'Breaking Bad', 'Year': 2008, 'Season': season, 'Episode': episode, 'Release': release,
            'Lang': lang, 'DownloadCount': 10, 'Rating': 4.5, 'Date': '2010-05-01T10:00:00'}


@pytest.fixture
def titlovi(files, monkeypatch):  # noqa: F811
    base, _tmp, baseErrors = files
    saved = dict(sys.modules)
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(titlovi_login=_Val(''), titlovi_password=_Val(''))))
    errors = []
    mods = {
        'Components.config': dict(config=cfg),
        'Plugins.Extensions.IPTVPlayer.components.isubprovider': dict(CBaseSubProviderClass=type(base), CSubProviderBase=object),
        'Plugins.Extensions.IPTVPlayer.components.iptvplayerinit': dict(TranslateTXT=lambda s: s, SetIPTVPlayerLastHostError=errors.append),
        'Plugins.Extensions.IPTVPlayer.p2p3.UrlLib': dict(urllib_urlencode=urllib.parse.urlencode),
        'Plugins.Extensions.IPTVPlayer.tools.iptvtools': dict(printDBG=lambda *a: None, printExc=lambda *a: None, GetDefaultLang=lambda: 'sr'),
    }
    for name, attrs in mods.items():
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod
    spec = importlib.util.spec_from_file_location('subprov_titlovicom_under_test', os.path.join(ROOT, 'subproviders', 'subprov_titlovicom.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # the base class reports its download errors through its own SetIPTVPlayerLastHostError
    monkeypatch.setitem(type(base).converFileToUtf8.__globals__, 'SetIPTVPlayerLastHostError', errors.append)

    def make(answers, download=None, login='', password=''):
        cfg.plugins.iptvplayer.titlovi_login.value = login
        cfg.plugins.iptvplayer.titlovi_password.value = password
        p = module.TitlovicomProvider.__new__(module.TitlovicomProvider)
        p.__dict__.update(base.__dict__)
        p.cm = _FakeApi(answers, download)
        p.currList, p.currItem, p.moreMode = [], {}, False
        p.params = {'confirmed_title': 'Breaking Bad S02E05', 'movie_title': 'Breaking.Bad.S02E05.720p.BluRay.x264-REWARD'}
        p.dInfo = {}
        p.API_HEADER = {'User-Agent': 'UA'}
        p.getSupportedFormats = lambda all=False: ['srt', 'vtt']
        p.imdbGetOrginalByTitle = lambda imdbid: (True, {'title': 'Breaking Bad'})
        return p
    module._TOKEN.clear()
    yield module, make, errors
    sys.modules.clear()
    sys.modules.update(saved)


def test_no_account_message_without_requests(titlovi):
    module, make, errors = titlovi
    p = make({})
    p.getMoviesTitles({'name': 'category'}, 'get_type')
    assert p.currList == [] and p.cm.requests == []
    assert errors == ['Titlovi.com needs a free titlovi.com account. Enter login and password in the E2iPlayer settings.']


def test_wrong_credentials(titlovi):
    module, make, errors = titlovi
    p = make({'gettoken': [(401, '')]}, login='me', password='bad')
    p.getMoviesTitles({'name': 'category'}, 'get_type')
    assert p.currList == [] and 'login failed for user "me"' in errors[-1]
    url, params, post = p.cm.requests[0]
    # like the add-on: POST, the credentials in the query, empty body
    assert url.startswith('https://kodi.titlovi.com/api/subtitles/gettoken?') and post == '' and params['raw_post_data']
    assert _query(url) == [('username', 'me'), ('password', 'bad'), ('returnStatusCode', 'True'), ('json', 'True')]


def test_api_access_disabled(titlovi):
    module, make, errors = titlovi
    p = make({'gettoken': [(403, '')]}, login='me', password='pw')
    assert not p._login() and 'API access is disabled' in errors[-1]


def test_series_search_list_and_download(titlovi):
    module, make, errors = titlovi
    zipBuf = io.BytesIO()
    with zipfile.ZipFile(zipBuf, 'w') as z:
        z.writestr('Breaking.Bad.S02E05.srt', SRT.encode('cp1250'))
    p = make({'gettoken': [_token()],
              'search': [_results(_sub(1, 'Hrvatski', 'Breaking.Bad.S02E05.HDTV.XviD-0TV'),
                                  _sub(2, 'Srpski', 'Breaking.Bad.S02E05.HDTV.XviD-0TV'),
                                  _sub(3, 'Srpski', 'Breaking.Bad.S02E05.720p.BluRay.x264-REWARD'),
                                  _sub(4, 'Cirilica', 'Breaking.Bad.S02E05.720p.BluRay.x264-REWARD'),
                                  _sub(5, 'English', 'whatever'),
                                  {'Title': 'no id'})]},
             download=zipBuf.getvalue(), login='me', password='pw')
    cItem = {'imdbid': '0903747', 'season': '2', 'episode': '5', 'title': 's02e05 Breathe', 'base_title': 'Breaking Bad'}
    p.getSearchList(cItem, 'get_subtitles')
    assert errors == []

    url, params, post = p.cm.requests[1]
    assert url.startswith('https://kodi.titlovi.com/api/subtitles/search?') and post is None
    q = _query(url)
    assert q[0] == ('imdbid', 'tt0903747')
    assert [v for k, v in q if k == 'season'] == ['0', '2'] and [v for k, v in q if k == 'episode'] == ['-1', '0', '5']
    # the user's language (sr: Srpski and Cirilica) first
    assert dict(q)['lang'] == 'Srpski|Cirilica|Hrvatski|Bosanski|Slovenski|Makedonski|English'
    assert (dict(q)['token'], dict(q)['userid'], dict(q)['json']) == ('TOK', '42', 'True')

    # by language, the matching release first within a language; the item without Id is dropped
    assert [x['sub_id'] for x in p.currList] == ['3', '2', '4', '1', '5']
    first = p.currList[0]
    assert first['lang'] == 'sr' and first['category'] == 'get_subtitles'
    assert first['url'] == 'https://titlovi.com/download/?type=2&mediaid=3'
    assert first['title'] == '[sr] Breaking Bad (2008) S02E05 Breaking.Bad.S02E05.720p.BluRay.x264-REWARD'
    assert [x['lang'] for x in p.currList] == ['sr', 'sr', 'sr', 'hr', 'en']

    # the download: the add-on's headers, the archive listed, then the file converted to UTF-8 (cp1250 fallback)
    hrItem = p.currList[3]
    p.currList = []
    p.getSubtitlesList(hrItem)
    url, params, post = p.cm.requests[-1]
    assert url == 'https://titlovi.com/download/?type=2&mediaid=1' and params['header']['Referer'] == 'www.titlovi.com'
    assert len(p.currList) == 1 and p.currList[0]['type'] == 'subtitle'
    ret = p.downloadSubtitleFile(p.currList[0])
    assert sorted(ret) == ['fps', 'imdbid', 'lang', 'path', 'sub_id', 'title']
    assert os.path.basename(ret['path']) == 'Breaking.Bad.S02E05_hr_0_1_0903747.srt'
    with open(ret['path'], 'rb') as f:
        assert f.read() == SRT.encode('utf-8')


def test_cyrillic_uses_cp1251(titlovi, tmp_path):
    module, make, errors = titlovi
    p = make({})
    src = tmp_path / 'in.srt'
    src.write_bytes(u'1\n00:00:01,000 --> 00:00:02,000\nЗдраво\n'.encode('cp1251'))
    ret = p.downloadSubtitleFile({'title': 'x', 'lang': 'sr', 'lang_name': 'Cirilica', 'sub_id': '4', 'imdbid': '1', 'file_path': str(src)})
    with open(ret['path'], 'rb') as f:
        assert u'Здраво'.encode('utf-8') in f.read()


def test_token_cached_and_relogin_on_401(titlovi):
    module, make, errors = titlovi
    p = make({'gettoken': [_token('A', 1), _token('B', 1)],
              'search': [_results(), _results(), (401, ''), _results(_sub(9, 'Hrvatski', 'r', type=1))]}, login='me', password='pw')
    movie = {'imdbid': '0133093', 'title': 'The Matrix', 'base_title': 'The Matrix'}
    p.imdbGetOrginalByTitle = lambda imdbid: (True, {'title': 'The Matrix'})
    p.getSearchList(movie, 'get_subtitles')
    # no results by IMDb id: the title search of the add-on, movie types 1 and 3, same token
    paths = [urllib.parse.urlparse(u).path.rsplit('/', 1)[-1] for u, _p, _d in p.cm.requests]
    assert paths == ['gettoken', 'search', 'search']
    q = _query(p.cm.requests[2][0])
    assert q[0] == ('query', 'The Matrix') and [v for k, v in q if k == 'type'] == ['1', '3'] and 'season' not in dict(q)
    assert p.currList == []

    # next search: the cached token, 401 -> one new login, the search again with the new token
    p.getSearchList(movie, 'get_subtitles')
    paths = [urllib.parse.urlparse(u).path.rsplit('/', 1)[-1] for u, _p, _d in p.cm.requests]
    assert paths == ['gettoken', 'search', 'search', 'search', 'gettoken', 'search']
    assert dict(_query(p.cm.requests[-1][0]))['token'] == 'B'
    assert [x['url'] for x in p.currList] == ['https://titlovi.com/download/?type=1&mediaid=9']
    assert errors == []


def test_expiration_parsing(titlovi):
    module, make, errors = titlovi
    assert module._parseExpiration('1970-01-02T00:00:00.1234567') == 86400
    assert module._parseExpiration(None) == 0 and module._parseExpiration('soon') == 0
