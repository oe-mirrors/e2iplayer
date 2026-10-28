# -*- coding: utf-8 -*-
# Offline tests for IPTVPlayer/libs/dashmpd.py: reading an MPD (period, representations, labels, subtitle files,
# DRM), the "Select link" items of getMPDLinksWithMeta, the filtered MPD with the ffmpeg dashdec workarounds and
# the local MPD server. strwithmeta is the real one, printDBG / printExc are stubbed.
import importlib.util
import os
import re
import sys
import types
import urllib.request

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"

VOD = """<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" xmlns:cenc="urn:mpeg:cenc:2013" type="static" mediaPresentationDuration="PT10M" minBufferTime="PT2S" profiles="urn:mpeg:dash:profile:isoff-live:2011">
  <Period id="ad" duration="PT30S">
    <AdaptationSet contentType="video" mimeType="video/mp4"><SegmentTemplate media="ad/$Number$.m4s" duration="2"/>
      <Representation id="ad1" bandwidth="500000" width="640" height="360" codecs="avc1.4d401e"/>
    </AdaptationSet>
  </Period>
  <Period id="main" duration="PT9M30S">
    <BaseURL>content/</BaseURL>
    <AdaptationSet id="1" contentType="video" mimeType="video/mp4" frameRate="25" codecs="avc1.640028">
      <SegmentTemplate media="$RepresentationID$/$Number$.m4s" initialization="$RepresentationID$/init.mp4" duration="2"/>
      <Representation id="v1080" bandwidth="5000000" width="1920" height="1080"/>
      <Representation id="v720" bandwidth="3000000" width="1280" height="720"/>
    </AdaptationSet>
    <AdaptationSet id="2" contentType="video" mimeType="video/mp4" codecs="hvc1.2.4.L153">
      <SupplementalProperty schemeIdUri="urn:mpeg:mpegB:cicp:TransferCharacteristics" value="16"/>
      <Representation id="h2160" bandwidth="15000000" width="3840" height="2160" frameRate="50"/>
    </AdaptationSet>
    <AdaptationSet id="3" contentType="video" mimeType="video/mp4" codecs="av01.0.08M.08">
      <Representation id="av1" bandwidth="2000000" width="1920" height="1080"/>
    </AdaptationSet>
    <AdaptationSet id="4" contentType="video" mimeType="video/mp4">
      <EssentialProperty schemeIdUri="http://dashif.org/guidelines/trickmode" value="1"/>
      <Representation id="trick" bandwidth="100000" width="320" height="180" codecs="avc1.42c00d"/>
    </AdaptationSet>
    <AdaptationSet id="5" contentType="image" mimeType="image/jpeg">
      <Representation id="thumbs" bandwidth="10000" width="1024" height="576"/>
    </AdaptationSet>
    <AdaptationSet id="6" contentType="video" mimeType="video/mp4" codecs="avc1.640028">
      <ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc" cenc:default_KID="1234"/>
      <Representation id="drm1080" bandwidth="5000000" width="1920" height="1080"/>
    </AdaptationSet>
    <AdaptationSet id="7" contentType="audio" mimeType="audio/mp4" lang="de" codecs="mp4a.40.2">
      <Role schemeIdUri="urn:mpeg:dash:role:2011" value="main"/>
      <AudioChannelConfiguration schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011" value="2"/>
      <Representation id="de128" bandwidth="128000"/>
      <Representation id="de64" bandwidth="64000"/>
    </AdaptationSet>
    <AdaptationSet id="8" contentType="audio" mimeType="audio/mp4" lang="de" codecs="ec-3">
      <Role schemeIdUri="urn:mpeg:dash:role:2011" value="alternate"/>
      <Accessibility schemeIdUri="urn:tva:metadata:cs:AudioPurposeCS:2007" value="1"/>
      <AudioChannelConfiguration schemeIdUri="tag:dolby.com,2014:dash:audio_channel_configuration:2011" value="F801"/>
      <Label>Audiodeskription</Label>
      <Representation id="dead" bandwidth="256000"/>
    </AdaptationSet>
    <AdaptationSet id="9" contentType="text" mimeType="text/vtt" lang="de">
      <Role schemeIdUri="urn:mpeg:dash:role:2011" value="subtitle"/>
      <Representation id="subde" bandwidth="1000"><BaseURL>subs/de.vtt</BaseURL></Representation>
    </AdaptationSet>
    <AdaptationSet id="10" contentType="text" mimeType="application/mp4" codecs="stpp" lang="en">
      <SegmentTemplate media="sub/$Number$.m4s" duration="2"/>
      <Representation id="suben" bandwidth="1000"/>
    </AdaptationSet>
  </Period>
</MPD>
"""

LIVE = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" xmlns:scte35="http://www.scte.org/schemas/35/2016" type="dynamic"
     availabilityStartTime="1970-01-01T00:00:00Z" publishTime="2025-05-20T14:42:11Z" maxSegmentDuration="PT4S" minimumUpdatePeriod="PT2S">
  <BaseURL>https://cdn.example/live/</BaseURL>
  <BaseURL>https://backup.example/live/</BaseURL>
  <Period id="p1" start="PT0S">
    <AdaptationSet contentType="video" mimeType="video/mp4" codecs="avc3.640028">
      <SegmentTemplate timescale="200" duration="768" media="$RepresentationID$/$Number%06d$.m4s" initialization="$RepresentationID$/IS.mp4"/>
      <Representation id="1080p" bandwidth="5000000" width="1920" height="1080"/>
      <Representation id="540p" bandwidth="1500000" width="960" height="540"/>
    </AdaptationSet>
    <AdaptationSet contentType="audio" mimeType="audio/mp4" lang="en" codecs="mp4a.40.2">
      <SegmentTemplate timescale="48000" duration="184320" media="$RepresentationID$/$Number%06d$.m4s" initialization="$RepresentationID$/IS.mp4"/>
      <Representation id="aac" bandwidth="128000"/>
    </AdaptationSet>
  </Period>
  <Period id="p2" start="PT1000S">
    <EventStream schemeIdUri="urn:scte:scte35:2014:xml+bin" timescale="1"><Event id="1"><scte35:Signal/></Event></EventStream>
    <AdaptationSet contentType="video" mimeType="video/mp4" codecs="avc1.640028">
      <SegmentTemplate timescale="1" duration="2" startNumber="500" presentationTimeOffset="1000" media="$RepresentationID$/$Number$.m4s"/>
      <Representation id="V1" bandwidth="3000000" width="1280" height="720"/>
      <Representation id="V2" bandwidth="800000" width="640" height="360"/>
    </AdaptationSet>
  </Period>
</MPD>
"""

DRM_ONLY = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT1M"><Period>
  <AdaptationSet contentType="video" mimeType="video/mp4"><ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"/>
    <Representation id="v" bandwidth="1" width="1280" height="720" codecs="avc1.4d401f"/></AdaptationSet>
  <AdaptationSet contentType="audio" mimeType="audio/mp4"><ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"/>
    <Representation id="a" bandwidth="1" codecs="mp4a.40.2"/></AdaptationSet>
</Period></MPD>"""


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dm():
    saved = dict(sys.modules)
    for pkg in ("Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".libs"):
        _stubModule(pkg)
    _stubModule(PKG + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None)
    _load(PKG + ".tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    module = _load(PKG + ".libs.dashmpd", os.path.join(ROOT, "libs", "dashmpd.py"))
    module.strwithmeta = sys.modules[PKG + ".tools.iptvtypes"].strwithmeta
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _linkHeight(name):
    # tools/linkpicker.py reads the height of a link name ("res: 1920x1080") for "Default video quality"
    spec = importlib.util.spec_from_file_location("linkpicker_for_dash", os.path.join(ROOT, "tools", "linkpicker.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.linkHeight(name), module.isTooWideH264(name)


def test_durations_and_dates(dm):
    assert dm.parseDuration("PT1H2M3.5S") == 3723.5
    assert dm.parseDuration("P1DT1S") == 86401
    assert dm.parseDuration("bad", 7) == 7
    assert dm.parseDateTime("1970-01-01T00:00:00Z") == 0
    assert dm.parseDateTime("2026-10-25T18:00:00+01:00") == dm.parseDateTime("2026-10-25T17:00:00Z")
    assert dm.parseDateTime("2026-10-25T17:00:00.5Z") == dm.parseDateTime("2026-10-25T17:00:00Z") + 0.5


def test_parse_vod(dm):
    mpd = dm.parseMpd(VOD, "https://vod.example/film/manifest.mpd")
    assert mpd["period"] == 1  # the longest period, not the ad in front of it
    assert not mpd["dynamic"]
    videos = dict((v["id"], v) for v in mpd["video"])
    # trick-mode, thumbnails and the encrypted set are left out
    assert sorted(videos) == ["av1", "h2160", "v1080", "v720"]
    assert videos["v1080"]["codec"] == "H.264" and videos["v1080"]["frame_rate"] == 25
    assert videos["h2160"]["codec"] == "HEVC" and videos["h2160"]["hdr"] == "HDR" and videos["h2160"]["frame_rate"] == 50
    assert videos["av1"]["codec"] == "AV1"
    audios = dict((a["id"], a) for a in mpd["audio"])
    assert audios["de128"]["channels"] == "" and audios["de128"]["codec"] == "AAC"
    assert audios["dead"]["channels"] == "5.1" and audios["dead"]["tags"] == ["AD"] and audios["dead"]["label"] == "Audiodeskription"
    # the subtitle file and the segmented stpp track (joined to WebVTT by the local server)
    assert [(t.get("url"), t.get("segmented"), t["format"], t["lang"]) for t in mpd["text"]] == [
        ("https://vod.example/film/content/subs/de.vtt", None, "vtt", "de"), (None, "stpp", "vtt", "en")]


def test_links(dm):
    links = dm.buildLinks(dm.parseMpd(VOD, "https://vod.example/film/manifest.mpd"), dm.strwithmeta("https://vod.example/film/manifest.mpd", {"Referer": "https://site/"}))
    # 4 videos x 2 audio tracks (one entry per track: its best bitrate), the main audio first
    assert len(links) == 8
    assert links[0]["name"] == "[de AAC] bitrate: 15128000 res: 3840x2160 HEVC HDR 50fps"
    assert links[1]["name"].startswith("[de AAC] bitrate: 5128000 res: 1920x1080 H.264 25fps")
    assert links[3]["name"].endswith("AV1")  # undecodable on receivers: last of its audio track
    assert links[3]["undecodable"] and not links[0]["undecodable"]
    assert links[4]["name"].startswith("[Audiodeskription de E-AC-3 5.1 AD] ")
    meta = links[1]["url"].meta
    assert meta["Referer"] == "https://site/" and meta["iptv_proto"] == "mpd" and meta["iptv_livestream"] is False
    assert meta["iptv_dash_sel"] == "v=v1080|vi=0.0|vh=1080|a=de128|ai=6.0"
    # for the player info bar when exteplayer3 reports nonsense (200 fps for a 1/200 time base)
    assert meta["iptv_frame_rate"] == 25 and "iptv_frame_rate" not in links[3]["url"].meta
    subs = meta["external_sub_tracks"]
    assert subs[0] == {"title": "de", "url": "https://vod.example/film/content/subs/de.vtt", "lang": "de", "format": "vtt"}
    assert (subs[1]["lang"], subs[1]["format"]) == ("en", "vtt") and re.match(r"^http://127\.0\.0\.1:\d+/dash/[0-9a-f]{20}\.vtt$", subs[1]["url"])
    assert (links[1]["width"], links[1]["height"], links[1]["bandwidth"], links[1]["codecs"]) == (1920, 1080, 5128000, "AAC,H.264")
    # "Default video quality" / "Select link automatically" read the height and H.264 from the name
    assert _linkHeight(links[1]["name"]) == (1080, False)
    assert _linkHeight(links[0]["name"]) == (2160, False)


def test_audio_only_and_drm(dm):
    audioOnly = re.sub(r'<AdaptationSet id="[1-6]".*?</AdaptationSet>', '', VOD, flags=re.S)
    links = dm.buildLinks(dm.parseMpd(audioOnly, "https://vod.example/a.mpd"), "https://vod.example/a.mpd")
    assert [l["name"] for l in links] == ["[Audiodeskription de E-AC-3 5.1 AD] bitrate: 256000 audio only",
                                         "[de AAC] bitrate: 128000 audio only", "[de AAC] bitrate: 64000 audio only"]
    assert _linkHeight(links[0]["name"]) == (0, False)
    # a track without language and label: its codec only, no "audio" placeholder
    noLang = VOD.replace(' lang="de" codecs="mp4a.40.2"', ' codecs="mp4a.40.5"')
    links = dm.buildLinks(dm.parseMpd(noLang, "https://vod.example/a.mpd"), "https://vod.example/a.mpd")
    assert links[1]["name"].startswith("[HE-AAC] bitrate: ")
    # "und" (undetermined, TV Trwam) is no language either
    undLang = VOD.replace(' lang="de" codecs="mp4a.40.2"', ' lang="und" codecs="mp4a.40.2"')
    links = dm.buildLinks(dm.parseMpd(undLang, "https://vod.example/a.mpd"), "https://vod.example/a.mpd")
    assert links[1]["name"].startswith("[AAC] bitrate: ") and links[1]["lang"] == ""
    # ... also as its Label (the real TV Trwam MPD: lang="und" + <Label>und</Label>)
    undLabel = undLang.replace('<Role schemeIdUri="urn:mpeg:dash:role:2011" value="main"/>', '<Role schemeIdUri="urn:mpeg:dash:role:2011" value="main"/><Label>und</Label>')
    links = dm.buildLinks(dm.parseMpd(undLabel, "https://vod.example/a.mpd"), "https://vod.example/a.mpd")
    assert links[1]["name"].startswith("[AAC] bitrate: ")
    mpd = dm.parseMpd(DRM_ONLY, "https://drm.example/a.mpd")
    assert mpd["drm_only"] and not mpd["video"] and not mpd["audio"]


def test_live_period_choice(dm):
    # the period running now: p2 starts 1000 s after availabilityStartTime
    assert dm.parseMpd(LIVE, "https://cdn.example/live/x.mpd", now=500)["period"] == 0
    mpd = dm.parseMpd(LIVE, "https://cdn.example/live/x.mpd", now=2000)
    assert mpd["period"] == 1 and mpd["dynamic"]
    links = dm.buildLinks(dm.parseMpd(LIVE, "https://cdn.example/live/x.mpd", now=500), "https://cdn.example/live/x.mpd")
    assert links[0]["url"].meta["iptv_livestream"] is True and links[0]["livestream"] is True


def test_filter_vod(dm):
    out = dm.filterMpd(VOD, "https://vod.example/film/manifest.mpd?token=1", "v=v720|vi=0.1|vh=720|a=dead|ai=7.0")
    assert out.startswith('<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"') and "ns0:" not in out
    assert 'xmlns:cenc="urn:mpeg:cenc:2013"' not in out or "cenc:" in out  # an unused prefix may stay declared
    reps = re.findall(r'<Representation id="([^"]+)"', out)
    assert reps == ["v720", "dead"]
    assert out.count("<Period") == 1 and 'id="main"' in out
    # a static MPD keeps one period: that is the whole programme now
    assert 'start="PT0S"' in out and 'duration="PT570.000S"' in out and 'mediaPresentationDuration="PT570.000S"' in out
    # the directory of the MPD (the query of the MPD url is not inherited), the period BaseURL stays relative
    assert "<BaseURL>https://vod.example/film/</BaseURL>" in out and "<BaseURL>content/</BaseURL>" in out


def test_filter_live_workarounds(dm):
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=500)
    # epoch availabilityStartTime: dashdec would count from publishTime
    assert "publishTime" not in out
    # some distance to the live edge (3 x maxSegmentDuration, at least 10 s)
    assert 'suggestedPresentationDelay="PT12S"' in out
    # one absolute BaseURL (the first of the MPD)
    assert out.count("<BaseURL>") == 1 and "<BaseURL>https://cdn.example/live/</BaseURL>" in out
    assert re.findall(r'<Representation id="([^"]+)"', out) == ["540p", "aac"]
    # period 2 later: other ids -> the video closest to the chosen height (a tie: the better one); period start
    # and presentationTimeOffset moved into startNumber, the SCTE-35 events dropped
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=2000)
    assert re.findall(r'<Representation id="([^"]+)"', out) == ["V1"]
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=288p|vi=0.1|vh=288|a=aac|ai=1.0", now=2000)
    assert re.findall(r'<Representation id="([^"]+)"', out) == ["V2"]
    assert 'startNumber="0"' in out and "presentationTimeOffset" not in out and 'start="PT0S"' in out
    assert "EventStream" not in out and "ns0:" not in out


def test_default_start_number(dm):
    # $Number$ without startNumber starts at 1; dashdec counted from 0 (BBC test card: 000000.m4s 404 every start)
    out = dm.filterMpd(VOD, "https://vod.example/a.mpd", "v=v720|vi=0.1|vh=720|a=de128|ai=6.0")
    assert re.findall(r'<SegmentTemplate[^>]*startNumber="1"', out)
    # one already given (also on a higher level) stays as it is
    given = VOD.replace('<SegmentTemplate media="$RepresentationID$/$Number$.m4s"', '<SegmentTemplate startNumber="7" media="$RepresentationID$/$Number$.m4s"')
    out = dm.filterMpd(given, "https://vod.example/a.mpd", "v=v720|vi=0.1|vh=720|a=de128|ai=6.0")
    assert 'startNumber="7"' in out and 'startNumber="1"' not in out


def test_live_start_behind_the_edge_and_clock(dm):
    # dashdec reads up to the segment still being written: the start moves one segment (4 s) + 1 s later
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=500)
    assert 'availabilityStartTime="1970-01-01T00:00:05Z"' in out
    # a receiver clock 12 s ahead of the server (clockOffset -12): 12 s more
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=512, clockOffset=-12)
    assert 'availabilityStartTime="1970-01-01T00:00:17Z"' in out
    # the period choice goes by the server time: receiver 1010 s, server 990 s -> still period 1
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=1010, clockOffset=-20)
    assert re.findall(r'<Representation id="([^"]+)"', out) == ["540p", "aac"]
    # buffering: 30 s more behind the edge ...
    out = dm.filterMpd(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=500, startDelay=30)
    assert 'availabilityStartTime="1970-01-01T00:00:35Z"' in out
    # ... but within what the server keeps (timeShiftBufferDepth 20 s, 4 s segments: 20 - 3 x 4 - 1 = 7 s)
    out = dm.filterMpd(LIVE.replace('minimumUpdatePeriod="PT2S"', 'minimumUpdatePeriod="PT2S" timeShiftBufferDepth="PT20S"'),
                       "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0", now=500, startDelay=30)
    assert 'availabilityStartTime="1970-01-01T00:00:12Z"' in out
    # a static MPD keeps its times
    assert "availabilityStartTime" not in dm.filterMpd(VOD, "https://vod.example/a.mpd", "v=v720|vi=0.1|vh=720|a=de128|ai=6.0")
    # the Date header of the MPD response: a difference under 2 s counts as none
    import email.utils
    import time
    assert dm._clockOffset(email.utils.formatdate(time.time() - 30, usegmt=True)) == pytest.approx(-30, abs=1.5)
    assert dm._clockOffset(email.utils.formatdate(time.time(), usegmt=True)) == 0
    assert dm._clockOffset(None) == 0 and dm._clockOffset("garbage") == 0


def test_channel_configurations(dm):
    import xml.etree.ElementTree as ET

    def ch(scheme, value):
        return dm._channels([ET.Element("AudioChannelConfiguration", schemeIdUri=scheme, value=value)])
    assert ch("urn:mpeg:dash:23003:3:audio_channel_configuration:2011", "6") == "5.1"
    assert ch("urn:mpeg:mpegB:cicp:ChannelConfiguration", "12") == "7.1"
    assert ch("urn:mpeg:mpegB:cicp:ChannelConfiguration", "1") == "mono"
    assert ch("tag:dolby.com,2014:dash:audio_channel_configuration:2011", "F801") == "5.1"
    assert ch("urn:mpeg:dash:23003:3:audio_channel_configuration:2011", "2") == ""


def test_local_server_serves_the_filtered_mpd(dm):
    url = "https://vod.example/film/manifest.mpd"
    # a static MPD the link list read already: served from memory, no second request
    dm.rememberManifest(url, url, VOD, False)
    local = dm.localManifestUrl(dm.strwithmeta(url, {"iptv_dash_sel": "v=v1080|vi=0.0|vh=1080|a=de128|ai=6.0", "User-Agent": "UA"}))
    assert re.match(r"^http://127\.0\.0\.1:\d+/dash/[0-9a-f]{20}\.mpd$", local)
    resp = urllib.request.urlopen(local, timeout=5)
    body = resp.read().decode("utf-8")
    assert resp.headers["Content-Type"] == "application/dash+xml"
    assert re.findall(r'<Representation id="([^"]+)"', body) == ["v1080", "de128"]
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(local.rsplit("/", 1)[0] + "/unknown.mpd", timeout=5)
    # no selection or no http url: the caller plays the original
    assert dm.localManifestUrl(dm.strwithmeta(url, {})) is None
    assert dm.localManifestUrl(dm.strwithmeta("/hdd/movie/a.mpd", {"iptv_dash_sel": "v=1"})) is None


def test_segment_math(dm):
    # rounded up, a float rest is no extra segment
    assert dm._ceilDiv(9, 2) == 5 and dm._ceilDiv(8.0000000001, 2) == 4 and dm._ceilDiv(8, 2) == 4
    import xml.etree.ElementTree as ET
    rep = ET.Element("Representation", id="a1", bandwidth="128000")
    assert dm._fillTemplate("$RepresentationID$/$Bandwidth%08d$/$Number%05d$-$Time$.m4s$$", rep, 7, 900) == "a1/00128000/00007-900.m4s$"
    plan = dm.downloadPlan(VOD, "https://vod.example/film/manifest.mpd", "v=v720|vi=0.1|vh=720|a=de128|ai=6.0")
    video, audio = plan["tracks"]
    # 570 s period, 2 s segments, numbers from 1
    assert len(video["segments"]) == 285 and video["counted"] and video["segments"][0][0].endswith("/content/v720/1.m4s")
    assert (video["lang"], audio["type"], audio["lang"]) == ("", "audio", "de")
    with pytest.raises(ValueError):
        dm.downloadPlan(LIVE, "https://cdn.example/live/x.mpd", "v=540p|vi=0.1|vh=540|a=aac|ai=1.0")


def test_decoded_text_with_its_own_encoding(dm):
    # a text already decoded keeps "Français" although the declaration says ISO-8859-1; a BOM in front is no error
    text = u'﻿<?xml version="1.0" encoding="ISO-8859-1"?>' + VOD.split("?>", 1)[1].replace('lang="de" codecs="ec-3"', 'lang="fr" codecs="ec-3"').replace(
        "<Label>Audiodeskription</Label>", u"<Label>Fran\xe7ais</Label>")
    audios = dict((a["id"], a) for a in dm.parseMpd(text, "https://vod.example/a.mpd")["audio"])
    assert audios["dead"]["label"] == u"Fran\xe7ais"


def test_closest_video_prefers_a_decodable_codec(dm):
    import xml.etree.ElementTree as ET
    vp9 = ET.Element("AdaptationSet", codecs="vp09.00.40.08")
    avc = ET.Element("AdaptationSet", codecs="avc1.640028")
    sets = [(vp9, "video", [ET.Element("Representation", id="p1", height="1080", bandwidth="9")]),
            (avc, "video", [ET.Element("Representation", id="p2", height="1080", bandwidth="5"),
                            ET.Element("Representation", id="p3", height="720", bandwidth="3")])]
    # another period: other ids, the position points to a 720p one -> the 1080p H.264
    assert dm._findRep(sets, "video", "gone", "1.1", 1080)[1].get("id") == "p2"
    # the position still has the chosen height
    assert dm._findRep(sets, "video", "gone", "1.1", 720)[1].get("id") == "p3"
    assert dm._findRep(sets, "video", "gone", "x", 0) == (vp9, sets[0][2][0])


class _Resp(object):
    def __init__(self, status, data):
        self.status, self.data = status, data

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self.data)
        block, self.data = self.data[:size], self.data[size:]
        return block


def test_read_range(dm):
    assert dm.readRange(_Resp(206, b"345"), "3-5") == b"345"
    # a short 206 is an error, not a segment
    with pytest.raises(IOError):
        dm.readRange(_Resp(206, b"34"), "3-5")
    # a server that ignores Range: skipped up to the range, then only the range
    assert dm.readRange(_Resp(200, b"0123456789"), "3-5") == b"345"
    assert dm.readRange(_Resp(200, b"0123456789"), "7-") == b"789"
    with pytest.raises(IOError):
        dm.readRange(_Resp(200, b"01"), "3-5")
    assert dm.readRange(_Resp(200, b"all"), "") == b"all"
