# -*- coding: utf-8 -*-
# Offline tests for the exteplayer3 188 gates: what requireDownloaderForDisguisedHls writes as iptv_buffering_reason
# (segments with another name, an image in front of the TS data, TS hidden in the pixels), the segment head check,
# and getMPDLinksWithMeta with ClearKey keys (iptv_drm_keys) for a player with "drmkey". The plugin modules are the
# real ones, the HTTP layer is a fake (test_hls_subtitles).
import sys

from test_hls_subtitles import PKG, _FakeCommon, env  # noqa: F401 - env is the fixture

BASE = "https://cdn.example/live/"
VARIANT = "#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:1\n#EXTINF:4.0,\nseg/0001.png\n#EXTINF:4.0,\nseg/0002.png\n"
VARIANT_AES = ("#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-KEY:METHOD=AES-128,URI=\"https://cdn.example/key\"\n"
               "#EXTINF:4.0,\nseg/0001.js\n")
TS = (b"\x47" + b"\x00" * 187) * 4
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 62
DRM_MPD = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" xmlns:cenc="urn:mpeg:cenc:2013" type="static" mediaPresentationDuration="PT1M"><Period>
  <AdaptationSet contentType="video" mimeType="video/mp4"><ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc" cenc:default_KID="00112233-4455-6677-8899-AABBCCDDEEFF"/>
    <SegmentTemplate media="v/$Number$.m4s" initialization="v/init.mp4" duration="2"/>
    <Representation id="v" bandwidth="1000" width="1280" height="720" codecs="avc1.4d401f"/></AdaptationSet>
  <AdaptationSet contentType="audio" mimeType="audio/mp4"><ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc" cenc:default_KID="00112233-4455-6677-8899-AABBCCDDEEFF"/>
    <SegmentTemplate media="a/$Number$.m4s" initialization="a/init.mp4" duration="2"/>
    <Representation id="a" bandwidth="100" codecs="mp4a.40.2"/></AdaptationSet>
</Period></MPD>"""


def _links(env, playlist, kind, hlsseg):  # noqa: F811 - the fixture of test_hls_subtitles
    sys.modules[PKG + ".libs.curlimpersonate"].getImpersonateBinary = lambda: ""
    env.uph._extePlayer3HlsSeg = lambda: hlsseg
    env.uph._segmentHeadKind = lambda *a: kind
    _FakeCommon.pages = {BASE + "index.m3u8": playlist}
    links = [{"name": "HLS", "url": env.strwithmeta(BASE + "index.m3u8", {"iptv_proto": "m3u8"})}]
    return env.uph.requireDownloaderForDisguisedHls(links)


def test_head_kinds(env):  # noqa: F811
    classify = env.uph._classifySegmentHead
    assert classify(TS) == "plain"
    assert classify(b"\x00\x00\x00\x18ftypiso6" + b"\x00" * 16) == "plain"
    assert classify(b"ID3\x04\x00\x00\x00\x00\x00\x00") == "plain"
    assert classify(b"\xff\xf1\x50\x80\x00\x1f\xfc\x00") == "plain"  # ADTS
    assert classify(PNG + TS) == "image"
    # TS hidden in the pixel data of a large image: no sync bytes in the first 2 KB
    assert classify(PNG + b"\x12" * 2000) == ""
    assert classify(b"\xff\xd8\xff\xe0" + b"\x00" * 100 + TS) == "image"  # JPEG is not ADTS
    assert classify(b"") == ""


def test_reason_for_renamed_segments(env):  # noqa: F811
    meta = _links(env, VARIANT, "plain", 1)[0]["url"].meta
    assert meta["iptv_buffering"] == "required" and meta["iptv_buffering_reason"] == "hlsseg1"


def test_reason_for_image_head(env):  # noqa: F811
    meta = _links(env, VARIANT, "image", 3)[0]["url"].meta
    assert meta["iptv_buffering"] == "required" and meta["iptv_buffering_reason"] == "hlsseg1,hlsseg2"


def test_unknown_head_stays_buffered_without_reason(env):  # noqa: F811
    meta = _links(env, VARIANT, "", 3)[0]["url"].meta
    assert meta["iptv_buffering"] == "required" and "iptv_buffering_reason" not in meta


def test_encrypted_needs_both_bits(env):  # noqa: F811
    meta = _links(env, VARIANT_AES, "", 3)[0]["url"].meta
    assert meta["iptv_buffering_reason"] == "hlsseg1,hlsseg2"


def test_key_rotation_with_method_none_counts_as_encrypted(env):  # noqa: F811
    # a playlist that switches between clear and AES segments is encrypted; the head is not fetched for exteplayer3
    calls = []
    sys.modules[PKG + ".libs.curlimpersonate"].getImpersonateBinary = lambda: ""
    env.uph._extePlayer3HlsSeg = lambda: 3
    env.uph._segmentHeadKind = lambda *a: calls.append(a) or "plain"
    rotated = ("#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-KEY:METHOD=NONE\n#EXTINF:4.0,\nseg/0001.js\n"
               "#EXT-X-KEY:METHOD=AES-128,URI=\"https://cdn.example/key\"\n#EXTINF:4.0,\nseg/0002.js\n")
    _FakeCommon.pages = {BASE + "index.m3u8": rotated}
    links = env.uph.requireDownloaderForDisguisedHls([{"name": "HLS", "url": env.strwithmeta(BASE + "index.m3u8", {"iptv_proto": "m3u8"})}])
    assert links[0]["url"].meta["iptv_buffering_reason"] == "hlsseg1,hlsseg2" and not calls


def test_no_player_check_without_hlsseg(env):  # noqa: F811
    # an older exteplayer3 and no impersonate helper: the segment is not fetched, buffered as before
    calls = []
    sys.modules[PKG + ".libs.curlimpersonate"].getImpersonateBinary = lambda: ""
    env.uph._extePlayer3HlsSeg = lambda: 0
    env.uph._segmentHeadKind = lambda *a: calls.append(a) or "plain"
    _FakeCommon.pages = {BASE + "index.m3u8": VARIANT}
    links = env.uph.requireDownloaderForDisguisedHls([{"name": "HLS", "url": env.strwithmeta(BASE + "index.m3u8", {"iptv_proto": "m3u8"})}])
    assert not calls and links[0]["url"].meta["iptv_buffering"] == "required" and "iptv_buffering_reason" not in links[0]["url"].meta


def _mpdLinks(env, keys, drmkey):  # noqa: F811
    env.uph._extePlayer3Cap = lambda name: drmkey if name == "drmkey" else 0
    _FakeCommon.pages = {"https://drm.example/a.mpd": DRM_MPD}
    meta = {"iptv_drm_keys": keys} if keys else {}
    return env.uph.getMPDLinksWithMeta(env.strwithmeta("https://drm.example/a.mpd", meta), checkExt=False)


def test_clearkey_dash_with_drmkey_player(env):  # noqa: F811
    links = _mpdLinks(env, "00112233445566778899aabbccddeeff:ffeeddccbbaa99887766554433221100", 3)
    assert links
    for lk in links:
        assert lk["url"].meta["iptv_buffering"] == "forbidden"
        assert lk["url"].meta["iptv_drm_keys"].startswith("00112233")


def test_clearkey_dash_without_keys_or_player(env):  # noqa: F811
    assert _mpdLinks(env, "", 3) == []
    assert _mpdLinks(env, "00112233445566778899aabbccddeeff:ffeeddccbbaa99887766554433221100", 0) == []


def test_clearkey_dash_with_dashed_key_kid(env):  # noqa: F811
    # a host may write the KID as a UUID: it is the same KID as the MPD's default_KID
    assert _mpdLinks(env, "00112233-4455-6677-8899-aabbccddeeff:ffeeddccbbaa99887766554433221100", 3)


def test_clearkey_dash_keys_of_other_kids(env):  # noqa: F811
    # OstoraTV 28.11.: the app's keys belong to other KIDs than the MPD's default_KID - DRM message, no dead player
    assert _mpdLinks(env, "dd51609092fff15e68b91debf5d591f9:ab4c789c76686632652eefc19f18c3db", 3) == []
    assert env.hostErrors and "DRM" in env.hostErrors[-1]
