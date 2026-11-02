# Offline tests for IPTVPlayer/libs/m3uparser.py (the lists of the LocalMedia host).
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _urlparser(object):
    @staticmethod
    def decorateParamsFromUrl(url):
        return url


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod


@pytest.fixture
def parser():
    saved = dict(sys.modules)
    for name in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.tools",
                 "Plugins.Extensions.IPTVPlayer.libs"):
        _stub(name)
    _stub("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None)
    _stub("Plugins.Extensions.IPTVPlayer.libs.urlparser", urlparser=_urlparser)
    spec = importlib.util.spec_from_file_location("m3uparser_under_test", os.path.join(ROOT, "libs", "m3uparser.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    sys.modules.clear()
    sys.modules.update(saved)


def test_attributes_and_title(parser):
    item = parser.ParseM3u('#EXTM3U\n#EXTINF:-1 tvg-logo="http://x/l.png" group-title="News",CNN\nhttp://x/a.m3u8\n')[0]
    assert (item['title'], item['length'], item['group-title'], item['tvg-logo'], item['uri']) == ('CNN', '-1', 'News', 'http://x/l.png', 'http://x/a.m3u8')


def test_length_without_attributes(parser):
    assert parser.ParseM3u('#EXTM3U\n#EXTINF:125,Song\nhttp://x/a\n')[0]['length'] == '125'


def test_comma_in_quoted_attribute_is_not_the_title_separator(parser):
    item = parser.ParseM3u('#EXTM3U\n#EXTINF:-1 tvg-name="News, Politics" group-title="Info",CNN, International\nhttp://x/a.m3u8\n')[0]
    assert (item['title'], item['tvg-name'], item['group-title']) == ('CNN, International', 'News, Politics', 'Info')


def test_comma_in_single_quoted_attribute_and_apostrophe_in_a_value(parser):
    item = parser.ParseM3u("#EXTM3U\n#EXTINF:-1 tvg-name='A, B',CNN\nhttp://x/a\n#EXTINF:-1 tvg-id=O'Neil,Fox's\nhttp://x/b\n")
    assert (item[0]['title'], item[0]['tvg-name']) == ('CNN', 'A, B')
    assert (item[1]['title'], item[1]['tvg-id']) == ("Fox's", "O'Neil")


def test_stray_quote_falls_back_to_the_first_comma(parser):
    assert parser.ParseM3u('#EXTM3U\n#EXTINF:-1 tvg-name="x,CNN\nhttp://x/a\n')[0]['title'] == 'CNN'


def test_attribute_without_quotes_keeps_the_others(parser):
    item = parser.ParseM3u("#EXTM3U\n#EXTINF:-1 tvg-id=abc tvg-chno='5' group-title=\"Info\" last=z,CNN\nhttp://x/a\n")[0]
    assert (item['tvg-id'], item['tvg-chno'], item['group-title'], item['last'], item['title']) == ('abc', '5', 'Info', 'z', 'CNN')


def test_user_agent_with_commas_and_referer(parser):
    data = '#EXTM3U\n#EXTINF:-1,CNN\n#EXTVLCOPT:http-user-agent=Mozilla/5.0 (KHTML, like Gecko) a=b\n#EXTVLCOPT:http-referrer="http://r/"\n#EXTVLCOPT:program=7\nhttp://x/a\n'
    item = parser.ParseM3u(data)[0]
    assert (item['user_agent'], item['referer'], item['program-id']) == ('Mozilla/5.0 (KHTML, like Gecko) a=b', 'http://r/', '7')


def test_entries_without_extinf_get_their_file_name(parser):
    items = parser.ParseM3u('#EXTM3U\n/media/hdd/My%20Song.mp3\nhttp://x/dir/b.mp4?token=1|User-Agent=a\nmusic\\c.mp3\n')
    assert [item['title'] for item in items] == ['My Song.mp3', 'b.mp4', 'c.mp3']
    assert all(item['f_type'] == 'inf' for item in items)


def test_list_without_header_only_when_allowed(parser):
    data = '/media/hdd/a.mp3\n/media/hdd/b.mp3\n'
    assert parser.ParseM3u(data) == []
    assert [item['uri'] for item in parser.ParseM3u(data, True)] == ['/media/hdd/a.mp3', '/media/hdd/b.mp3']


def test_web_page_is_no_list(parser):
    assert parser.ParseM3u('<html>\n<body>nothing</body>\n') == []


def test_blank_lines(parser):
    items = parser.ParseM3u('\n\r\n#EXTM3U\r\n\r\n#EXTINF:-1,CNN\r\n\r\n\r\nhttp://x/a\r\n')
    assert [(item['title'], item['uri']) for item in items] == [('CNN', 'http://x/a')]


def test_import_entry(parser):
    item = parser.ParseM3u('#EXTM3U\n#EXTIMPORT:0,Other list\nhttp://x/l.m3u\n')[0]
    assert (item['f_type'], item['title'], item['uri']) == ('import', 'Other list', 'http://x/l.m3u')
