# Offline tests for the Python subtitle parsers of IPTVPlayer/tools/iptvsubtitles.py (used when the
# C parser extension is missing or fails): SRT, ASS/SSA, MicroDVD, SubViewer, TMPlayer, MPL2.
import importlib.util
import io
import os
import re
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Helper(object):
    @staticmethod
    def getSearchGroups(data, pattern, grupsNum=1, ignoreCase=False):
        m = re.search(pattern, data, re.I if ignoreCase else 0)
        return [m.group(i + 1) if m else '' for i in range(grupsNum)]


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod


@pytest.fixture
def handler(tmp_path):
    saved = dict(sys.modules)
    for name in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.tools",
                 "Plugins.Extensions.IPTVPlayer.libs", "Plugins.Extensions.IPTVPlayer.p2p3"):
        _stub(name)
    _stub("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
          GetSubtitlesDir=lambda f="": str(tmp_path / f), byteify=lambda x, *a, **k: x,
          IsSubtitlesParserExtensionCanBeUsed=lambda: False)
    _stub("Plugins.Extensions.IPTVPlayer.libs.pCommon", CParsingHelper=_Helper)
    _stub("Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings", ensure_str=lambda s, *a, **k: s)
    spec = importlib.util.spec_from_file_location("iptvsubtitles_under_test", os.path.join(ROOT, "tools", "iptvsubtitles.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def load(name, text, fps=0):
        path = tmp_path / name
        with io.open(str(path), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        h = mod.IPTVSubtitlesHandler()
        sts = h.loadSubtitles(str(path), fps=fps)
        return sts, h.subAtoms

    yield load
    sys.modules.clear()
    sys.modules.update(saved)


ASS = u"""\ufeff[Script Info]
Title: test
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize
Style: Default,Arial,20

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:05.00,0:00:07.50,Default,,0,0,0,,Hello, {\\i1}world{\\i0}!
Comment: 0,0:00:06.00,0:00:08.00,Default,,0,0,0,,not shown
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{\\an8}first\\Nsecond line
Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,{\\p1}m 0 0 l 10 10{\\p0}
"""


def test_ass(handler):
    sts, atoms = handler("movie.ass", ASS)
    assert sts
    assert atoms == [{'start': 1000, 'end': 2000, 'text': 'first\nsecond line'},
                     {'start': 5000, 'end': 7500, 'text': 'Hello, world!'}]


def test_ssa_extension_and_field_order(handler):
    text = u"[Events]\nFormat: Start, End, Text\nDialogue: 0:00:01.50,0:00:02.25,a, b\n"
    sts, atoms = handler("movie.ssa", text)
    assert sts and atoms == [{'start': 1500, 'end': 2250, 'text': 'a, b'}]


def test_microdvd_fps_from_first_line(handler):
    text = u"{1}{1}25.000\n{25}{50}One|{y:i}Two\n{100}{}Three\n{200}{250}Four\n"
    sts, atoms = handler("movie.sub", text)
    assert sts
    assert atoms[0] == {'start': 1000, 'end': 2000, 'text': 'One\nTwo'}
    # no end frame: until the next line, 5s at most
    assert atoms[1] == {'start': 4000, 'end': 8000, 'text': 'Three'}
    assert atoms[2] == {'start': 8000, 'end': 10000, 'text': 'Four'}


def test_microdvd_fps_from_file_name_and_srt_extension(handler):
    sts, atoms = handler("Movie_de_0_1_2_fps25.srt", u"{25}{50}content decides, not the extension\n")
    assert sts and atoms == [{'start': 1000, 'end': 2000, 'text': 'content decides, not the extension'}]


def test_subviewer(handler):
    text = u"[INFORMATION]\n[TITLE]x\n[END INFORMATION]\n\n00:00:01.00,00:00:03.50\nline one[br]line two\n\n00:01:00.00,00:01:02.00\nlast\n"
    sts, atoms = handler("movie.sub", text)
    assert sts
    assert atoms == [{'start': 1000, 'end': 3500, 'text': 'line one\nline two'},
                     {'start': 60000, 'end': 62000, 'text': 'last'}]


def test_tmplayer(handler):
    text = u"00:00:01:Hello|world\n00:00:03=Next\n00:00:20:Long gap\n"
    sts, atoms = handler("movie.txt", text)
    assert sts
    assert atoms == [{'start': 1000, 'end': 3000, 'text': 'Hello\nworld'},
                     {'start': 3000, 'end': 8000, 'text': 'Next'},
                     {'start': 20000, 'end': 25000, 'text': 'Long gap'}]


def test_mpl2_in_txt(handler):
    sts, atoms = handler("movie.txt", u"[10][25]/Hi|there\n")
    assert sts and atoms == [{'start': 1000, 'end': 2500, 'text': 'Hi\nthere'}]


def test_srt_still_works(handler):
    sts, atoms = handler("movie.srt", u"1\n00:00:01,000 --> 00:00:02,000\n<i>Hi</i>\n\n2\n00:00:03,000 --> 00:00:04,000\nBye\n")
    assert sts and atoms == [{'start': 1000, 'end': 2000, 'text': 'Hi'}, {'start': 3000, 'end': 4000, 'text': 'Bye'}]


def test_unknown_or_empty_fails(handler):
    assert handler("movie.txt", u"just some text\nwithout timing\n")[0] is False
    assert handler("movie.srt", u"")[0] is False


def test_open_ends_cut_at_next_cue(handler):
    # two MicroDVD lines without end frame in a row (default 23.976 fps): the first ends when the second starts
    sts, atoms = handler("movie.sub", u"{25}{}One\n{50}{}Two\n")
    assert sts and atoms == [{'start': 1042, 'end': 2085, 'text': 'One'}, {'start': 2085, 'end': 7085, 'text': 'Two'}]
    # MPL2 without end time, same rule
    sts, atoms = handler("movie.txt", u"[10][]One\n[25][30]Two\n")
    assert sts and atoms == [{'start': 1000, 'end': 2500, 'text': 'One'}, {'start': 2500, 'end': 3000, 'text': 'Two'}]


def test_microdvd_known_fps_wins_over_first_line(handler):
    # like the C parser: an fps from the caller / file name beats {1}{1}<fps> in the file
    sts, atoms = handler("Movie_de_0_1_2_fps25.sub", u"{1}{1}50\n{25}{50}Hi\n")
    assert sts and atoms == [{'start': 1000, 'end': 2000, 'text': 'Hi'}]
