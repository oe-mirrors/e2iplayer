# -*- coding: utf-8 -*-
# Offline tests for the exteplayer3 capability probe (tools/iptvtools.py: GetExtePlayer3Info and the helpers on it) and
# the ClearKey keys of OstoraTV (hosts/hostostoratv.py: _clearKeys). The functions are taken out of their modules (the
# modules need Enigma2), the player is a small fake script that writes what exteplayer3 writes.
import ast
import base64
import os
import stat
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PROBE_FUNCS = ("GetExtePlayer3Info", "ExtePlayer3Version", "ExtePlayer3Cap", "ExtePlayer3CoversBufferingReason")


def _functions(relPath, names, namespace):
    tree = ast.parse(open(os.path.join(ROOT, relPath), encoding="utf-8").read())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(nodes, []), relPath, "exec"), namespace)
    return namespace


def _fakePlayer(tmp_path, stderrText):
    # a "player" that writes stderrText to stderr and the usage to stdout, like exteplayer3 without arguments
    data = tmp_path / "stderr.txt"
    data.write_text(stderrText)
    if os.name == "nt":
        path = tmp_path / "exteplayer3.bat"
        path.write_text('@"%s" -c "import sys; sys.stderr.write(open(r\'%s\').read()); print(\'Usage: exteplayer3\')"\n' % (sys.executable, data))
    else:
        path = tmp_path / "exteplayer3"
        path.write_text("#!/bin/sh\ncat '%s' >&2\necho 'Usage: exteplayer3'\n" % data)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def _probe(tmp_path, stderrText):
    ns = {"os": os, "threading": None, "printDBG": lambda *a: None, "printExc": lambda *a: None,
          "ensure_str": lambda b, errors="strict": b.decode("utf-8", errors) if isinstance(b, bytes) else b,
          "EXTEPLAYER3_PATH": _fakePlayer(tmp_path, stderrText), "_extePlayer3Info": [(None, {})]}
    return _functions("tools/iptvtools.py", PROBE_FUNCS, ns)


def test_probe_reads_the_extended_line(tmp_path):
    ns = _probe(tmp_path, '{"EPLAYER3_EXTENDED":{"version":188,"start":1,"xcode":7,"hlsseg":3,"drmkey":3}}\n')
    assert ns["ExtePlayer3Version"]() == 188
    assert ns["ExtePlayer3Cap"]("hlsseg") == 3 and ns["ExtePlayer3Cap"]("cover") == 0
    assert ns["ExtePlayer3CoversBufferingReason"]("hlsseg1") and ns["ExtePlayer3CoversBufferingReason"]("hlsseg2")
    assert ns["ExtePlayer3CoversBufferingReason"]("avcc") and ns["ExtePlayer3CoversBufferingReason"]("chunkedpl")
    assert not ns["ExtePlayer3CoversBufferingReason"]("unknown")


def test_probe_of_an_older_player(tmp_path):
    # image player 185: the version only - no capability, no reason covered
    ns = _probe(tmp_path, '{"EPLAYER3_EXTENDED":{"version":185}}\n')
    assert ns["ExtePlayer3Version"]() == 185 and ns["ExtePlayer3Cap"]("hlsseg") == 0
    assert not ns["ExtePlayer3CoversBufferingReason"]("hlsseg1") and not ns["ExtePlayer3CoversBufferingReason"]("oldtls")


def test_probe_is_cached_until_the_binary_changes(tmp_path):
    ns = _probe(tmp_path, '{"EPLAYER3_EXTENDED":{"version":188,"hlsseg":1}}\n')
    assert ns["ExtePlayer3Cap"]("hlsseg") == 1
    key, info = ns["_extePlayer3Info"][0]
    assert key is not None and info["version"] == 188
    # the same stat key: the cached dict, the player is not started again
    ns["_extePlayer3Info"][0] = (key, {"version": 999})
    assert ns["ExtePlayer3Version"]() == 999


def test_probe_without_the_line_or_player(tmp_path):
    ns = _probe(tmp_path, "some other output\n")
    assert ns["GetExtePlayer3Info"]() == {} and ns["ExtePlayer3Version"]() == 0
    ns["EXTEPLAYER3_PATH"] = str(tmp_path / "missing")
    assert ns["GetExtePlayer3Info"]() == {}


def _clearKeys():
    ns = {"base64": base64, "ensure_str": lambda b: b.decode() if isinstance(b, bytes) else b}
    return _functions("hosts/hostostoratv.py", ("_clearKeys",), ns)["_clearKeys"]


def test_ostora_clear_keys():
    clearKeys = _clearKeys()
    # the app's form (28.11.2026): base64 without padding, "+" and "/"
    assert clearKeys("lizuSe6UIrRKbGCnmZhUrQ:cUx4nHZoZjJlLu/BnxjD2w") == "962cee49ee9422b44a6c60a7999854ad:714c789c76686632652eefc19f18c3db"
    # base64url and two pairs
    pair = "lizuSe6UIrRKbGCnmZhUrQ:cUx4nHZoZjJlLu_BnxjD2w"
    assert clearKeys(pair + "," + pair).count(",") == 1
    # wrong length, no ":" or no base64: no keys (the source is left out)
    assert clearKeys("AAAA:BBBB") == "" and clearKeys("lizuSe6UIrRKbGCnmZhUrQ") == "" and clearKeys("!!:??") == ""
