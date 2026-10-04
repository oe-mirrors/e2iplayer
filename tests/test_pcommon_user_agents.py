# pCommon User-Agents (common.getDefaultUserAgent / getDefaultHeader) and common.buildURLWithParams.
# pCommon itself needs enigma2, so only the version constants and the common class are taken out of
# the source; the class body is only defined, none of the enigma2-bound methods run.
import ast
import os
import random
import re
from urllib.parse import unquote_plus, urlencode, urlparse, urlunparse

import pytest

SOURCE = os.path.join(os.path.dirname(__file__), "..", "IPTVPlayer", "libs", "pCommon.py")
CONSTANT = re.compile(r"^_?[A-Z][A-Z_]*$")


@pytest.fixture(scope="module")
def common():
    with open(SOURCE, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    nodes = [n for n in tree.body if (isinstance(n, ast.ClassDef) and n.name == "common")
             or (isinstance(n, ast.Assign) and all(CONSTANT.match(getattr(t, "id", "")) for t in n.targets)
                 and any(getattr(t, "id", "").endswith(("_VERSION", "_CHROME", "_FIREFOX", "_SAFARI_IOS", "_MAG")) for t in n.targets))]
    namespace = {"random": random, "unquote_plus": unquote_plus, "urlencode": urlencode, "urlparse": urlparse,
                 "urlunparse": urlunparse, "printExc": lambda *a: None, "CParsingHelper": None}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), SOURCE, "exec"), namespace)
    return namespace["common"]


FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/27.0 Mobile/15E148 Safari/604.1"


def test_existing_calls_keep_their_browser(common):
    assert common.getDefaultHeader()["User-Agent"] == FIREFOX
    assert common.getDefaultHeader(browser="firefox")["User-Agent"] == FIREFOX
    assert common.getDefaultHeader(browser="chrome")["User-Agent"] == CHROME
    assert common.HOST == CHROME
    # 'Firefox' with a capital F always got the Chrome UA - 98 hosts rely on it
    assert common.getDefaultHeader(browser="Firefox")["User-Agent"] == CHROME
    assert common.getDefaultHeader(browser="iphone")["User-Agent"] == IPHONE
    assert common.getDefaultHeader(browser="iphone_3_0")["User-Agent"] == IPHONE
    assert common.getDefaultHeader(browser="nonsense")["User-Agent"] == CHROME
    assert common.getDefaultHeader(browser=None)["User-Agent"] == CHROME


def test_header_fields_unchanged(common):
    header = common.getDefaultHeader()
    assert header == {"User-Agent": FIREFOX, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                      "Accept-Encoding": "gzip, deflate", "DNT": 1}
    header["User-Agent"] = "changed"
    assert common.getDefaultHeader()["User-Agent"] == FIREFOX


def test_named_user_agents(common):
    assert "Edg/154.0.0.0" in common.getDefaultUserAgent("edge")
    assert common.getDefaultUserAgent("opera").endswith("Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0")
    assert "Version/27.0 Safari/605.1.15" in common.getDefaultUserAgent("safari")
    assert "Android 10; K" in common.getDefaultUserAgent("android")
    assert "SamsungBrowser/30.0 Chrome/143.0.0.0" in common.getDefaultUserAgent("samsung")
    assert "iPad; CPU OS 18_7" in common.getDefaultUserAgent("ipad")
    assert "MAG254" in common.getDefaultUserAgent("mag254")
    assert common.getDefaultUserAgent("vlc") == "VLC/3.0.24 LibVLC/3.0.24"
    assert common.getDefaultHeader(browser="vlc")["User-Agent"] == "VLC/3.0.24 LibVLC/3.0.24"
    # a group name without randomUA gives its first entry
    assert common.getDefaultUserAgent("mobile") == IPHONE
    assert "MAG250" in common.getDefaultUserAgent("mag")
    assert "MAG250" in common.getDefaultUserAgent("qt")
    assert common.getDefaultUserAgent() == CHROME


def test_all_user_agents_use_the_version_constants(common):
    for name, ua in common.USER_AGENTS.items():
        assert ua.startswith("Mozilla/5.0 (") or name == "vlc", name
        assert "%" not in ua, name
        for version in re.findall(r"(?:Chrome|Firefox|Edg)/(\d+)", ua):
            assert version in ("154", "157", "152", "143"), (name, version)
    for group, names in common.USER_AGENT_GROUPS.items():
        assert all(n in common.USER_AGENTS for n in names), group


def test_random_user_agent_stays_in_its_group(common):
    for group, names in common.USER_AGENT_GROUPS.items():
        seen = set(common.getDefaultUserAgent(group, randomUA=True) for _i in range(400))
        assert seen == set(common.USER_AGENTS[n] for n in names), group
    # a single name or an unknown name is not randomised
    assert common.getDefaultUserAgent("iphone", randomUA=True) == IPHONE
    assert common.getDefaultUserAgent("nonsense", randomUA=True) == CHROME


@pytest.mark.parametrize("url, query, multi, expected", [
    ("https://x.tv/a?id=1&id=2&e=&p=1#frag", {"p": 2, "q": "a b"}, None, "https://x.tv/a?id=1&id=2&e=&p=2&q=a+b#frag"),
    ("https://x.tv/a", None, None, "https://x.tv/a"),
    ("https://x.tv/a?x=1", {}, None, "https://x.tv/a?x=1"),
    ("https://x.tv/a?x=1", [("y", "1"), ("y", "2")], None, "https://x.tv/a?x=1&y=1&y=2"),
    ("https://x.tv/a", {"f": {"genre": ["a", "b"]}}, True, "https://x.tv/a?f%5Bgenre%5D%5B0%5D=a&f%5Bgenre%5D%5B1%5D=b"),
    # the other parameters keep their own encoding (latin-1, %2F, +)
    ("https://x.tv/s?q=%E4&path=%2Fa%2Fb&t=a+b&p=1", {"p": 3}, None, "https://x.tv/s?q=%E4&path=%2Fa%2Fb&t=a+b&p=3"),
    # a list value gives a repeated key and replaces every old one
    ("https://x.tv/s?id=1&id=2&x=1", {"id": [7, 8]}, None, "https://x.tv/s?x=1&id=7&id=8"),
    # encoded keys of the old query are matched
    ("https://x.tv/s?f%5Bg%5D%5B0%5D=old&k=1", {"f": {"g": ["new"]}}, True, "https://x.tv/s?k=1&f%5Bg%5D%5B0%5D=new"),
    ("https://x.tv/s?my+key=1", {"my key": 2}, None, "https://x.tv/s?my+key=2"),
    ("https://x.tv/s?1=a", {1: "b"}, None, "https://x.tv/s?1=b"),
    ("https://x.tv/s?a=1", {"f": {}}, True, "https://x.tv/s?a=1"),
    # broken input gives the URL back unchanged
    ("https://x.tv/s?a=1", "abc", None, "https://x.tv/s?a=1"),
])
def test_build_url_with_params(common, url, query, multi, expected):
    assert common.buildURLWithParams(url, query, multi) == expected


def test_build_url_with_params_default_url(common):
    assert common.buildURLWithParams(Query={"a": 1}) == "http://fake/?a=1"
