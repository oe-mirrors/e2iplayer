"""The helper scripts report to the plugin through one JSON line on stderr.

The plugin reads it in two ways (components/captchascriptwidget.py subclasses):
MyE2i cuts the {...} out of the line with a regular expression and calls json.loads on it,
MyJD calls json.loads on the whole line. Both must get back exactly what the script sent.
"""
import ast
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join("IPTVPlayer", "scripts"))

import fakejd  # noqa: E402
import mye2iserver  # noqa: E402

MESSAGES = [
    "MyE2i extension is outdated - please update it.",
    "Can't connect: it said \"no\"",
    "Zeit\u00fcberschreitung \u2013 bitte pr\u00fcfen",
    "path C:\\temp\\x and a new\nline",
    "\u041f\u0440\u0438\u0432\u0435\u0442",
]


@pytest.mark.parametrize("module", [mye2iserver, fakejd])
@pytest.mark.parametrize("text", MESSAGES)
def test_status_line_reads_back_the_same_in_both_widgets(module, text, capsys):
    module.updateStatus("status", text, 500)
    lines = [line for line in capsys.readouterr().err.split("\n") if line]
    assert len(lines) == 1
    expected = {"type": "status", "data": text, "code": 500}
    assert json.loads(lines[0]) == expected  # MyJD widget
    assert json.loads(re.findall("{.*}", lines[0])[0]) == expected  # MyE2i widget


def test_bytes_are_decoded_before_they_are_sent(capsys):
    mye2iserver.updateStatus("captcha_result", b"abc==")
    assert json.loads(capsys.readouterr().err.strip())["data"] == "abc=="


def test_get_page_cf_protection_has_no_shared_default_dict():
    tree = ast.parse(open(os.path.join("IPTVPlayer", "libs", "pCommon.py"), encoding="utf-8").read())
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "getPageCFProtection")
    assert not [d for d in function.args.defaults if isinstance(d, (ast.Dict, ast.List, ast.Set))]
