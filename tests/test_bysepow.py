# Byse proof of work: IPTVPlayer/scripts/bysepow.py (one worker process per core) and the in-process
# fallback in parserBYSE (libs/urlparser.py) must use the same hash. No network, no enigma2.
import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
SCRIPT = os.path.join(ROOT, "scripts", "bysepow.py")
URLPARSER = os.path.join(ROOT, "libs", "urlparser.py")
FUNCS = ("powBytes", "grAbsorb", "gr")


def _load_script():
    spec = importlib.util.spec_from_file_location("bysepow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _function_source(text, name, indent):
    # the def line up to the next line with the same or a smaller indent
    pad = " " * indent
    match = re.search(r"(?ms)^%sdef %s\(.*?(?=^ {0,%d}\S)" % (pad, name, indent), text)
    assert match, name
    return textwrap.dedent(match.group(0)).strip()


def test_hash_code_in_sync_with_urlparser():
    with open(SCRIPT) as f:
        script = f.read()
    with open(URLPARSER, encoding="utf-8") as f:
        parser = f.read()
    for name in FUNCS:
        assert _function_source(script, name, 0) == _function_source(parser, name, 8), name


def test_strided_workers_find_valid_solutions():
    pow_ = _load_script()
    state = pow_.grAbsorb(pow_.powBytes("e2i-test-nonce:"))
    for k in range(3):
        solution, hashes = pow_.solve("e2i-test-nonce", 6, k, 3, 30)
        assert solution is not None and hashes > 0
        assert int(solution) % 3 == k
        assert pow_.gr(state, pow_.powBytes(solution)) >= 6


def test_single_worker_finds_the_smallest_counter():
    pow_ = _load_script()
    state = pow_.grAbsorb(pow_.powBytes("abc:"))
    solution, hashes = pow_.solve("abc", 5, 0, 1, 30)
    assert hashes == int(solution) + 1
    assert all(pow_.gr(state, pow_.powBytes(str(s))) < 5 for s in range(int(solution)))


def test_cli_solves_and_times_out():
    run = subprocess.run([sys.executable, SCRIPT, "e2i-test-nonce", "6", "1", "2", "30"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert int(out["solution"]) % 2 == 1
    run = subprocess.run([sys.executable, SCRIPT, "e2i-test-nonce", "64", "0", "1", "0"], capture_output=True, text=True)
    assert run.returncode == 3
    assert json.loads(run.stdout)["solution"] is None
    run = subprocess.run([sys.executable, SCRIPT, "x"], capture_output=True, text=True)
    assert run.returncode == 2
