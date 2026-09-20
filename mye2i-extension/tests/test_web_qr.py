import os
import struct
import sys
import types

import pytest

# web_qr.py imports one helper from the plugin package, which only exists on the receiver
for _name in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.p2p3"):
    sys.modules.setdefault(_name, types.ModuleType(_name))
_helper = types.ModuleType("Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings")
_helper.ensure_binary = lambda value: value if isinstance(value, bytes) else value.encode("utf-8")
sys.modules.setdefault("Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings", _helper)

sys.path.insert(0, os.path.join("IPTVPlayer", "libs"))

import web_qr  # noqa: E402

WIKI = "https://github.com/oe-mirrors/e2iplayer/wiki/Solve-Cloudflare-hCaptcha-reCAPTCHA-with-MyE2i"
SESSION = "http://192.168.178.22:9001/?t=0123456789abcdef"


@pytest.mark.parametrize("length,size", [(1, 29), (53, 29), (54, 33), (78, 33), (79, 37), (106, 37)])
def test_smallest_version_that_fits_is_used(length, size):
    assert len(web_qr._matrix("a" * length)) == size


def test_text_that_is_too_long_is_refused():
    with pytest.raises(ValueError):
        web_qr._matrix("a" * 107)


def test_wiki_address_fits():
    assert len(web_qr._matrix(WIKI)) == 37


def test_png_is_written(tmp_path):
    path = str(tmp_path / "qr.png")
    web_qr.make_qr_png(WIKI, path, scale=4, border=2)
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width == height == (37 + 2 * 2) * 4


def test_codes_decode_with_a_real_reader(tmp_path):
    zxingcpp = pytest.importorskip("zxingcpp")
    image_module = pytest.importorskip("PIL.Image")
    for text in (SESSION, "x" * 60, WIKI, "y" * 106):
        path = str(tmp_path / "qr.png")
        web_qr.make_qr_png(text, path, scale=6, border=4)
        found = zxingcpp.read_barcodes(image_module.open(path))
        assert [item.text for item in found] == [text]
