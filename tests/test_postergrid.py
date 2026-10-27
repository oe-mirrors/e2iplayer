# Offline test of the poster grid of the main list (components/iptvpostergrid.py): Enigma2 and the list base
# class are stubbed, the grid logic (when a list becomes a grid, item index <-> row/column, keys, highlight,
# pictures) is the real one.
import importlib.util
import os
import struct
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
TYPE_TEXT = 1


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


class _Size(object):
    def __init__(self, w, h):
        self.w, self.h = w, h

    def width(self):
        return self.w

    def height(self):
        return self.h


class _Content(object):
    # eListboxPythonMultiContent: the entries and the item height
    def __init__(self):
        self.entries = []
        self.itemHeight = 32
        self.invalidated = []

    def setList(self, entries):
        self.entries = entries

    def setItemHeight(self, h):
        self.itemHeight = h

    def getItemSize(self):
        return _Size(1000, self.itemHeight)

    def setFont(self, idx, font):
        pass

    def invalidateEntry(self, idx):
        self.invalidated.append(idx)

    def invalidate(self):
        self.invalidated.append('all')


class _Instance(object):
    # the eListbox: the current row, reports a change like the real one
    def __init__(self, owner, w=1200, h=384):
        self.owner = owner
        self.index = 0
        self.w, self.h = w, h
        self.selectionEnabled = 1

    def size(self):
        return _Size(self.w, self.h)

    def getCurrentIndex(self):
        return self.index

    def moveSelectionTo(self, idx):
        if idx != self.index:
            self.index = idx
            self.owner.selectionChanged()

    def setSelectionEnable(self, en):
        self.selectionEnabled = en


class _Pixmap(object):
    def __init__(self, w, h):
        self.w, self.h = w, h

    def size(self):
        return _Size(self.w, self.h)


class _PicLoad(object):
    instances = []

    def __init__(self):
        self.PictureData = object()
        self.started = []
        self.broken = False
        _PicLoad.instances.append(self)

    def setPara(self, para):
        self.para = para

    def startDecode(self, path):
        self.started.append(path)
        return 0

    def getData(self):
        # broken: ePicLoad started on the file but made no picture of it (an empty file)
        return None if self.broken else _Pixmap(self.para[0], self.para[1])


class _Timer(object):
    def __init__(self):
        self.timeout = object()
        self.starts = 0

    def start(self, *a):
        self.starts += 1

    def stop(self):
        pass


class _BaseList(object):
    # the parts of IPTVMainNavigatorList the grid uses
    def __init__(self):
        self.l = _Content()
        self.font = ("Regular", 18, 35, 0)
        self.dictPIX = {}
        self.ICON_W = 31
        self.watchedBadgePIX = self.startedBadgePIX = self.selectMarkerPIX = None
        self.instance = None
        self.changes = 0

    def onCreate(self):
        pass

    def onDestroy(self):
        pass

    def selectionChanged(self):
        self.changes += 1

    def _getRowMarkers(self, item):
        return []

    def getCurrent(self):
        return self.l.entries[self.instance.index][0]

    def getCurrentIndex(self):
        return self.instance.index

    def moveToIndex(self, index):
        self.instance.index = index

    def buildEntry(self, item):
        return ['list', item]


class _Item(object):
    def __init__(self, name, icon='', type='video', imageType='video'):
        self.name = name
        self.iconimage = icon
        self.type = type
        self.imageType = imageType

    def getDisplayTitle(self):
        return self.name

    def getTextColor(self):
        return None


@pytest.fixture
def pg():
    saved = dict(sys.modules)
    _PicLoad.instances = []
    for pkg in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                "Plugins.Extensions.IPTVPlayer.components", "Plugins.Extensions.IPTVPlayer.tools", "Components"):
        _stubModule(pkg)
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
                eConnectCallback=lambda signal, fnc: (signal, fnc))
    itemTypes = {'TYPE_NEXT': 'next', 'TYPE_JUMP': 'jump', 'TYPE_FIRST': 'first', 'TYPE_PREVIOUS': 'previous',
                 'TYPE_LAST': 'last', 'TYPE_MORE': 'more'}
    _stubModule("Plugins.Extensions.IPTVPlayer.components.ihost",
                CDisplayListItem=type('CDisplayListItem', (), itemTypes))
    _stubModule("Plugins.Extensions.IPTVPlayer.components.iptvlist", IPTVMainNavigatorList=_BaseList,
                fitPixmapInBox=lambda icon, x, y, w, h: (x, y, w, h))
    _stubModule("Plugins.Extensions.IPTVPlayer.components.cover", PicLoadPara=lambda w, h, f: (w, h))
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.listselection", isMarked=lambda item: False)
    option = types.SimpleNamespace(poster_grid=types.SimpleNamespace(value=True))
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=option))
    _stubModule("Components.config", config=cfg)
    _stubModule("Components.MultiContent", MultiContentEntryPixmapAlphaBlend=lambda **kw: ('pixmap', kw))
    _stubModule("enigma", eListboxPythonMultiContent=types.SimpleNamespace(TYPE_TEXT=TYPE_TEXT), ePicLoad=_PicLoad,
                eTimer=_Timer, gFont=lambda *a: a,
                getDesktop=lambda n: types.SimpleNamespace(size=lambda: _Size(1280, 720)),
                BT_SCALE=1, RT_HALIGN_CENTER=2, RT_VALIGN_TOP=4, RT_WRAP=8)
    path = os.path.join(ROOT, "components", "iptvpostergrid.py")
    spec = importlib.util.spec_from_file_location("iptvpostergrid_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._cfg = cfg
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _grid(pg, paths=None):
    grid = pg.IPTVPosterGridList()
    grid.instance = _Instance(grid)
    grid.onCreate()
    asked = []

    failed = []

    def posterPath(url):
        asked.append(url)
        return (paths or {}).get(url, '')

    def posterFailed(url, path):
        failed.append((url, path))
        return grid.failHandled
    grid.setPosterSource(posterPath, posterFailed)
    grid.asked = asked
    grid.failed = failed
    grid.failHandled = True
    return grid


def _paint(grid, row):
    # like eListbox: while it paints, its own index (getCurrentIndex) walks over the rows it draws
    selected = grid.instance.index
    grid.instance.index = row
    try:
        return grid.buildEntry(row)
    finally:
        grid.instance.index = selected


def _highlighted(grid, entries):
    return [e for e in entries[1:]
            if isinstance(e, tuple) and e[0] == TYPE_TEXT and len(e) > 10 and e[10] == grid.SELECTED_COLOR]


def _items(n, icons=True):
    return [_Item('Film %d' % i, ('http://x/%d.jpg' % i) if icons else '') for i in range(n)]


def test_list_has_posters(pg):
    assert pg.ListHasPosters(_items(5))
    assert not pg.ListHasPosters(_items(5, icons=False))
    # the host's logo on every category row: a menu, not posters
    assert not pg.ListHasPosters([_Item('Cat %d' % i, 'http://x/logo.png', 'category', 'category') for i in range(8)])
    # pager rows do not count against the posters
    items = _items(3) + [_Item('Next page', '', 'next', 'next'), _Item('Jump', '', 'category', 'jump')]
    assert pg.ListHasPosters(items)
    # only two different pictures: too few for a grid
    assert not pg.ListHasPosters(_items(2))
    # most rows without a picture
    assert not pg.ListHasPosters(_items(3) + _items(5, icons=False))


def test_mode_follows_list_and_option(pg):
    grid = _grid(pg)
    modes = []
    grid.onModeChanged.append(modes.append)
    grid.setList([(x,) for x in _items(30)])
    assert grid.gridMode and modes == [True]
    assert grid.instance.selectionEnabled == 0
    assert grid.l.entries == [(r,) for r in range(grid._rowCount())]
    assert 1 < grid.cols and 2 * grid.l.itemHeight <= grid.instance.h
    plain = [(x,) for x in _items(4, icons=False)]
    grid.setList(plain)
    assert not grid.gridMode and modes == [True, False]
    assert grid.instance.selectionEnabled == 1 and grid.l.entries == plain and grid.l.itemHeight == 32
    # the option off: lists with posters stay lists
    pg._cfg.plugins.iptvplayer.poster_grid.value = False
    grid.setList([(x,) for x in _items(30)])
    assert not grid.gridMode


def test_no_poster_source_no_grid(pg):
    grid = pg.IPTVPosterGridList()
    grid.instance = _Instance(grid)
    grid.onCreate()
    grid.setList([(x,) for x in _items(30)])
    assert not grid.gridMode


def test_index_mapping_and_keys(pg):
    grid = _grid(pg)
    items = _items(25)
    grid.setList([(x,) for x in items])
    cols = grid.cols
    assert 25 > cols > 2
    grid.moveToIndex(cols + 2)
    assert grid.instance.index == 1 and grid.col == 2 and grid.getCurrentIndex() == cols + 2
    assert grid.getCurrent() is items[cols + 2]
    changes = grid.changes
    grid.moveColumn(1)
    assert grid.getCurrentIndex() == cols + 3 and grid.changes == changes + 1
    # RIGHT at the end of a row goes on in the next row, LEFT at the start back to the row before
    grid.moveToIndex(cols - 1)
    grid.moveColumn(1)
    assert grid.instance.index == 1 and grid.col == 0
    grid.moveColumn(-1)
    assert grid.instance.index == 0 and grid.col == cols - 1
    # around the whole list
    grid.moveToIndex(0)
    grid.moveColumn(-1)
    assert grid.getCurrentIndex() == 24
    # DOWN into the shorter last row keeps to its last tile, DOWN on the last row goes to the top
    rows = grid._rowCount()
    grid.moveToIndex((rows - 2) * cols + cols - 1)
    grid.moveRow(1)
    assert grid.instance.index == rows - 1 and grid.getCurrentIndex() == min((rows - 1) * cols + cols - 1, 24)
    grid.moveRow(1)
    assert grid.instance.index == 0
    grid.moveRow(-1)
    assert grid.instance.index == rows - 1
    # an index past the end is the last item
    grid.moveToIndex(99)
    assert grid.getCurrentIndex() == 24
    grid.invalidateItem(cols + 1)
    assert grid.l.invalidated[-1] == 1


def test_highlight_only_on_selected_tile(pg):
    grid = _grid(pg)
    grid.setList([(x,) for x in _items(25)])
    grid.moveToIndex(grid.cols + 1)

    assert _highlighted(grid, _paint(grid, 0)) == []
    sel = _highlighted(grid, _paint(grid, 1))
    assert len(sel) == 1 and sel[0][1] == grid.tileW
    titles = [e[7] for e in grid.buildEntry(1)[1:] if isinstance(e, tuple) and e[0] == TYPE_TEXT and e[7]]
    assert titles == ['Film %d' % i for i in range(grid.cols, 2 * grid.cols)]
    # an entry of the other mode painted while switching gives an empty row, no exception
    assert grid.buildEntry(_items(1)[0]) == [None]


def test_posters_downloaded_then_decoded(pg, monkeypatch):
    paths = {}
    grid = _grid(pg, paths)
    items = _items(25)
    grid.setList([(x,) for x in items])
    grid.buildEntry(0)
    first = list(grid.asked)
    assert first == [x.iconimage for x in items[:grid.cols]]
    # not asked again on the next paint while the download runs
    grid.buildEntry(0)
    assert grid.asked == first
    # the IconMenager has it: asked again, decoded in poster size, then drawn
    paths[items[0].iconimage] = '/tmp/0.jpg'
    grid.posterChanged(items[0].iconimage)
    picload = _PicLoad.instances[-1]
    monkeypatch.setattr(os.path, 'isfile', lambda p: True)
    grid.buildEntry(0)
    assert picload.started == ['/tmp/0.jpg']
    assert picload.para == (grid.posterW, grid.posterH)
    grid.loader._decodeCallBack()
    pixmaps = [e for e in grid.buildEntry(0)[1:] if e[0] == 'pixmap']
    assert len(pixmaps) == 1 and pixmaps[0][1]['size'] == (grid.posterW, grid.posterH)


def test_loader_newest_first_and_bounded(pg, monkeypatch):
    decoded = []
    loader = pg._PosterLoader(lambda: decoded.append(1), lambda path: False)
    loader.setSize(100, 150, 4)
    picload = _PicLoad.instances[-1]
    monkeypatch.setattr(os.path, 'isfile', lambda p: True)
    assert loader.get('a') is None
    for name in 'bcd':
        loader.get(name)
    assert picload.started == ['a']
    loader._decodeCallBack()
    # the newest request comes next
    assert picload.started == ['a', 'd']
    assert loader.get('a') is not None
    assert decoded == [1]
    for i in range(100):
        loader._store('p%d' % i, None)
    assert len(loader.cache) == loader.maxCache


def test_selection_kept_over_setlist(pg):
    grid = _grid(pg)
    items = _items(25)
    grid.setList([(x,) for x in items])
    grid.moveToIndex(grid.cols + 2)
    # the same rows again (reordered list, markers): the selected item index stays
    grid.setList([(x,) for x in reversed(items)])
    assert grid.gridMode and grid.getCurrentIndex() == grid.cols + 2
    # grid -> list -> grid keeps the item index, not the row index of the other mode
    grid.setList([(x,) for x in _items(25, icons=False)])
    assert not grid.gridMode and grid.instance.index == grid.cols + 2
    grid.instance.index = 13
    grid.setList([(x,) for x in items])
    assert grid.gridMode and grid.getCurrentIndex() == 13
    # a shorter list: the last item
    grid.setList([(x,) for x in items[:5]])
    assert grid.getCurrentIndex() == 4


def test_only_pictures_of_the_list_remembered(pg, monkeypatch):
    grid = _grid(pg, {'http://x/0.jpg': '/tmp/0.jpg'})
    monkeypatch.setattr(os.path, 'isfile', lambda p: True)
    items = _items(25)
    grid.setList([(x,) for x in items])
    grid.buildEntry(0)
    assert 'http://x/0.jpg' in grid.paths and 'http://x/1.jpg' in grid.pending
    grid.setList([(x,) for x in items[1:]])
    assert 'http://x/0.jpg' not in grid.paths and 'http://x/1.jpg' in grid.pending
    grid.setList([(x,) for x in _items(25, icons=False)])
    assert not grid.paths and not grid.pending


def test_one_highlight_while_the_listbox_paints(pg):
    # the listbox's index walks over the rows while it paints: every row painted after a move once got a frame
    grid = _grid(pg)
    grid.setList([(x,) for x in _items(25)])
    grid.moveToIndex(grid.cols + 6)
    for row in range(grid._rowCount()):
        _paint(grid, row)
    grid.moveRow(-1)
    grid.moveColumn(-3)
    frames = [(row, len(_highlighted(grid, _paint(grid, row)))) for row in range(grid._rowCount())]
    assert frames == [(0, 1)] + [(row, 0) for row in range(1, grid._rowCount())]
    assert grid.getCurrentIndex() == 3
    # a move of the listbox itself (its own keys) takes the highlight along and redraws both rows
    grid.l.invalidated = []
    grid.instance.moveSelectionTo(2)
    assert grid.selRow == 2 and set(grid.l.invalidated) == {0, 2}
    assert [len(_highlighted(grid, _paint(grid, row))) for row in range(3)] == [0, 0, 1]


def test_poster_not_shown_reported(pg, monkeypatch):
    # an empty file in the icon cache: ePicLoad makes no picture of it -> reported, the grid asks again
    paths = {'http://x/0.jpg': '/tmp/0.jpg'}
    grid = _grid(pg, paths)
    grid.setList([(x,) for x in _items(25)])
    monkeypatch.setattr(os.path, 'isfile', lambda p: True)
    picload = _PicLoad.instances[-1]
    picload.broken = True
    grid.buildEntry(0)
    grid.loader._decodeCallBack()
    assert grid.failed == [('http://x/0.jpg', '/tmp/0.jpg')]
    assert 'http://x/0.jpg' not in grid.paths and '/tmp/0.jpg' not in grid.loader.cache
    # its new download later is still drawn (the url is no longer in paths / pending), a foreign one is not
    starts = grid.redrawTimer.starts
    grid.posterChanged('http://x/0.jpg')
    assert grid.redrawTimer.starts == starts + 1
    grid.posterChanged('http://other/list.jpg')
    assert grid.redrawTimer.starts == starts + 1
    # now the red X (the IconMenager marked it failed)
    paths['http://x/0.jpg'] = '/icons/CoverError.png'
    picload.broken = False
    grid.buildEntry(0)
    assert grid.paths['http://x/0.jpg'] == '/icons/CoverError.png'
    # a file nobody can drop (a local picture) stays the type icon, no new try on every paint
    grid.failHandled = False
    picload.broken = True
    grid.loader._decodeCallBack()
    grid.loader.get('/tmp/local.jpg')
    grid.paths['file:///tmp/local.jpg'] = '/tmp/local.jpg'
    grid.loader._decodeCallBack()
    assert grid.loader.cache['/tmp/local.jpg'] is None


def _png(width, height):
    ihdr = b'IHDR' + struct.pack('>II', width, height) + b'\x08\x02\x00\x00\x00'
    return b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + ihdr


def _jpeg(width, height):
    # SOI, an APP1 (EXIF) segment, a DHT (0xC4 - no size in it), then SOF2 (progressive) with the size
    app1 = b'\xff\xe1' + struct.pack('>H', 2 + 10) + b'Exif\x00\x00' + b'\x00' * 4
    dht = b'\xff\xc4' + struct.pack('>H', 2 + 3) + b'\x00\x01\x02'
    sof = b'\xff\xc2' + struct.pack('>HBHH', 11, 8, height, width) + b'\x01\x01\x11\x00'
    return b'\xff\xd8' + app1 + dht + sof + b'\xff\xd9'


def test_picture_size_from_header(pg, tmp_path):
    files = {'a.png': (_png(640, 360), (640, 360)), 'b.jpg': (_jpeg(300, 450), (300, 450)),
             'c.gif': (b'GIF89a' + struct.pack('<HH', 120, 90) + b'\x00' * 8, (120, 90)),
             'd.webp': (b'RIFF\x00\x00\x00\x00WEBPVP8 ', None), 'e.jpg': (b'', None)}
    for name, (data, size) in files.items():
        path = tmp_path / name
        path.write_bytes(data)
        assert pg.PictureSize(str(path)) == size, name
    assert pg.PictureSize(str(tmp_path / 'missing.jpg')) is None
    assert pg.FitSizeInBox(640, 360, 10, 20, 144, 216) == (10, 20 + (216 - 81) // 2, 144, 81)


def _landscapeList(pg, tmp_path, n=25, size=(480, 360)):
    paths = {}
    for i in range(n):
        path = tmp_path / ('%d.jpg' % i)
        path.write_bytes(_jpeg(*size))
        paths['http://x/%d.jpg' % i] = str(path)
    grid = _grid(pg, paths)
    grid.setPosterSource(grid.posterPath, grid.posterFailed, '/icons/CoverError.png')
    return grid


def test_landscape_pictures_give_landscape_tiles(pg, tmp_path):
    grid = _landscapeList(pg, tmp_path)
    items = _items(25)
    grid.setList([(x,) for x in items])
    portrait = (grid.cols, grid.posterW, grid.posterH)
    assert grid.posterW < grid.posterH and grid.l.itemHeight == grid.instance.h // 2
    grid.moveToIndex(7)
    # the first pictures on disk decide; the new layout comes after the paint, not during it
    _paint(grid, 0)
    assert grid.landscape and grid.relayoutPending and grid.cols == portrait[0]
    grid._redraw()
    assert not grid.relayoutPending and grid.posterW > grid.posterH
    assert grid.l.itemHeight == grid.instance.h // 3 and grid.cols < portrait[0]
    assert grid.posterW * grid.posterH > 2 * portrait[1] * portrait[2] // 3
    # the same item stays selected
    assert grid.getCurrentIndex() == 7
    # the next page of the same host starts with landscape tiles at once
    grid.setList([(x,) for x in _items(25)[3:]])
    assert grid.landscape and grid.l.itemHeight == grid.instance.h // 3


def test_portrait_pictures_and_the_red_x_keep_posters(pg, tmp_path):
    grid = _landscapeList(pg, tmp_path, size=(300, 450))
    grid.paths = {}
    # the red X has no say (it is a portrait picture itself)
    grid.setList([(x,) for x in _items(25)])
    _paint(grid, 0)
    assert grid.shapeDecided and not grid.landscape and not grid.relayoutPending
    assert grid._voteShape('http://x/err', '/icons/CoverError.png') is None


def test_markers_on_the_picture_from_its_file(pg, tmp_path, monkeypatch):
    grid = _landscapeList(pg, tmp_path, size=(640, 360))
    grid.SHAPE_VOTES = 99  # keep the portrait boxes: a 16:9 picture in a 2:3 box
    grid.watchedBadgePIX = _Pixmap(32, 32)
    items = _items(25)
    items[0].isWatched = True
    grid.setList([(x,) for x in items])
    grid.buildEntry(0)
    grid.loader._decodeCallBack()
    pixmaps = [e[1] for e in grid.buildEntry(0)[1:] if e[0] == 'pixmap']
    # ePicLoad padded the picture to the whole box: drawn there, the badge sits in the 16:9 picture's corner
    assert pixmaps[0]['size'] == (grid.posterW, grid.posterH)
    pictureH = grid.posterW * 360 // 640
    pictureBottom = grid.pad + (grid.posterH - pictureH) // 2 + pictureH
    badge = pixmaps[1]
    assert badge['pos'][1] + badge['size'][1] == pictureBottom - 2


def test_markers_same_size_on_flat_and_high_logos(pg, tmp_path, monkeypatch):
    # hostxxx site logos: flat ones (420 x 100) and high ones (420 x 300) - the star is as big on both
    grid = _landscapeList(pg, tmp_path, size=(420, 100))
    (tmp_path / '1.jpg').write_bytes(_jpeg(420, 300))
    grid.SHAPE_VOTES = 99
    items = _items(25)
    items[0].isFavourite = items[1].isFavourite = True
    star = _Pixmap(32, 32)
    grid._getRowMarkers = lambda item: [star] if getattr(item, 'isFavourite', False) else []
    grid.setList([(x,) for x in items])
    grid.buildEntry(0)
    grid.loader._decodeCallBack()
    grid.loader._decodeCallBack()
    stars = [e[1] for e in grid.buildEntry(0)[1:] if e[0] == 'pixmap' and e[1]['png'] is star]
    assert len(stars) == 2 and stars[0]['size'] == stars[1]['size']
    assert stars[0]['size'][1] == max(min(grid.posterW, grid.posterH) // 4, 14)
