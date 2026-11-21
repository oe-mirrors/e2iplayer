# Offline tests for fixMkvH264Header() in IPTVPlayer/iptvdm/downloaderhelpers.py: an MKV whose H.264 header
# (CodecPrivate) carries each SPS / PPS twice gets each of them once, in place - the file keeps its size, the freed
# bytes become an EBML Void element and the CRC-32 of the Tracks element is right again.
import importlib.util
import os
import struct
import sys
import types
import zlib

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"

# the avcC of a BongaCams room (box test 21.11.2026): SPS + SPS + PPS + PPS, High profile extension at the end
SPS = bytes.fromhex("67640028ac191a80780225e58078442350")
PPS = bytes.fromhex("68ce3c80")
EXT = bytes.fromhex("fdf8f800")


def _avcc(spsList, ppsList, ext=EXT):
    out = bytearray(b"\x01\x64\x00\x28\xff")
    out.append(0xE0 | len(spsList))
    for unit in spsList:
        out += struct.pack(">H", len(unit)) + unit
    out.append(len(ppsList))
    for unit in ppsList:
        out += struct.pack(">H", len(unit)) + unit
    return bytes(out + ext)


def _size(value, length=1):
    return (value | (1 << (7 * length))).to_bytes(length, "big")


def _el(elementId, data, sizeLen=1):
    return elementId + _size(len(data), sizeLen) + data


def _mkv(codecPrivate, codecId=b"V_MPEG4/ISO/AVC", crc=True, tracksSizeLen=2):
    header = _el(b"\x1a\x45\xdf\xa3", _el(b"\x42\x82", b"matroska"))
    entry = _el(b"\xd7", b"\x01") + _el(b"\x86", codecId) + _el(b"\x63\xa2", codecPrivate)
    tracksBody = _el(b"\xae", entry)
    if crc:
        tracksBody = b"\xbf\x84" + struct.pack("<I", zlib.crc32(tracksBody) & 0xFFFFFFFF) + tracksBody
    tracks = _el(b"\x16\x54\xae\x6b", tracksBody, tracksSizeLen)
    info = _el(b"\x15\x49\xa9\x66", _el(b"\x2a\xd7\xb1", b"\x0f\x42\x40"))
    cluster = _el(b"\x1f\x43\xb6\x75", _el(b"\xe7", b"\x00") + b"\xa3\x85\x81\x00\x00\x80\x00")
    # a live recording: Segment of unknown size
    return header + b"\x18\x53\x80\x67\x01\xff\xff\xff\xff\xff\xff\xff" + info + tracks + cluster


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


@pytest.fixture
def dh(tmp_path):
    saved = dict(sys.modules)
    for pkg in ("Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".libs", PKG + ".iptvdm"):
        _stubModule(pkg)
    _stubModule(PKG + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
                eConnectCallback=lambda *a: a, GetNice=lambda *a: 0, E2PrioFix=lambda cmd, *a: cmd,
                GetTmpDir=lambda name="": str(tmp_path / name), GetDefaultLang=lambda *a: "en")
    _stubModule(PKG + ".libs.pCommon", common=object)
    _stubModule("Tools")
    _stubModule("Tools.BoundFunction", boundFunction=lambda f, *a: f)
    _stubModule("Components")
    _stubModule("Components.config", config=types.SimpleNamespace())
    _stubModule("enigma", eConsoleAppContainer=object)
    spec = importlib.util.spec_from_file_location(PKG + ".iptvdm.downloaderhelpers", os.path.join(ROOT, "iptvdm", "downloaderhelpers.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _tracks(data):
    # (CRC element data, rest of the Tracks data, CodecPrivate data, Void present)
    pos = data.index(b"\x16\x54\xae\x6b") + 4
    size = int.from_bytes(data[pos:pos + 2], "big") & 0x3FFF
    body = data[pos + 2:pos + 2 + size]
    crc = None
    if body[:2] == b"\xbf\x84":
        crc, body = body[2:6], body[6:]
    private = body.index(b"\x63\xa2")
    length = body[private + 2] & 0x7F
    return crc, body, body[private + 3:private + 3 + length], b"\xec" in body[private + 3 + length:]


def test_duplicates_removed_in_place(dh, tmp_path):
    path = tmp_path / "room.mkv"
    original = _mkv(_avcc([SPS, SPS], [PPS, PPS]))
    path.write_bytes(original)
    assert dh.fixMkvH264Header(str(path)) is True
    fixed = path.read_bytes()
    assert len(fixed) == len(original)
    crc, body, private, void = _tracks(fixed)
    assert private == _avcc([SPS], [PPS])
    assert void
    assert struct.unpack("<I", crc)[0] == zlib.crc32(body) & 0xFFFFFFFF
    # everything after the Tracks element is unchanged (the clusters, the offsets of the Cues ...)
    end = original.index(b"\x1f\x43\xb6\x75")
    assert fixed[end:] == original[end:]
    # nothing left to do the second time
    assert dh.fixMkvH264Header(str(path)) is False
    assert path.read_bytes() == fixed


def test_without_crc_element(dh, tmp_path):
    path = tmp_path / "room.mkv"
    path.write_bytes(_mkv(_avcc([SPS, SPS], [PPS, PPS]), crc=False))
    assert dh.fixMkvH264Header(str(path)) is True
    crc, _body, private, _void = _tracks(path.read_bytes())
    assert crc is None
    assert private == _avcc([SPS], [PPS])


@pytest.mark.parametrize("avcc", [_avcc([SPS], [PPS]), _avcc([SPS, SPS[:-1] + b"\x01"], [PPS])])
def test_untouched_without_duplicates(dh, tmp_path, avcc):
    # one SPS / PPS each, or two different SPS: nothing to remove
    path = tmp_path / "film.mkv"
    original = _mkv(avcc)
    path.write_bytes(original)
    assert dh.fixMkvH264Header(str(path)) is False
    assert path.read_bytes() == original


def test_other_codec_and_other_container_untouched(dh, tmp_path):
    hevc = tmp_path / "film.mkv"
    original = _mkv(_avcc([SPS, SPS], [PPS, PPS]), codecId=b"V_MPEGH/ISO/HEVC")
    hevc.write_bytes(original)
    assert dh.fixMkvH264Header(str(hevc)) is False
    assert hevc.read_bytes() == original
    ts = tmp_path / "room.ts"
    ts.write_bytes(original)
    assert dh.fixMkvH264Header(str(ts)) is False
    assert dh.fixMkvH264Header(str(tmp_path / "missing.mkv")) is False


def test_when_done_waits_for_the_writer(dh, tmp_path):
    # a stopped live recording: ffmpeg rewrites the header after the stop - the fix comes once the file is quiet
    path = tmp_path / "room.mkv"
    path.write_bytes(_mkv(_avcc([SPS], [PPS])))
    worker = dh.fixMkvH264HeaderWhenDone(str(path), quietSecs=0.6, maxSecs=10)
    # the writer's last word: the header with the duplicates again
    path.write_bytes(_mkv(_avcc([SPS, SPS], [PPS, PPS])))
    worker.join(10)
    assert not worker.is_alive()
    assert _tracks(path.read_bytes())[2] == _avcc([SPS], [PPS])


def test_broken_file_does_not_raise(dh, tmp_path):
    path = tmp_path / "broken.mkv"
    path.write_bytes(b"\x1a\x45\xdf\xa3\x00")
    assert dh.fixMkvH264Header(str(path)) is False
