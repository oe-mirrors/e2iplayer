# Offline tests for IPTVGraphicSubtitlesHandler (IPTVPlayer/tools/iptvsubtitles.py): the image subtitles
# exteplayer3 writes with -G as PNG files and announces as {"s_a":{..,"r":[{x,y,w,h,f}]}}.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod


@pytest.fixture
def mod(tmp_path):
    saved = dict(sys.modules)
    for name in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.tools",
                 "Plugins.Extensions.IPTVPlayer.libs", "Plugins.Extensions.IPTVPlayer.p2p3"):
        _stub(name)
    _stub("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
          GetSubtitlesDir=lambda f="": str(tmp_path / f), byteify=lambda x, *a, **k: x,
          IsSubtitlesParserExtensionCanBeUsed=lambda: False)
    _stub("Plugins.Extensions.IPTVPlayer.libs.pCommon", CParsingHelper=object)
    _stub("Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings", ensure_str=lambda s, *a, **k: s)
    spec = importlib.util.spec_from_file_location("iptvsubtitles_graphic_under_test", os.path.join(ROOT, "tools", "iptvsubtitles.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _atom(handler, tmp_path, start, end, names):
    rects = []
    for i, name in enumerate(names):
        (tmp_path / name).write_bytes(b"png")
        rects.append({'x': 10 * i, 'y': 600, 'w': 300, 'h': 40, 'f': name})
    handler.addAtom(start, end, rects)
    return rects


def test_open_end_atom_lasts_until_the_next_one(mod, tmp_path):
    h = mod.IPTVGraphicSubtitlesHandler(str(tmp_path))
    first = _atom(h, tmp_path, 1000, None, ["1_1000_0.png"])
    _atom(h, tmp_path, 3000, None, [])  # PGS clear
    assert h.getRects(500) == (-1, [])
    assert h.getRects(1000) == (1000, first)
    assert h.getRects(2999, 1000) == (1000, None)  # unchanged
    assert h.getRects(3000, 1000) == (3000, [])


def test_atom_with_end_time(mod, tmp_path):
    h = mod.IPTVGraphicSubtitlesHandler(str(tmp_path))
    rects = _atom(h, tmp_path, 1000, 2000, ["1_1000_0.png", "1_1000_1.png"])
    assert h.getRects(1500) == (1000, rects)
    assert h.getRects(2000, 1000) == (-1, [])


def test_atoms_arriving_out_of_order_are_sorted(mod, tmp_path):
    h = mod.IPTVGraphicSubtitlesHandler(str(tmp_path))
    late = _atom(h, tmp_path, 5000, None, ["1_5000_0.png"])
    early = _atom(h, tmp_path, 1000, None, ["1_1000_0.png"])
    assert h.getRects(1200)[1] == early
    assert h.getRects(5200)[1] == late


def test_shown_files_are_deleted_and_flush_removes_the_rest(mod, tmp_path):
    h = mod.IPTVGraphicSubtitlesHandler(str(tmp_path))
    for start in (1000, 2000, 3000, 4000):
        _atom(h, tmp_path, start, None, ["1_%d_0.png" % start])
    h.getRects(4000)
    # the shown atom and the one before it stay
    assert sorted(os.listdir(str(tmp_path))) == ["1_3000_0.png", "1_4000_0.png"]
    assert h.getRects(3500)[0] == 3000
    h.flushSubtitles()
    assert os.listdir(str(tmp_path)) == []
    assert h.getRects(4000) == (-1, [])


def test_path_stays_in_the_directory(mod, tmp_path):
    h = mod.IPTVGraphicSubtitlesHandler(str(tmp_path))
    assert h.getPath({'f': "../../etc/x.png"}) == os.path.join(str(tmp_path), "x.png")
