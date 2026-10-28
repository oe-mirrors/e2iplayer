# -*- coding: utf-8 -*-
# Offline test: HLS disguised in its playlist names too (majedkoora's majedcss: master.css -> v/v_stream_06.css with
# .js segments, box log 28.10.). getDirectM3U8Playlist with variantCheck=False keeps iptv_proto on such variants, so
# requireDownloaderForDisguisedHls sees the .js segments and asks for buffering (hlsdl); exteplayer3 alone stopped
# with "Invalid data found". The plugin modules are the real ones, the HTTP layer is a fake (test_hls_subtitles).
import sys

from test_hls_subtitles import PKG, _FakeCommon, env  # noqa: F401 - env is the fixture

BASE = "https://smarter.example/live/ch1/token/"
MASTER = ("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=6096000,RESOLUTION=1920x1080,CODECS=\"avc1.640028,mp4a.40.2\"\n"
          "v/v_stream_06.css\n#EXT-X-STREAM-INF:BANDWIDTH=1096000,RESOLUTION=640x360,CODECS=\"avc1.4d401e,mp4a.40.2\"\n"
          "v/v_stream_02.css\n")
VARIANT = "#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:1\n#EXTINF:3.84,\n../m/abc/v_stream_06/4942808924331535.js\n"


def _links(env, variantCheck):  # noqa: F811 - the fixture of test_hls_subtitles
    sys.modules[PKG + ".libs.curlimpersonate"].getImpersonateBinary = lambda: ""
    _FakeCommon.pages = {BASE + "master.css": MASTER, BASE + "v/v_stream_06.css": VARIANT, BASE + "v/v_stream_02.css": VARIANT}
    url = env.strwithmeta(BASE + "master.css", {"iptv_proto": "m3u8", "iptv_livestream": True, "Referer": "https://player.example/"})
    links = env.uph.getDirectM3U8Playlist(url, checkExt=False, variantCheck=variantCheck, checkContent=True, sortWithMaxBitrate=99999999)
    return env.uph.requireDownloaderForDisguisedHls(links)


def test_css_variants_with_js_segments_are_buffered(env):  # noqa: F811
    links = _links(env, variantCheck=False)
    assert [str(lk["url"]).rsplit("/", 1)[1] for lk in links] == ["v_stream_06.css", "v_stream_02.css"]
    for lk in links:
        meta = lk["url"].meta
        assert meta["iptv_proto"] == "m3u8" and meta["iptv_buffering"] == "required"
        assert meta["Referer"] == "https://player.example/"


def test_with_variant_check_the_disguise_went_unseen(env):  # noqa: F811
    # the old call: the .css variants lost iptv_proto, the check returned at once - no buffering
    links = _links(env, variantCheck=True)
    assert links and all(not lk["url"].meta.get("iptv_buffering") for lk in links)
