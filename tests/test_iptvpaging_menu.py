# Offline test of the "Main menu" row of tools/iptvpaging.py: the Enigma2 / E2iPlayer imports are stubbed.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


@pytest.fixture
def paging():
    saved = dict(sys.modules)
    for pkg in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.components",
                "Plugins.Extensions.IPTVPlayer.tools"):
        _stubModule(pkg)
    _stubModule("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit", TranslateTXT=lambda t: t)
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None)
    spec = importlib.util.spec_from_file_location("iptvpaging_under_test", os.path.join(ROOT, "tools", "iptvpaging.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


class _Host(object):
    def __init__(self):
        self.rows = []

    def addDir(self, params):
        self.rows.append(params)


def _kinds(host):
    return [row.get("image_type", row["title"]) for row in host.rows]


def test_main_menu_row_first_on_a_paged_list(paging):
    host = _Host()
    paging.addPagingItems(host, {"category": "list", "url": "https://site/list/", "page": 2}, 2, True, 5, "https://site/list/{page}/")
    assert _kinds(host) == [paging.MENU_IMAGE_TYPE, "FIRST", "JUMP", "Next page"]
    assert host.rows[0]["title"] == "Main menu" and "page" not in host.rows[0]


def test_no_main_menu_row_on_a_single_page(paging):
    host = _Host()
    paging.addPagingItems(host, {"category": "list"}, 1, False)
    assert host.rows == []
    paging.addPagingItems(host, {"category": "list"}, 1, True)
    assert _kinds(host)[0] == paging.MENU_IMAGE_TYPE
