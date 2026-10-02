# -*- coding: utf-8 -*-
# Offline tests for the smaller site providers (subprov_ytssubs / indexsubtitle / justsubtitles / subtitlecat /
# wyzie / subtitlesmora): unexpected JSON shapes must not raise (an exception leaves the widget "downloading"),
# the language keys of subtitlecat, archives inside archives, MicroDVD from Wyzie, the archive.org file list.
import importlib.util
import json
import os
import re
import sys
import types
import urllib.parse
import zipfile

import pytest

from test_isubprovider_files import files  # noqa: F401 - base class with patched file helpers
from test_isubprovider_imdb import ROOT, provider  # noqa: F401

SRT = u'1\n00:00:01,000 --> 00:00:02,000\nGrüße\n'


class _Val(object):
    def __init__(self, value):
        self.value = value


class _Ph(object):
    @staticmethod
    def getSearchGroups(data, pattern, grupsNum=1, ignoreCase=False):
        m = re.search(pattern, data)
        return [m.group(1) if m else '']


class _Cm(object):
    """pCommon stand-in: getPage answers in order"""
    ph = _Ph

    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []
        self.meta = {}

    def getPage(self, url, params={}, post=None):
        self.requests.append((url, post))
        sts, body = self.answers.pop(0)
        self.meta = {'status_code': 200 if sts else 500}
        return sts, body

    @staticmethod
    def getBaseUrl(url):
        return '/'.join(url.split('/')[:3]) + '/'


@pytest.fixture
def load(files, tmp_path):  # noqa: F811
    base, _tmp, baseErrors = files
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(wyzieapi=_Val('KEY'))))
    errors = []
    mods = {
        'Components.config': dict(config=cfg),
        'Plugins.Extensions.IPTVPlayer.components.isubprovider': dict(CBaseSubProviderClass=type(base), CSubProviderBase=object),
        'Plugins.Extensions.IPTVPlayer.components.iptvplayerinit': dict(TranslateTXT=lambda s: s, SetIPTVPlayerLastHostError=errors.append),
        'Plugins.Extensions.IPTVPlayer.p2p3.UrlLib': dict(urllib_urlencode=urllib.parse.urlencode, urllib_quote_plus=urllib.parse.quote_plus,
                                                          urllib_quote=urllib.parse.quote),
        'Plugins.Extensions.IPTVPlayer.tools.iptvtools': dict(printDBG=lambda *a: None, printExc=lambda *a: None, GetDefaultLang=lambda: 'de'),
    }
    type(base).converFileToUtf8.__globals__['SetIPTVPlayerLastHostError'] = errors.append

    def make(name, cls, answers=(), title='Inception 2010', dInfo=None):
        saved = {k: sys.modules.get(k) for k in mods}
        for modName, attrs in mods.items():
            mod = types.ModuleType(modName)
            mod.__dict__.update(attrs)
            sys.modules[modName] = mod
        spec = importlib.util.spec_from_file_location('subprov_%s_under_test' % name, os.path.join(ROOT, 'subproviders', 'subprov_%s.py' % name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for k, v in saved.items():
            if v is not None:
                sys.modules[k] = v
        p = getattr(module, cls).__new__(getattr(module, cls))
        p.__dict__.update(base.__dict__)
        p.cm = _Cm(answers)
        p.currList, p.currItem, p.moreMode = [], {}, False
        p.params = {'confirmed_title': title, 'movie_title': title, 'discover_info': dInfo or {}}
        p.dInfo = dInfo or {}
        p.HTTP_HEADER = {'User-Agent': 'UA'}
        p.defaultParams = {'header': p.HTTP_HEADER}
        p.getSupportedFormats = lambda all=False: ['srt', 'vtt', 'sub']
        p.cleanHtmlStr = lambda s: re.sub(r'<[^>]*>', '', s).strip()
        return module, p
    return make, errors, tmp_path


def test_ytssubs_search_answer_not_a_list(load):
    make, errors, _tmp = load
    for body in ('{"error": "blocked"}', '"text"', '["x", 1, {"imdb": "tt1375666", "movie": "Inception 2010"}]'):
        _m, p = make('ytssubs', 'YtsSubsProvider', [(True, body)])
        p.getMoviesList({'name': 'category'}, 'get_languages')
    assert [it['imdbid'] for it in p.currList] == ['tt1375666']
    _m, p = make('ytssubs', 'YtsSubsProvider', title='Breaking Bad S02E05')
    p.getMoviesList({'name': 'category'}, 'get_languages')
    assert errors[-1] == 'This subtitle provider has subtitles for movies only.' and p.cm.requests == []


def test_indexsubtitle_search_and_language_menu(load):
    make, errors, _tmp = load
    _m, p = make('indexsubtitle', 'IndexSubtitleProvider', [(True, '{"message": "no"}')])
    p.getSearchList({'name': 'category'}, 'get_languages')
    assert p.currList == []
    _m, p = make('indexsubtitle', 'IndexSubtitleProvider', [(True, json.dumps([{'title': None, 'url': '/x'}, 'junk', {'title': 'Inception (2010)', 'url': '/inception'}]))])
    p.getSearchList({'name': 'category'}, 'get_languages')
    assert [it['title'] for it in p.currList] == ['Inception (2010)', '']
    rows = [{'title': 'Inception.2010.720p', 'url': 'inception/French/1', 'language': 'French'},
            {'title': None, 'url': 'inception/English/2', 'language': 'English', 'author': 'x', 'comment': None},
            {'title': 'Inception.2010.1080p', 'url': 'inception/German/3', 'language': 'German', 'author': {'name': 'Tom'}},
            {'title': 'Inception.2010', 'url': 'inception/Arabic/4', 'language': 'Arabic'}, 'junk',
            {'title': 'Inception.2010.BluRay', 'url': 'inception/French/5', 'language': 'French'}]
    page = 'var ttl = 77; table({data: %s, columns: []})' % json.dumps(rows)
    _m, p = make('indexsubtitle', 'IndexSubtitleProvider', [(True, page)])
    p.getLanguages({'name': 'category', 'url': 'https://indexsubtitle.cc/inception'}, 'get_subtitles')
    assert [it['title'] for it in p.currList] == ['German [de] (1)', 'English [en] (1)', 'Arabic [ar] (1)', 'French [fr] (2)']
    german = p.currList[0]
    assert german['ttl'] == '77' and german['page'] == 'https://indexsubtitle.cc/inception'
    p.currList = []
    p.getSubtitlesList(german, 'get_files')
    sub = p.currList[0]
    assert sub['title'] == '[de] Inception.2010.1080p' and sub['sub_id'] == '3' and sub['site_lang'] == 'German' and sub['desc'] == 'Author: Tom'
    assert 'rows' not in sub


def test_justsubtitles_odd_action_answers(load):
    make, errors, _tmp = load
    _m, p = make('justsubtitles', 'JustSubtitlesProvider', [(False, '')])
    p.getSubtitlesList({'tmdb_id': '27205', 'movie': 'Inception'}, 'get_files')
    assert errors[-1] == 'Failed to connect to server "https://www.justsubtitles.com/".'
    answer = '0:["$@1"]\n1:%s\n' % json.dumps({'results': 'bad', 'subtitles': [{'url': '/subtitle/3197651-3200000.rar', 'release_name': 'Inception.2010.1080p', 'author': None},
                                                                              'junk', {'url': None}]})
    _m, p = make('justsubtitles', 'JustSubtitlesProvider', [(True, answer), (True, '1:"text"\n')])
    p.getActionId = lambda tmdbId: ('abc', '')
    p.getSubtitlesList({'tmdb_id': '27205', 'movie': 'Inception'}, 'get_files')
    assert [(it['lang'], it['release'], it['imdbid'], it['sub_url']) for it in p.currList] == [
        ('de', 'Inception.2010.1080p', '', 'https://dl.subdl.com/subtitle/3197651-3200000.zip')]
    _m, p = make('justsubtitles', 'JustSubtitlesProvider', title='Breaking Bad S02E05')
    p.getSearchList({'name': 'category'}, 'get_subtitles')
    assert errors[-1] == 'This subtitle provider has subtitles for movies only.'


def test_subtitlecat_language_keys(load):
    make, errors, _tmp = load
    page = ''.join('<a id="download_%s" href="/subs/1/Inception.%s.srt">x</a>' % (c, c) for c in ('zh-CN', 'zh-TW', 'en', 'sr', 'sr-ME', 'de', 'iw')) + \
        "translate_from_server_folder('x', 'Inception.srt', '/subs/1/')"
    _m, p = make('subtitlecat', 'SubtitlecatProvider', [(True, page)])
    p.MAIN_URL = 'https://www.subtitlecat.com/'
    p.getSubtitlesList({'url': 'https://www.subtitlecat.com/subs/1/Inception.html', 'base_title': 'Inception', 'orig_lang': ''})
    titles = [it['title'] for it in p.currList]
    # the original of an unnamed language is not "machine translated" and comes right after de / en
    assert titles[:3] == ['[de] Inception (machine translated)', '[en] Inception (machine translated)', '[--] Inception']
    assert sorted(it['lang'] for it in p.currList) == ['--', 'de', 'en', 'he', 'sr', 'zh', 'zh-tw']
    assert [it['url'] for it in p.currList if it['lang'] == 'sr'] == ['https://www.subtitlecat.com/subs/1/Inception.sr.srt']


def _zip(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)


def test_archive_in_archive(load):
    make, errors, tmp_path = load
    for name, cls in (('ytssubs', 'YtsSubsProvider'), ('moviesubtitles', 'MovieSubtitlesProvider'), ('indexsubtitle', 'IndexSubtitleProvider'),
                      ('justsubtitles', 'JustSubtitlesProvider')):
        d = tmp_path / ('unpacked_' + name)
        d.mkdir()
        _zip(str(d / 'Inception.Pack.zip'), [('Inception.2010.720p.srt', SRT.encode('utf-8'))])
        (d / 'Inception.2010.1080p.srt').write_bytes(SRT.encode('utf-8'))
        _m, p = make(name, cls)
        p.listArchiveFiles({'name': 'category', 'category': 'get_files', 'path': str(d), 'lang': 'de', 'sub_id': '1', 'imdbid': ''})
        assert [(it['type'], it['category'], it['title']) for it in p.currList] == [('subtitle', '', 'Inception.2010.1080p'),
                                                                                  ('category', 'unpack_archive', 'Inception.Pack')], name
        inner = p.currList[1]
        p.currList = []
        p.unpackInnerArchive(inner)
        assert [(it['type'], it['title']) for it in p.currList] == [('subtitle', 'Inception.2010.720p')], name
        ret = p.downloadSubtitleFile(p.currList[0])
        assert open(ret['path'], 'rb').read() == SRT.encode('utf-8') and ret['lang'] == 'de'


def test_wyzie_microdvd_and_odd_rows(load):
    make, errors, _tmp = load
    _m, p = make('wyzie', 'WyzieProvider', [(True, json.dumps([{'url': 'https://sub.wyzie.io/c/1', 'language': 'de', 'format': 'sub', 'releases': 'one string'},
                                                                'junk', {'url': None}]))])
    p.getLanguages({'name': 'category', 'imdbid': '1375666', 'base_title': 'Inception'}, 'get_subtitles')
    assert [it['title'] for it in p.currList] == ['German [de] (1)'] and p.currList[0]['rows'][0]['releases'] == []
    p.downloadBinary = lambda url, params={}: (True, u'{1}{100}Grüße\n'.encode('cp1252'))
    ret = p.downloadSubtitleFile({'release': 'Inception', 'lang': 'de', 'sub_id': '1', 'imdbid': '1375666', 'url': 'https://sub.wyzie.io/c/1'})
    assert ret['path'].endswith('.sub') and open(ret['path'], 'rb').read() == u'{1}{100}Grüße\n'.encode('utf-8')
    p.downloadBinary = lambda url, params={}: (True, b'{"code": 404, "message": "not found"}')
    assert p.downloadSubtitleFile({'release': 'I', 'lang': 'de', 'sub_id': '1', 'imdbid': '1', 'url': 'x'}) == {}
    assert errors[-1] == 'The server did not send a subtitle file.'


def test_subtitlesmora_list_cache_and_cp1256(load):
    make, errors, _tmp = load
    meta = {'files': [{'name': 'Inception.2010.1080p.mora.25r.srt'}, {'name': 'Inception.Something.2015.srt'}, {'name': 'Inception.2010.jpg'},
                      {'name': None}, 'junk']}
    module, p = make('subtitlesmora', 'SubtitlesMoraProvider', [(True, json.dumps(meta))])
    module.FILE_LIST.clear()
    p.getSubtitlesList({'name': 'category'})
    assert [it['file_name'] for it in p.currList] == ['Inception.2010.1080p.mora.25r.srt']
    assert module.FILE_LIST['files'][0] == ('Inception.2010.1080p.mora.25r.srt', 'inception.2010.1080p.mora.25r.')
    # the second search comes from the cache (no answer queued)
    p.currList = []
    p.getSubtitlesList({'name': 'category'})
    assert len(p.currList) == 1
    p.downloadBinary = lambda url, params={}: (True, (u'1\n00:00:01,000 --> 00:00:02,000\nمرحبا\n').encode('cp1256'))
    ret = p.downloadSubtitleFile(p.currList[0])
    assert u'مرحبا' in open(ret['path'], 'rb').read().decode('utf-8') and ret['sub_id'] == 'mora25r'
