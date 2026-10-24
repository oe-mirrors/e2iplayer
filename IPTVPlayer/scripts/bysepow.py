# -*- coding: utf-8 -*-
# add 241026: proof of work of the Byse player (libs/urlparser.py parserBYSE), one worker per CPU core.
#
# Python threads do not run in parallel (GIL), so parserBYSE starts this script once per core with the
# same nonce: worker k of n tries the counters k, k+n, k+2n, ... and the first one that finds a solution
# wins (the others are killed). Any counter whose hash has enough leading zero bits is a valid solution.
#
# Usage: bysepow.py <pow_nonce> <difficulty> <start> <step> <timeout seconds>
# Output (stdout, one JSON line): {"solution": "<counter>" or null, "hashes": <tried>}
# Exit codes: 0 solved, 1 internal error, 2 usage, 3 time limit reached.
#
# The hash is the same code as the in-process fallback in parserBYSE (tests/test_bysepow.py checks
# that both copies stay identical). Python 2.7 and 3 compatible, no enigma2 imports.
from __future__ import print_function

import json
import os
import sys
import time


# Proof of work of the player (assets/pow-*.js: gr/wr/Er): find a counter s so that the custom
# 512-word ChaCha-style hash of "<pow_nonce>:<s>" starts with pow_difficulty zero bits. Pure Python
# is ~100x slower than the browser, so the solver is written flat: the ChaCha quarter round (ye) is
# inlined on local variables (no function calls or list writes per round), the constant
# "<pow_nonce>:" prefix is absorbed only once, and gr() stops at the first non-zero output word.
def powBytes(s):
    # like the player's yr(): one byte per char code (& 255); a list behaves the same on py2 and py3
    return [ord(ch) & 255 for ch in s]


def grAbsorb(data, state=(1779033703, 3144134277, 1013904242, 2773480762)):
    M = 0xFFFFFFFF
    a, b, c, d = state
    for i in data:
        a = (a + i) & M
        a = ((a << 7) | (a >> 25)) & M
        a = (a + b) & M
        d ^= a
        d = ((d << 16) | (d >> 16)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 12) | (b >> 20)) & M
        a = (a + b) & M
        d ^= a
        d = ((d << 8) | (d >> 24)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 7) | (b >> 25)) & M
    return a, b, c, d


def gr(state, tail):
    # number of leading zero bits of the player's gr() hash of (absorbed prefix + tail), same as
    # wr(gr()) in the player JS; the eight output words are only computed until one is non-zero
    M = 0xFFFFFFFF
    a, b, c, d = grAbsorb(tail, state)
    for _i in range(8):
        a = (a + b) & M
        d ^= a
        d = ((d << 16) | (d >> 16)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 12) | (b >> 20)) & M
        a = (a + b) & M
        d ^= a
        d = ((d << 8) | (d >> 24)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 7) | (b >> 25)) & M
    r = [0] * 512
    for i in range(512):
        a = (a + b) & M
        d ^= a
        d = ((d << 16) | (d >> 16)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 12) | (b >> 20)) & M
        a = (a + b) & M
        d ^= a
        d = ((d << 8) | (d >> 24)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 7) | (b >> 25)) & M
        r[i] = a ^ c
    for _i in range(2):
        for s in range(512):
            x = r[s]
            x = (x + r[x & 511]) & M
            x = ((x << 13) | (x >> 19)) & M
            x ^= (r[(s + 1) & 511] * 2654435761) & M
            r[s] = x
            a ^= x
            a = (a + b) & M
            d ^= a
            d = ((d << 16) | (d >> 16)) & M
            c = (c + d) & M
            b ^= c
            b = ((b << 12) | (b >> 20)) & M
            a = (a + b) & M
            d ^= a
            d = ((d << 8) | (d >> 24)) & M
            c = (c + d) & M
            b ^= c
            b = ((b << 7) | (b >> 25)) & M
    zeros = 0
    for i in range(0, 512, 64):
        a = (a + b) & M
        d ^= a
        d = ((d << 16) | (d >> 16)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 12) | (b >> 20)) & M
        a = (a + b) & M
        d ^= a
        d = ((d << 8) | (d >> 24)) & M
        c = (c + d) & M
        b ^= c
        b = ((b << 7) | (b >> 25)) & M
        s = a
        for x in r[i:i + 64]:
            s = (s + x) & M
            s = ((s << 5) | (s >> 27)) & M
            s ^= (x * 2246822519) & M
        s ^= c
        if s:
            return zeros + 32 - s.bit_length()
        zeros += 32
    return zeros


def solve(nonce, difficulty, start, step, timeout):
    # returns (solution or None, hashes tried); the time limit is checked every 16 hashes
    if difficulty <= 0:
        return "0", 0
    state = grAbsorb(powBytes(nonce + ":"))
    begin = time.time()
    s = start
    tried = 0
    while True:
        for _i in range(16):
            if gr(state, powBytes(str(s))) >= difficulty:
                return str(s), tried + 1
            s += step
            tried += 1
        if time.time() - begin > timeout:
            return None, tried


def main(argv):
    if len(argv) != 6:
        print("usage: bysepow.py <pow_nonce> <difficulty> <start> <step> <timeout>", file=sys.stderr)
        return 2
    try:
        nonce = argv[1]
        difficulty, start, step = int(argv[2]), int(argv[3]), max(1, int(argv[4]))
        timeout = float(argv[5])
    except ValueError:
        print("bysepow: bad arguments", file=sys.stderr)
        return 2
    try:
        # the box keeps playing / recording while all cores are busy here
        os.nice(10)
    except Exception:
        pass
    solution, hashes = solve(nonce, difficulty, start, step, timeout)
    print(json.dumps({"solution": solution, "hashes": hashes}))
    sys.stdout.flush()
    return 0 if solution is not None else 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print("bysepow: %s" % e, file=sys.stderr)
        sys.exit(1)
