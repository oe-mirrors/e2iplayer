"""On-screen keyboard data: key grid, layout list, .kle files and flags.

Read from the source with ast, so no enigma2 is needed.
"""
import ast
import io
import os
import re

import pytest

VK_SOURCE = "IPTVPlayer/components/e2ivk.py"
VK_DIR = "IPTVPlayer/vk"
FLAG_DIRS = ["IPTVPlayer/icons/%s/e2ivk/flags" % tier for tier in ("HD", "FHD", "WQHD")]
# historic scripts without a country: no flag
NO_FLAG = {"00120c00", "000c0c00"}  # Futhark, Gothic


def _class_data():
    with open(VK_SOURCE, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "E2iVirtualKeyBoard")
    wanted = ("KEYIDMAP", "ALL_VK_LAYOUTS", "DEFAULT_VK_LAYOUT")
    return {n.targets[0].id: ast.literal_eval(n.value) for n in cls.body if isinstance(n, ast.Assign) and n.targets[0].id in wanted}


DATA = _class_data()
GRID = DATA["KEYIDMAP"]
LAYOUTS = DATA["ALL_VK_LAYOUTS"]
# keys that type characters, as in E2iVirtualKeyBoard.CHARACTER_KEYS
CHARACTER_KEYS = set(list(range(2, 15)) + list(range(17, 29)) + list(range(31, 42)) + [63] + list(range(44, 55)) + [59])


def _read_kle(layout_id):
    with io.open(os.path.join(VK_DIR, "%s.kle" % layout_id), encoding="utf-16", newline='') as f:
        return ast.literal_eval(f.read())


def _flag_name(names, locale):
    # same lookup as E2iVKSelectionList._getFlagName()
    if locale + ".png" in names:
        return locale + ".png"
    parts = re.split("[_-]", locale)
    if len(parts) > 2 and "%s_%s.png" % (parts[0], parts[-1]) in names:
        return "%s_%s.png" % (parts[0], parts[-1])
    if len(parts) > 1:
        for name in names:
            if name.endswith("_%s.png" % parts[-1]):
                return name
    for name in names:
        if name.startswith(parts[0] + "_"):
            return name
    return "missing.png"


def test_grid_is_iso_48():
    assert all(len(row) == 15 for row in GRID)
    ids = set(key for row in GRID for key in row)
    assert ids == set(range(64))
    # Caps Lock is a single key, 63 sits between the last letter key and Enter
    assert GRID[3].count(30) == 1
    assert GRID[3][12] == 63 and GRID[3][13] == GRID[3][14] == 42
    assert CHARACTER_KEYS <= ids and len(CHARACTER_KEYS - {59}) == 48


def test_character_keys_match_source():
    with open(VK_SOURCE, encoding="utf-8") as f:
        source = f.read()
    expr = re.search(r"^    CHARACTER_KEYS = (.+)$", source, re.M).group(1)
    # own source, plain list arithmetic
    assert set(eval(expr, {"__builtins__": {"list": list, "range": range}})) == CHARACTER_KEYS


def test_layout_list():
    assert len(LAYOUTS) == 218
    ids = [item[2] for item in LAYOUTS]
    assert len(set(ids)) == len(ids)
    assert sorted(f[:-4] for f in os.listdir(VK_DIR) if f.endswith(".kle")) == sorted(ids)


@pytest.mark.parametrize("name,locale,layout_id", LAYOUTS)
def test_kle_file(name, locale, layout_id):
    layout = _read_kle(layout_id)
    assert layout["id"] == layout_id
    assert layout["locale"]
    assert set(layout["layout"]) <= CHARACTER_KEYS, sorted(set(layout["layout"]) - CHARACTER_KEYS)
    assert isinstance(layout["deadkeys"], dict)


def test_default_layout_is_its_kle():
    default = DATA["DEFAULT_VK_LAYOUT"]
    assert default == _read_kle(default["id"])
    assert default["id"] in [item[2] for item in LAYOUTS]


def test_german_layout():
    de = _read_kle("00000407")["layout"]
    assert de[22][0] == "z" and de[45][0] == "y"            # QWERTZ
    assert de[63][0] == "#" and de[63][1] == "'"            # key next to Enter
    assert de[44][0] == "<" and de[44][1] == ">"            # key next to the left Shift
    # Caps Lock types Y and X (these keys had no Caps Lock state before)
    assert de[45][8] == "Y" and de[46][8] == "X"


def test_french_layout_is_azerty():
    fr = _read_kle("0000040c")["layout"]
    assert fr[17][0] == "a" and fr[31][0] == "q" and fr[45][0] == "w"


@pytest.mark.parametrize("flag_dir", FLAG_DIRS)
def test_every_layout_has_a_flag(flag_dir):
    names = sorted(os.listdir(flag_dir))
    assert "missing.png" in names
    without = [item for item in LAYOUTS if _flag_name(names, item[1]) == "missing.png" and item[2] not in NO_FLAG]
    assert not without, without
    assert _flag_name(names, "de_DE") == "de_DE.png"
    assert _flag_name(names, "sr_Cyrl-CS") == "sr_CS.png"   # without the script part
    assert _flag_name(names, "as_IN") == "hi_IN.png"        # same country


def test_flag_sets_equal():
    sets = [sorted(os.listdir(d)) for d in FLAG_DIRS]
    assert sets[0] == sets[1] == sets[2]
