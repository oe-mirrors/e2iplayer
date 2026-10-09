# -*- coding: utf-8 -*-
# The torrent hosts are hidden while torrent playback is off: iptvtools.TORRENT_HOSTS decides that, the "torrent"
# group of hostgroups.txt shows them - both lists must name the same hosts, and every one must exist.
# Checked on the sources, no Enigma2 imports needed.
import ast
import io
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), '..', 'IPTVPlayer')


def _torrentHosts():
    with io.open(os.path.join(ROOT, 'tools', 'iptvtools.py'), encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'TORRENT_HOSTS' for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError('TORRENT_HOSTS not found in iptvtools.py')


def _groups():
    with io.open(os.path.join(ROOT, 'hosts', 'hostgroups.txt'), encoding='utf-8') as f:
        return json.load(f)


def test_torrent_group_matches_torrent_hosts():
    assert set(_groups()['torrent']) == _torrentHosts()


def test_torrent_hosts_only_in_torrent_group():
    torrentHosts = _torrentHosts()
    others = dict((g, sorted(torrentHosts & set(hosts))) for g, hosts in _groups().items() if g != 'torrent')
    others = dict((g, hosts) for g, hosts in others.items() if hosts)
    assert not others, 'torrent hosts belong only to the torrent group: %s' % others


def test_torrent_hosts_exist():
    missing = sorted(h for h in _torrentHosts() if not os.path.isfile(os.path.join(ROOT, 'hosts', 'host%s.py' % h)))
    assert not missing, 'torrent hosts without a host file: %s' % missing


def test_torrent_group_icons_exist():
    for size in (100, 120, 135):
        assert os.path.isfile(os.path.join(ROOT, 'icons', 'PlayerSelector', 'groups', 'torrent%d.png' % size))
    assert os.path.isfile(os.path.join(ROOT, 'icons', 'logos', 'groups', 'torrentlogo.png'))
