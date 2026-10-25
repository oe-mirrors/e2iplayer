# -*- coding: utf-8 -*-
# Offline tests for segmented DASH subtitles: IPTVPlayer/libs/dashsubs.py (fragmented MP4 wvtt / stpp, TTML times,
# WebVTT output) and the segment list + local .vtt of IPTVPlayer/libs/dashmpd.py. The MP4 fragments are built here.
import importlib.util
import os
import re
import struct
import sys
import types
import urllib.request

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env():
    saved = dict(sys.modules)
    for pkg in ("Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".libs"):
        sys.modules[pkg] = types.ModuleType(pkg)
    tools = types.ModuleType(PKG + ".tools.iptvtools")
    tools.printDBG = tools.printExc = lambda *a: None
    sys.modules[PKG + ".tools.iptvtools"] = tools
    _load(PKG + ".tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    subs = _load(PKG + ".libs.dashsubs", os.path.join(ROOT, "libs", "dashsubs.py"))
    mpd = _load(PKG + ".libs.dashmpd", os.path.join(ROOT, "libs", "dashmpd.py"))
    yield types.SimpleNamespace(subs=subs, mpd=mpd, strwithmeta=sys.modules[PKG + ".tools.iptvtypes"].strwithmeta)
    sys.modules.clear()
    sys.modules.update(saved)


def box(kind, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), kind.encode("latin-1")) + payload


def full(kind, version, flags, payload):
    return box(kind, bytes([version]) + struct.pack(">I", flags)[1:] + payload)


def init(timescale):
    mdhd = full("mdhd", 0, 0, struct.pack(">IIII", 0, 0, timescale, 0) + b"\x00" * 4)
    return box("ftyp", b"iso6") + box("moov", box("trak", box("mdia", mdhd)))


def fragment(baseTime, samples, version=1):
    # samples: [(duration, bytes)] -> moof (tfhd, tfdt, trun with durations, sizes, data offset) + mdat
    def moof(offset):
        tfhd = full("tfhd", 0, 0x20000, struct.pack(">I", 1))
        tfdt = full("tfdt", version, 0, struct.pack(">Q" if version else ">I", baseTime))
        entries = b"".join(struct.pack(">II", d, len(b)) for d, b in samples)
        trun = full("trun", 0, 0x301, struct.pack(">Ii", len(samples), offset) + entries)
        return box("moof", box("traf", tfhd + tfdt + trun))
    size = len(moof(0))
    return moof(size + 8) + box("mdat", b"".join(b for _d, b in samples))


def vttc(text, settings=""):
    inner = box("payl", text.encode("utf-8"))
    if settings:
        inner = box("sttg", settings.encode("utf-8")) + inner
    return box("vttc", inner)


TTML = """<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml" xmlns:ttp="http://www.w3.org/ns/ttml#parameter" ttp:tickRate="10000000" ttp:frameRate="25">
 <body><div>
  <p begin="%s" end="%s">Erste <span>Zeile</span><br/>zweite   Zeile</p>
  <p begin="%s" dur="1s">Kurz</p>
 </div></body></tt>"""


def test_ttml_times(env):
    t = env.subs.ttmlTime
    assert t("00:01:02.500") == 62.5
    assert t("00:00:10:05", frameRate=25) == 10.2
    assert t("1.5s") == 1.5 and t("1500ms") == 1.5 and t("2m") == 120 and t("50f", frameRate=25) == 2
    assert t("20000000t", tickRate=10000000) == 2
    assert t("") is None and t("bad") is None


def test_ttml_cues(env):
    cues = env.subs.ttmlCues(TTML % ("10000000t", "30000000t", "00:00:05.000"))
    assert cues == [(1.0, 3.0, "Erste Zeile\nzweite Zeile", ""), (5.0, 6.0, "Kurz", "")]


GROWING = """<tt xmlns="http://www.w3.org/ns/ttml"><body><div>
 <p begin="00:00:18.000" end="00:00:22.000"><span begin="0s" end="4s">Beep,</span> <span begin="1s" end="4s">beep,</span>
 <span begin="2s" end="4s">beeeep!</span></p>
</div></body></tt>"""


def test_ttml_growing_line(env):
    # spans with times of their own: one line that grows, not three lines on top of each other (BBC test card)
    assert env.subs.ttmlCues(GROWING) == [(18.0, 19.0, "Beep,", ""), (19.0, 20.0, "Beep, beep,", ""), (20.0, 22.0, "Beep, beep, beeeep!", "")]
    # a line that runs past its sample is cut at the sample end; the next segment brings it again and the joiner
    # makes one cue of the two
    first = fragment(10 * 1000, [(10 * 1000, (TTML % ("00:00:18.000", "00:00:24.000", "00:00:30.000")).encode("utf-8"))])
    second = fragment(20 * 1000, [(10 * 1000, (TTML % ("00:00:18.000", "00:00:24.000", "00:00:30.000")).encode("utf-8"))])
    assert [c[:2] for c in env.subs.segmentCues(first, "stpp", 1000)][0] == (18.0, 20.0)
    j = env.subs.CueJoiner()
    out = j.feed(env.subs.segmentCues(first, "stpp", 1000)) + j.feed(env.subs.segmentCues(second, "stpp", 1000)) + j.close()
    assert "00:00:18.000 --> 00:00:24.000\nErste Zeile\nzweite Zeile\n" in out


def test_wvtt_fragment(env):
    seg = fragment(90000, [(45000, vttc("Hallo", "line:90%") + vttc("Welt")), (45000, box("vtte"))])
    assert env.subs.mdhdTimescale(init(90000)) == 90000
    cues = env.subs.segmentCues(seg, "wvtt", 90000)
    assert cues == [(1.0, 1.5, "Hallo", "line:90%"), (1.0, 1.5, "Welt", "")]
    # presentationTimeOffset
    assert env.subs.segmentCues(seg, "wvtt", 90000, ptoSeconds=1.0)[0][:2] == (0.0, 0.5)


def test_stpp_absolute_and_relative(env):
    # absolute times (ISO/IEC 14496-30) stay, times counted from the sample start get its start added
    absolute = fragment(20 * 1000, [(10 * 1000, (TTML % ("00:00:21.000", "00:00:23.000", "00:00:25.000")).encode("utf-8"))], version=0)
    assert [c[:2] for c in env.subs.segmentCues(absolute, "stpp", 1000)] == [(21.0, 23.0), (25.0, 26.0)]
    relative = fragment(20 * 1000, [(10 * 1000, (TTML % ("00:00:01.000", "00:00:03.000", "00:00:05.000")).encode("utf-8"))])
    assert [c[:2] for c in env.subs.segmentCues(relative, "stpp", 1000)] == [(21.0, 23.0), (25.0, 26.0)]


def test_joiner_merges_and_orders(env):
    j = env.subs.CueJoiner()
    out = j.feed([(0.0, 8.0, "Titel", ""), (6.0, 6.08, "PING!", ""), (9.0, 10.0, "A", "")])
    # "A" may still run on in the next segment, "Titel" / "PING!" are done - written in start order
    assert out.index("Titel") < out.index("PING!") and "\nA\n" not in out
    out = j.feed([(10.0, 12.0, "A", ""), (10.0, 12.0, "A", ""), (12.0, 14.0, "B", "")])
    out += j.close()
    assert "00:00:09.000 --> 00:00:12.000\nA\n" in out and out.count("\nA\n") == 1 and j.count == 4
    assert env.subs.vttTextCues("WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500 align:start\nHi\n") == [(1.0, 2.5, "Hi", "align:start")]


MPD = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT20S">
 <Period id="1">
  <AdaptationSet contentType="video" mimeType="video/mp4" codecs="avc1.640028">
   <SegmentTemplate media="v/$Number$.m4s" duration="4"/><Representation id="v" bandwidth="1" width="1280" height="720"/>
  </AdaptationSet>
  <AdaptationSet contentType="text" mimeType="application/mp4" codecs="wvtt" lang="de">
   <SegmentTemplate timescale="1000" media="sub/$RepresentationID$/$Number%03d$.m4s" initialization="sub/$RepresentationID$/init.mp4" duration="10000"/>
   <Representation id="de" bandwidth="1"/>
  </AdaptationSet>
  <AdaptationSet contentType="text" mimeType="application/mp4" codecs="stpp.ttml.im1i" lang="en">
   <SegmentTemplate media="img/$Number$.m4s" duration="10"/><Representation id="img" bandwidth="1"/>
  </AdaptationSet>
  <AdaptationSet contentType="text" mimeType="application/mp4" codecs="stpp" lang="fr">
   <SegmentTemplate timescale="10" media="fr/$Time$.m4s" initialization="fr/init.mp4" presentationTimeOffset="50">
    <SegmentTimeline><S t="50" d="60" r="1"/><S d="80" r="-1"/></SegmentTimeline>
   </SegmentTemplate>
   <Representation id="fr" bandwidth="1"/>
  </AdaptationSet>
 </Period>
</MPD>"""


def test_segment_lists(env):
    m = env.mpd
    parsed = m.parseMpd(MPD, "https://cdn.example/a/manifest.mpd")
    # the image subtitles (im1i) are left out
    assert [(t["lang"], t["segmented"]) for t in parsed["text"]] == [("de", "wvtt"), ("fr", "stpp")]
    seg = m.subtitleSegments(MPD, "https://cdn.example/a/manifest.mpd", 0, 1, 0, "de")
    assert seg["init"] == "https://cdn.example/a/sub/de/init.mp4" and seg["timescale"] == 1000 and seg["pto"] == 0
    assert seg["segments"] == [("https://cdn.example/a/sub/de/001.m4s", ""), ("https://cdn.example/a/sub/de/002.m4s", "")]
    seg = m.subtitleSegments(MPD, "https://cdn.example/a/manifest.mpd", 0, 3, 0, "fr")
    # 50 + 2 x 60 = 170, then 80 up to the end of the period (pto 5 s + 20 s = 250)
    assert [u.rsplit("/", 1)[1] for u, _r in seg["segments"]] == ["50.m4s", "110.m4s", "170.m4s"] and seg["pto"] == 5.0
    assert m.subtitleKind(types.SimpleNamespace(get=lambda k, d=None: {"mimeType": "text/vtt"}.get(k)), types.SimpleNamespace(get=lambda k, d=None: None)) == "vtt"


def test_local_vtt(env, monkeypatch):
    m = env.mpd
    url = "https://cdn.example/a/manifest.mpd"
    pages = {"https://cdn.example/a/sub/de/init.mp4": init(1000),
             "https://cdn.example/a/sub/de/001.m4s": fragment(0, [(10000, vttc("Eins"))]),
             "https://cdn.example/a/sub/de/002.m4s": fragment(10000, [(10000, vttc("Zwei"))])}
    asked = []

    def fakeFetch(u, headers, byteRange=""):
        asked.append((u, headers.get("Referer")))
        return u, pages[u], 0
    monkeypatch.setattr(m, "_fetch", fakeFetch)
    m.rememberManifest(url, url, MPD, False)
    links = m.buildLinks(m.parseMpd(MPD, url), env.strwithmeta(url, {"Referer": "https://site/"}))
    tracks = links[0]["url"].meta["external_sub_tracks"]
    assert [(t["lang"], t["format"]) for t in tracks] == [("de", "vtt"), ("fr", "vtt")]
    assert m.isLocalSubtitleUrl(tracks[0]["url"]) and m.subtitleProgress(tracks[0]["url"]) is None
    text = urllib.request.urlopen(tracks[0]["url"], timeout=10).read().decode("utf-8")
    assert text.startswith("WEBVTT\n\n")
    # the subtitle download window shows the segments done
    assert m.subtitleProgress(tracks[0]["url"]) == (1, 1)
    assert m.subtitleProgress(url) is None and not m.isLocalSubtitleUrl("http://127.0.0.1:1/dash/x.mpd")
    assert re.findall(r"(\S+) --> (\S+)\n(\w+)", text) == [("00:00:00.000", "00:00:10.000", "Eins"), ("00:00:10.000", "00:00:20.000", "Zwei")]
    # the headers of the link go to the segment requests; the finished text is kept
    assert ("https://cdn.example/a/sub/de/001.m4s", "https://site/") in asked
    count = len(asked)
    assert urllib.request.urlopen(tracks[0]["url"], timeout=10).read().decode("utf-8") == text and len(asked) == count
    # a live MPD offers no segmented subtitles
    live = MPD.replace('type="static"', 'type="dynamic" availabilityStartTime="2026-01-01T00:00:00Z"')
    assert m.parseMpd(live, url)["text"] == []


def _moofNoDurations(sizes, baseTime=None):
    # a moof whose trun gives sizes only (data offset + sizes); the durations come from trex; no tfdt when
    # baseTime is None
    def moof(offset):
        tfhd = full("tfhd", 0, 0x20000, struct.pack(">I", 1))
        tfdt = full("tfdt", 1, 0, struct.pack(">Q", baseTime)) if baseTime is not None else b""
        trun = full("trun", 0, 0x201, struct.pack(">Ii", len(sizes), offset) + b"".join(struct.pack(">I", s) for s in sizes))
        return box("moof", box("traf", tfhd + tfdt + trun))
    return moof(len(moof(0)) + 8)


def test_trex_default_duration_and_moof_without_tfdt(env):
    trex = full("trex", 0, 0, struct.pack(">IIIII", 1, 1, 500, 0, 0))
    initSeg = box("ftyp", b"iso6") + box("moov", box("mvex", trex))
    assert env.subs.trexDefaultDuration(initSeg) == 500 and env.subs.trexDefaultDuration(init(1000)) == 0
    one, two = vttc("Eins"), vttc("Zwei")
    seg = _moofNoDurations([len(one)], 2000) + box("mdat", one) + _moofNoDurations([len(two)]) + box("mdat", two)
    # the second moof has no tfdt: it goes on where the first ended
    assert [(t, d) for t, d, _s in env.subs.fragmentSamples(seg, 500)] == [(2000, 500), (2500, 500)]
    assert [c[:3] for c in env.subs.segmentCues(seg, "wvtt", 1000, defaultDuration=500)] == [(2.0, 2.5, "Eins"), (2.5, 3.0, "Zwei")]


def test_ttml_rates_nesting_and_text(env):
    import xml.etree.ElementTree as ET
    ttp = 'xmlns="http://www.w3.org/ns/ttml" xmlns:ttp="http://www.w3.org/ns/ttml#parameter"'
    rate, ticks = env.subs.ttmlRates(ET.fromstring('<tt %s ttp:frameRate="30" ttp:frameRateMultiplier="1000 1001"/>' % ttp))
    assert rate == pytest.approx(29.97, abs=0.001) and ticks == pytest.approx(29.97, abs=0.001)
    # without tickRate: frameRate x subFrameRate ticks per second
    assert env.subs.ttmlRates(ET.fromstring('<tt %s ttp:frameRate="25" ttp:subFrameRate="2"/>' % ttp)) == (25.0, 50.0)
    assert env.subs.ttmlRates(ET.fromstring('<tt %s/>' % ttp)) == (30.0, 1.0)
    # times count from the parent and end with it; a <p> without times runs with its div; "<" stays visible text
    doc = """<tt xmlns="http://www.w3.org/ns/ttml"><body><div begin="10s" end="12s">
      <p begin="1s" end="5s">Lang</p><p>Ganz &lt;b&gt;</p></div></body></tt>"""
    assert env.subs.ttmlCues(doc) == [(11.0, 12.0, "Lang", ""), (10.0, 12.0, u"Ganz ‹b›", "")]
    # a blank line inside a cue would end it early
    assert env.subs.vttCue((1.0, 2.0, "A\n\nB", "")) == "00:00:01.000 --> 00:00:02.000\nA\nB\n\n"


def test_second_request_waits_for_the_first(env, monkeypatch):
    # the player and the download manager ask at the same time: one run fetches the segments, the second request
    # gets blank lines while it waits, then the same cues
    import threading
    m = env.mpd
    url = "https://cdn.example/b/manifest.mpd"
    pages = {"https://cdn.example/b/sub/de/init.mp4": init(1000),
             "https://cdn.example/b/sub/de/001.m4s": fragment(0, [(10000, vttc("Eins"))]),
             "https://cdn.example/b/sub/de/002.m4s": fragment(10000, [(10000, vttc("Zwei"))])}
    asked, release = [], threading.Event()

    def slowFetch(u, headers, byteRange=""):
        asked.append(u)
        if u.endswith("002.m4s"):
            release.wait(5)
        return u, pages[u], 0
    monkeypatch.setattr(m, "_fetch", slowFetch)
    monkeypatch.setattr(m, "SUBTITLE_KEEPALIVE", 0.1)
    m.rememberManifest(url, url, MPD, False)
    links = m.buildLinks(m.parseMpd(MPD, url), env.strwithmeta(url, {}))
    sub = links[0]["url"].meta["external_sub_tracks"][0]["url"]
    texts = []

    def get():
        texts.append(urllib.request.urlopen(sub, timeout=10).read().decode("utf-8"))
    first = threading.Thread(target=get)
    first.start()
    while "https://cdn.example/b/sub/de/002.m4s" not in asked:
        release.wait(0.01)
    second = threading.Thread(target=get)
    second.start()
    release.wait(0.4)
    release.set()
    first.join(10)
    second.join(10)
    assert len(texts) == 2 and asked.count("https://cdn.example/b/sub/de/001.m4s") == 1
    cues = [re.findall(r"--> \S+\n(\w+)", t) for t in texts]
    assert cues == [["Eins", "Zwei"], ["Eins", "Zwei"]]
    assert any("\n\n\n" in t for t in texts)
