# -*- coding: utf-8 -*-
# urlparser builds its hostMap in __init__ - one entry pointing at a parser that does not exist breaks
# every host on the box (AttributeError while loading). Checked on the source, no Enigma2 imports needed.
import collections
import io
import os
import re

URLPARSER = os.path.join(os.path.dirname(__file__), '..', 'IPTVPlayer', 'libs', 'urlparser.py')


def _source():
    with io.open(URLPARSER, encoding='utf-8') as f:
        return f.read()


def _hostMapEntries(source):
    start = source.index('self.hostMap = {')
    end = source.index('\n        }', start)
    return re.findall(r'^\s*"([^"]+)"\s*:\s*self\.pp\.(\w+)', source[start:end], re.M)


def test_every_mapped_parser_exists():
    source = _source()
    defined = set(re.findall(r'^    def (parser\w+)\(', source, re.M))
    missing = sorted(set(p for _, p in _hostMapEntries(source) if p not in defined))
    assert not missing, 'hostMap points at parsers that do not exist: %s' % missing


def test_no_duplicate_domains():
    entries = _hostMapEntries(_source())
    assert len(entries) > 400
    dups = [d for d, n in collections.Counter(d for d, _ in entries).items() if n > 1]
    assert not dups, 'duplicate hostMap keys: %s' % dups
