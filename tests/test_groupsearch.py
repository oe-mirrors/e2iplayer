# -*- coding: utf-8 -*-
# hosts/hostgroupsearch.py must be listed for the "userdefined" group and keep its own icons
import io
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'IPTVPlayer')


def test_listed_in_userdefined():
    with io.open(os.path.join(ROOT, 'hosts', 'hostgroups.txt'), encoding='utf-8') as f:
        assert 'groupsearch' in json.load(f)['userdefined']


def test_icons_exist():
    paths = ['icons/logos/groupsearchlogo.png'] + ['icons/PlayerSelector/groupsearch%d.png' % size for size in (100, 120, 135)]
    for path in paths:
        assert os.path.isfile(os.path.join(ROOT, path)), path


def test_not_part_of_the_web_global_search():
    with io.open(os.path.join(ROOT, 'web', 'webThreads.py'), encoding='utf-8') as f:
        assert "'groupsearch'" in f.read()
