# Offline tests for the automatic link choice: IPTVPlayer/tools/linkpicker.py (height read from a link name,
# the quality closest to "Default video quality", the order "Select link automatically" tries mirrors in).
# The module has no enigma2 / E2iPlayer imports.
import importlib.util
import os

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


def _load():
    spec = importlib.util.spec_from_file_location("linkpicker_under_test", os.path.join(ROOT, "tools", "linkpicker.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lp = _load()


class Link(object):
    def __init__(self, name, failed=False):
        self.name = name
        self.failed = failed


def _names(links):
    return [link.name for link in links]


def test_link_height_formats():
    assert lp.linkHeight("720p") == 720
    assert lp.linkHeight("[HLS] 1080p") == 1080
    assert lp.linkHeight("bitrate: 2500000 res: 1280x720") == 720
    assert lp.linkHeight("[ar] bitrate: 800000 640x360 avc1 25fps") == 360
    assert lp.linkHeight("mp4 4K") == 2160
    assert lp.linkHeight("FHD") == 1080
    assert lp.linkHeight("1080i") == 1080
    assert lp.linkHeight("1280×720") == 720
    # YouTube: height first, or only the height
    assert lp.linkHeight("YouTube | mp4: 360x640") == 360
    assert lp.linkHeight("YouTube | mp4: 720x") == 720
    # portrait video: the shorter side
    assert lp.linkHeight("res: 1080x1920") == 1080


def test_link_height_none():
    assert lp.linkHeight("Vidoza") == 0
    assert lp.linkHeight("bitrate: 128000 audio only") == 0
    assert lp.linkHeight("[f4m/hds] bitrate[1500]") == 0
    assert lp.linkHeight("Server 2024") == 0
    assert lp.linkHeight("") == 0
    assert lp.linkHeight(None) == 0


def test_too_wide_h264():
    assert lp.isTooWideH264("bitrate: 2000000 res: 2592x1080 mp4a,avc1 30fps")
    assert lp.isTooWideH264("[de] bitrate: 9000000 3840x2160 avc1.640033 25fps")
    assert not lp.isTooWideH264("bitrate: 1443297 res: 1280x720 mp4a,avc1 25fps")
    assert not lp.isTooWideH264("bitrate: 5000000 res: 1920x1080 mp4a,avc1 25fps")
    # HEVC / unknown codec: the receiver may well decode it
    assert not lp.isTooWideH264("bitrate: 9000000 res: 3840x2160 mp4a,hvc1 25fps")
    assert not lp.isTooWideH264("2160p")
    assert lp.isTooWideH264("H.264 3840x2160")
    # "avc" inside a word is no codec
    assert not lp.isTooWideH264("Mavcloud 2592x1080")
    assert not lp.isTooWideH264("")


def test_pick_closest_not_above_wish():
    links = [Link("1080p"), Link("720p"), Link("480p")]
    assert lp.pickByQuality(links, "720").name == "720p"
    assert lp.pickByQuality(links, "2160").name == "1080p"
    assert lp.pickByQuality(links, "max").name == "1080p"
    # nothing at or below the wish: the lowest one
    assert lp.pickByQuality(links, "360").name == "480p"


def test_pick_ask_or_no_quality_list():
    links = [Link("1080p"), Link("720p")]
    assert lp.pickByQuality(links, "") is None
    # a mirror list (not every link names a height): the picker stays
    assert lp.pickByQuality([Link("Vidoza 720p"), Link("Streamtape")], "720") is None
    assert lp.pickByQuality([Link("720p")], "720") is None


def test_pick_ignores_audio_only():
    links = [Link("bitrate: 128000 audio only"), Link("res: 1920x1080"), Link("res: 1280x720")]
    assert lp.pickByQuality(links, "720").name == "res: 1280x720"


def test_auto_order_preferred_first_then_host_order():
    links = [Link("Vidoza"), Link("Dood 480p"), Link("VOE 720p"), Link("Streamtape 720p")]
    assert _names(lp.autoOrder(links, "720", lambda link: link.failed)) == ["VOE 720p", "Streamtape 720p", "Dood 480p", "Vidoza"]
    # wish, then the next lower qualities, unknown, the higher ones last
    q = [Link("1080p"), Link("360p"), Link("Server"), Link("720p"), Link("480p")]
    assert _names(lp.autoOrder(q, "720", lambda link: link.failed)) == ["720p", "480p", "360p", "Server", "1080p"]
    assert _names(lp.autoOrder(q, "max", lambda link: link.failed)) == ["1080p", "720p", "480p", "360p", "Server"]
    assert _names(lp.autoOrder(links, "", lambda link: link.failed)) == _names(links)


def test_auto_order_leaves_out_trailer():
    links = [Link("VOE (Deutsch)"), Link("Doodstream (Deutsch)"), Link("Trailer")]
    assert _names(lp.autoOrder(links, "", lambda link: link.failed)) == ["VOE (Deutsch)", "Doodstream (Deutsch)"]
    # all failed: still no trailer
    failed = [Link("VOE", failed=True), Link("Trailer")]
    assert _names(lp.autoOrder(failed, "", lambda link: link.failed)) == ["VOE"]
    # only a trailer: that one
    assert _names(lp.autoOrder([Link("Trailer"), Link("YouTube Trailer")], "", lambda link: link.failed)) == ["Trailer", "YouTube Trailer"]


def test_auto_order_skips_failed_unless_all_failed():
    links = [Link("A", failed=True), Link("B"), Link("C")]
    assert _names(lp.autoOrder(links, "", lambda link: link.failed)) == ["B", "C"]
    allFailed = [Link("A", failed=True), Link("B", failed=True)]
    assert _names(lp.autoOrder(allFailed, "", lambda link: link.failed)) == ["A", "B"]
