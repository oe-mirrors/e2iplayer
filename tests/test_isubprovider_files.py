# Offline tests for the file helpers of IPTVPlayer/components/isubprovider.py: converFileToUtf8 (BOM, UTF-8,
# code page of the language without uchardet) and downloadArchive / downloadFileData (type from the first bytes).
import importlib.util
import io
import os
import re
import shutil
import zipfile

import pytest

from test_isubprovider_imdb import ROOT, provider  # noqa: F401 - the stubbed module fixture


class _Ph(object):
    @staticmethod
    def getSearchGroups(data, pattern, grupsNum=1, ignoreCase=False):
        m = re.search(pattern, data)
        return [m.group(1) if m else '']


class _Meta(object):
    """pCommon stand-in: one saveWebFile answer and its meta (status 200 unless given)"""
    ph = _Ph

    def __init__(self, body, meta):
        self.body, self.answerMeta, self.calls, self.meta = body, meta, [], {}

    def saveWebFile(self, filePath, url, params=None, post=None):
        self.calls.append((url, dict(params or {})))
        self.meta = dict({'status_code': 200}, **self.answerMeta)
        with open(filePath, 'wb') as f:
            f.write(self.body)
        return {'sts': len(self.body) > 0, 'fsize': len(self.body)}


@pytest.fixture
def files(provider, tmp_path):  # noqa: F811
    p = provider([])
    g = type(p).converFileToUtf8.__globals__
    errors = []
    g.update(ensure_binary=lambda x: x, GetDefaultLang=lambda: 'de', SetIPTVPlayerLastHostError=errors.append,
             GetTmpDir=lambda f='': str(tmp_path / ('tmp_' + f.strip('/'))), RemoveDisallowedFilenameChars=lambda s: s.replace('/', '_'),
             printExc=lambda *a: None, rm=lambda f: None)

    def _mkdirs(d):
        os.makedirs(d, exist_ok=True)
        return True
    g.update(rmtree=lambda d, ignore_errors=False: shutil.rmtree(d, ignore_errors=True), mkdirs=_mkdirs,
             GetSubtitlesDir=lambda f='': str(tmp_path / f))
    g['os_path'] = os.path
    # the real format detection of the player (plain Python, its imports are stubbed)
    spec = importlib.util.spec_from_file_location("iptvsubtitles_for_files", os.path.join(ROOT, "tools", "iptvsubtitles.py"))
    subs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subs)
    g['IPTVSubtitlesHandler'] = subs.IPTVSubtitlesHandler
    # same result with or without uchardet on the test machine: it is "missing"
    p.iptv_execute = lambda cmd: {'sts': False, 'code': 127, 'data': ''}
    p.TMP_FILE_NAME, p.TMP_DIR_NAME = '.f', '.d/'
    p.getMaxFileSize = lambda: 1024 * 1024
    p.unpackArchive = lambda arch, d: (shutil.rmtree(d, ignore_errors=True), zipfile.ZipFile(arch).extractall(d), True)[-1]
    return p, tmp_path, errors


def _convert(p, tmp_path, raw, lang):
    src, dst = tmp_path / 'in.srt', tmp_path / 'out.srt'
    src.write_bytes(raw)
    assert p.converFileToUtf8(str(src), str(dst), lang)
    return dst.read_bytes()


def test_utf8_bom_and_codepages(files):
    p, tmp_path, errors = files
    text = u'1\n00:00:01,000 --> 00:00:02,000\n'
    assert _convert(p, tmp_path, (text + u'Grüße').encode('utf-8'), 'de') == (text + u'Grüße').encode('utf-8')
    assert _convert(p, tmp_path, b'\xef\xbb\xbf' + u'Grüße'.encode('utf-8'), 'de') == u'Grüße'.encode('utf-8')
    assert _convert(p, tmp_path, u'Grüße'.encode('utf-16'), 'de') == u'Grüße'.encode('utf-8')
    # no uchardet on the PC: the code page of the language
    assert _convert(p, tmp_path, u'Grüße'.encode('cp1252'), 'de') == u'Grüße'.encode('utf-8')
    assert _convert(p, tmp_path, u'مرحبا'.encode('cp1256'), 'ar') == u'مرحبا'.encode('utf-8')
    assert _convert(p, tmp_path, u'Žluťoučký'.encode('cp1250'), 'cs') == u'Žluťoučký'.encode('utf-8')
    assert _convert(p, tmp_path, u'Привет'.encode('cp1251'), 'ru') == u'Привет'.encode('utf-8')


def _zip(name, data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(name, data)
    return buf.getvalue()


def test_download_archive_by_content(files):
    p, tmp_path, errors = files
    # a redirect page name and a content-disposition without a file name: the bytes decide
    p.cm = _Meta(_zip('movie.srt', b'1\n00:00:01,000 --> 00:00:02,000\nHi\n'), {'content-disposition': 'attachment', 'url': 'https://x/download-1.html'})
    d = p.downloadArchive('https://x/download-1.html', {'header': {}})
    assert d and (tmp_path / 'tmp_.d' / 'movie.srt').read_bytes().startswith(b'1\n')
    # saveWebFile follows redirects itself and refuses max_data_size (the size is checked afterwards)
    assert 'max_data_size' not in p.cm.calls[0][1] and 'allow_redirects' not in p.cm.calls[0][1]
    # a plain subtitle body, file name from an unquoted content-disposition
    p.cm = _Meta(b'WEBVTT\n\n00:01.000 --> 00:02.000\nHi\n', {'content-disposition': 'attachment; filename=Movie.Name.vtt'})
    d = p.downloadArchive('https://x/get?id=1')
    assert d and (tmp_path / 'tmp_.d' / 'Movie.Name.vtt').exists()
    # an HTML error page is no subtitle
    p.cm = _Meta(b'<html>limit reached</html>', {})
    assert p.downloadArchive('https://x/get?id=2') is None and errors
    # saveWebFile also stores the body of an error page - a 404 is no download
    p.cm = _Meta(b'1\n00:00:01,000 --> 00:00:02,000\nHi\n', {'status_code': 404})
    assert p.downloadBinary('https://x/get?id=3') == (False, None)
    # too big
    p.cm = _Meta(b'x' * (1024 * 1024 + 1), {})
    assert p.downloadBinary('https://x/get?id=4') == (False, None)


def test_download_archive_plain_formats_and_names(files):
    p, tmp_path, errors = files
    # MicroDVD is a subtitle too (the player reads it), RFC 5987 file name, an apostrophe in a quoted name
    p.cm = _Meta(b'{1}{1}25\n{25}{50}Hi\n', {'content-disposition': "attachment; filename*=UTF-8''Ocean%27s%20Eleven.txt"})
    assert p.downloadArchive('https://x/a') and (tmp_path / 'tmp_.d' / "Ocean's Eleven.sub").exists()
    p.cm = _Meta(b'[Script Info]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,,,0,0,0,,Hi\n', {'content-disposition': 'attachment; filename="Ocean\'s.ass"'})
    assert p.downloadArchive('https://x/b') and (tmp_path / 'tmp_.d' / "Ocean's.ass").exists()
    # a JSON error object is no MicroDVD file
    p.cm = _Meta(b'{"error": "limit"}', {})
    assert p.downloadArchive('https://x/c') is None


def test_file_name_wanted_info_and_save(files):
    p, tmp_path, errors = files
    assert p.subtitleFileName('.My/Movie_x', 'de', 7, 'tt123', 'srt') == 'My.Movie.x_de_0_7_123.srt'
    assert p.subtitleFileName('M', 'de', 7, '', 'sub', 23.976) == 'M_de_0_7__fps23.976.sub'
    assert p.subtitleFileName('Y', 'en', 0, 'dQw4ttX', 'vtt') == 'Y_en_0_0_dQw4ttX.vtt'
    p.params = {'confirmed_title': 'Breaking Bad S02E05', 'discover_info': {'season': 1, 'episode': 1}}
    assert p.wantedInfo() == ('Breaking Bad', None, 2, 5)
    p.params = {'confirmed_title': 'Breaking Bad', 'discover_info': {'season': 3, 'episode': 4}, 'release_title': 'BB.S03E04.720p-X'}
    assert p.wantedInfo() == ('Breaking Bad', None, 3, 4) and p.releaseName() == 'BB.S03E04.720p-X'
    srt = u'1\n00:00:01,000 --> 00:00:02,000\nGrüße\n'
    # the encoding the site reports wins, else the code page of the language
    ret = p.saveSubtitleData(srt.encode('cp1250'), 'T', 'cs', 9, 'tt5', encoding='cp1250')
    assert ret['path'].endswith('T_cs_0_9_5.srt') and open(ret['path'], 'rb').read() == srt.encode('utf-8')
    ret = p.saveSubtitleData(srt.encode('cp1252'), 'T2', 'de', 9, '')
    assert open(ret['path'], 'rb').read() == srt.encode('utf-8') and ret['imdbid'] == ''
    assert p.saveSubtitleData(b'<html>no</html>', 'T3', 'de', 9, '') == {} and errors
