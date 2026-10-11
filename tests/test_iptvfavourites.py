# Offline tests for the favourites helpers "Remove marked items from favourites" uses:
# IPTVPlayer/tools/iptvfavourites.py findItemsOfKeys() (the stored favourites of identity keys, in every group) and
# delGroupItems() (several at once, the highest index first), with a load / save round trip through real files, and
# the order the favourites group removes marked rows in (storage position, host list, shuffled display list).
# The enigma2 / E2iPlayer imports are stubbed; e2ijson and listselection are the real ones.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"


class CFavItem(object):
    # components/ihost.py CFavItem, the parts the favourites file uses
    def __init__(self, name='', data='', resolver='SELF', hostName=''):
        self.name = name
        self.description = ''
        self.type = 'VIDEO'
        self.iconimage = ''
        self.data = data
        self.resolver = resolver
        self.hostName = hostName

    def setFromDict(self, data):
        for key in data:
            setattr(self, key, data[key])
        return self

    def getAsDict(self):
        return vars(self)


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fav():
    saved = dict(sys.modules)
    for pkg in ("Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".components", PKG + ".libs"):
        _stubModule(pkg)
        sys.modules[pkg].__path__ = []
    _stubModule(PKG + ".components.iptvplayerinit", TranslateTXT=lambda text: text)
    _stubModule(PKG + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None)
    _stubModule(PKG + ".components.ihost", CFavItem=CFavItem)
    _load(PKG + ".libs.e2ijson", os.path.join(ROOT, "libs", "e2ijson.py"))
    module = _load(PKG + ".tools.iptvfavourites", os.path.join(ROOT, "tools", "iptvfavourites.py"))
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _item(name, host='ted', extra=None):
    data = {'title': name, 'url': 'https://example.org/' + name}
    data.update(extra or {})
    return CFavItem(name, json_dumps(data), host, host)


def json_dumps(data):
    import json
    return json.dumps(data, sort_keys=True)


def _key(fav, item):
    return fav.IPTVFavourites.getItemIdentityKey(item.hostName, item.resolver, item.data)


def _helper(fav, groups):
    helper = fav.IPTVFavourites('unused')
    helper.groups = [{'group_id': gid, 'title': gid.upper(), 'items': list(items)} for gid, items in groups]
    return helper


def _names(helper, gid):
    return [item.name for item in helper.getGroup(gid)['items']]


def test_find_items_of_keys_in_every_group(fav):
    a, b, c = _item('a'), _item('b'), _item('c')
    # the same item in another listing (other description / watched state) is the same favourite
    aAgain = _item('a', extra={'desc': 'other', 'isWatched': True})
    helper = _helper(fav, [('one', [a, b, c]), ('two', [c, aAgain])])
    found = helper.findItemsOfKeys({_key(fav, a), _key(fav, c)})
    assert [(gid, idx) for gid, idx, key in found] == [('one', 0), ('one', 2), ('two', 0), ('two', 1)]
    assert set(key for gid, idx, key in found) == {_key(fav, a), _key(fav, c)}


def test_meta_keys_are_no_identity(fav):
    # a favourite stored before its host set the moviemeta keys stays the same item
    old = _item('a')
    new = _item('a', extra={'meta_type': 'movie', 'meta_title': 'A', 'meta_year': '2026', 'meta_imdb': 'tt1234567'})
    assert _key(fav, old) == _key(fav, new)


def test_find_items_of_keys_other_host_or_nothing(fav):
    a = _item('a')
    helper = _helper(fav, [('one', [a])])
    assert helper.findItemsOfKeys({_key(fav, _item('a', host='youtube'))}) == []
    assert helper.findItemsOfKeys(set()) == []


def test_del_group_items_highest_index_first(fav):
    items = [_item(name) for name in 'abcdef']
    helper = _helper(fav, [('one', items), ('two', [_item('x'), _item('y')])])
    # given in any order: deleting index 1 first would move the others
    count = helper.delGroupItems([('one', 1), ('one', 4), ('two', 0), ('one', 2)])
    assert count == 4
    assert _names(helper, 'one') == ['a', 'd', 'f']
    assert _names(helper, 'two') == ['y']


def test_del_group_items_leaves_out_doubles_and_unknown(fav):
    helper = _helper(fav, [('one', [_item(name) for name in 'abc'])])
    count = helper.delGroupItems([('one', 1), ('one', 1), ('one', 7), ('one', -1), ('nogroup', 0)])
    assert count == 1
    assert _names(helper, 'one') == ['a', 'c']
    assert helper.delGroupItems([]) == 0


def test_remove_marked_of_a_host_list_round_trip(fav, tmp_path):
    # in a host list: the marked rows' favourites go from every group, everything else stays in the files
    favDir = str(tmp_path)
    a, b, c, d = _item('a'), _item('b'), _item('c'), _item('d')
    helper = fav.IPTVFavourites(favDir)
    for gid in ('one', 'two'):
        helper.addGroup({'group_id': gid, 'title': gid.upper()})
    for item in (a, b, c):
        helper.addGroupItem(item, 'one')
    for item in (c, d, a):
        helper.addGroupItem(item, 'two')
    assert helper.save()

    helper = fav.IPTVFavourites(favDir)
    assert helper.load()
    marked = {_key(fav, a), _key(fav, c), _key(fav, _item('notstored'))}
    found = helper.findItemsOfKeys(marked)
    assert helper.delGroupItems([(entry[0], entry[1]) for entry in found]) == 4
    assert helper.save()

    helper = fav.IPTVFavourites(favDir)
    assert helper.load()
    assert _names(helper, 'one') == ['b']
    assert _names(helper, 'two') == ['d']
    assert fav.getFavouritesIdentityKeys(favDir) == frozenset([_key(fav, b), _key(fav, d)])


def test_remove_marked_rows_of_a_favourites_group(fav):
    # inside a favourites group (iptvplayerwidget._deleteFavouriteRows): the group is shown sorted, so storage
    # position != host list position, and the display list is shuffled. The stored favourites go highest storage
    # position first, then the rows one by one with their host index read again (hostfavourites
    # onGroupItemDeleted + listselection.removeRow) - the other rows keep host index and storage position.
    ls = _load("listselection_under_test", os.path.join(ROOT, "tools", "listselection.py"))
    stored = [_item(name) for name in 'abcdef']
    helper = _helper(fav, [('one', stored)])
    # host rows (hostfavourites currList): sorted e c a f b d, item_idx = storage position
    rawRows = [{'name': item.name, 'group_id': 'one', 'item_idx': stored.index(item)} for item in [stored[i] for i in (4, 2, 0, 5, 1, 3)]]

    class Row(object):
        def __init__(self, name, itemIdx):
            self.name = name
            self.itemIdx = itemIdx

    original = [Row(raw['name'], idx) for idx, raw in enumerate(rawRows)]
    order = [5, 0, 3, 1, 4, 2]
    shown = ls.arrangeRows(original, lambda row: True, order)
    marked = [row for row in shown if row.name in ('a', 'f', 'e')]

    def groupItemIdx(index):
        return rawRows[index]['item_idx']

    def onGroupItemDeleted(index, storageIdx):
        del rawRows[index]
        for params in rawRows:
            if params['item_idx'] > storageIdx:
                params['item_idx'] -= 1

    entries = sorted([(groupItemIdx(row.itemIdx), row) for row in marked], key=lambda entry: entry[0], reverse=True)
    assert helper.delGroupItems([('one', entry[0]) for entry in entries]) == 3
    for storageIdx, row in entries:
        onGroupItemDeleted(row.itemIdx, storageIdx)
        original, order = ls.removeRow(original, row, lambda row: True, order)
        shown.remove(row)

    assert _names(helper, 'one') == ['b', 'c', 'd']
    assert [raw['name'] for raw in rawRows] == ['c', 'b', 'd']
    for row in shown:
        # every remaining row still points at its own host row and its own stored favourite
        assert rawRows[row.itemIdx]['name'] == row.name
        assert helper.getGroup('one')['items'][groupItemIdx(row.itemIdx)].name == row.name
    assert [row.name for row in ls.arrangeRows(original, lambda row: True, order)] == [row.name for row in shown]
