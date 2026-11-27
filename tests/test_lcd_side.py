# Offline test of the LCD layout "side" of the external player (components/iptvlcd.py): Enigma2 is stubbed, the
# geometry and the skin XML of the colour summary are the real ones.
import importlib.util
import os
import sys
import types
import xml.etree.ElementTree as ET

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Value(object):
    def __init__(self, value):
        self.value = value


class _Settings(object):
    pass


class _Any(object):
    # a class or function of Enigma2 that the layout code only names
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return _Any()

    def __getattr__(self, name):
        return _Any()


def _noDisplay(*args):
    raise RuntimeError('no display outside enigma2')


@pytest.fixture
def lcd():
    settings = _Settings()
    config = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=settings))
    saved = {}

    def stub(name, **attrs):
        saved[name] = sys.modules.get(name)
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod

    base = "Plugins.Extensions.IPTVPlayer"
    for name in ("Plugins", "Plugins.Extensions", base, base + ".components", base + ".tools", "Components",
                 "Components.Sources", "Screens", "Tools"):
        stub(name)
    stub(base + ".components.cover", Cover=_Any)
    stub(base + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, eConnectCallback=_Any(),
         StripColorCodes=lambda t: t, GetTmpDir=lambda *a: '/tmp/', mkdirs=lambda *a: True)
    stub(base + ".components.iptvplayerinit", TranslateTXT=lambda t: t)
    stub("enigma", getDesktop=_noDisplay, eTimer=_Any, eLabel=_Any(), gFont=_Any, ePoint=_Any, eSize=_Any)
    stub("Screens.Screen", Screen=object)
    stub("Components.Label", Label=_Any)
    stub("Components.Pixmap", Pixmap=_Any)
    stub("Tools.LoadPixmap", LoadPixmap=_Any())
    stub("Components.config", config=config)
    stub("Components.Sources.StaticText", StaticText=_Any)
    stub("Components.Sources.Progress", Progress=_Any)
    stub("skin", fonts={})
    spec = importlib.util.spec_from_file_location("iptvlcd_test", os.path.join(ROOT, "components", "iptvlcd.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.test_settings = settings
    yield module
    for name, mod in saved.items():
        if mod is None:
            del sys.modules[name]
        else:
            sys.modules[name] = mod


def _set(lcd, **values):
    for name, value in values.items():
        setattr(lcd.test_settings, name, _Value(value))


def _summary(lcd, w, h):
    # the colour summary of the player without Enigma2: the size of the display and a parent with playback
    cls = lcd.IPTVExtMoviePlayerColorSummary
    cls.w, cls.h = w, h
    summary = cls.__new__(cls)
    summary.lcdParent = types.SimpleNamespace(playback={})
    return summary


def _inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1] and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


def _overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


@pytest.mark.parametrize("size", [(800, 480), (480, 320), (400, 240), (320, 240)])
def test_full_width_title_geometry(lcd, size):
    w, h = size
    cls = lcd.IPTVExtMoviePlayerColorSummary
    opts = lcd.lcdSideOptions([('clock', 100), ('end', 100), ('remaining', 100)], True)
    L = cls.lcdGeometry(w, h, 'large', 'side', True, None, 70, 100, opts)
    assert L['side']
    screen = (0, 0, w, h)
    cover, column, title, line = L['coverRect'], L['sideRect'], L['rectBeside'], L['sepRect']
    for rect in (cover, column, title, line):
        assert _inside(rect, screen), rect
    # the title line has the whole width, the line lies between the picture / column and the title
    assert title[0] == cover[0] and title[2] == L['cw']
    assert line[2] == L['cw'] and cover[1] + cover[3] < line[1] < title[1]
    assert column[1] + column[3] < line[1]
    # the picture and the column side by side, the column between the minimum and the maximum width
    assert not _overlap(cover, column) and cover[3] == column[3]
    assert L['cw'] * lcd.LCD_SIDE_MIN_RIGHT_PERCENT // 100 <= column[2] <= L['cw'] * lcd.LCD_SIDE_MAX_RIGHT_PERCENT // 100
    assert title[1] + title[3] <= L['barY']
    assert L['besideOneLine'] and L['besideAlign'] == 'left'


def test_picture_title_keeps_the_old_layout(lcd):
    cls = lcd.IPTVExtMoviePlayerColorSummary
    _set(lcd, lcd_side_title='picture')
    opts = lcd.lcdSideOptions([('clock', 100), ('end', 100), ('remaining', 100), ('percent', 100)], True)
    L = cls.lcdGeometry(800, 480, 'large', 'side', True, None, 70, 100, opts)
    cover, title = L['coverRect'], L['rectBeside']
    # a 16:9 picture with the title line below it (as wide as the picture, centred), no line above the title
    assert abs(cover[2] * 9 - cover[3] * 16) <= 16
    assert title[2] == cover[2] and title[1] > cover[1] + cover[3]
    assert L['besideAlign'] == 'center' and L['sepRect'] is None
    assert L['sideRect'][3] > cover[3]


def test_narrow_display_falls_back(lcd):
    cls = lcd.IPTVExtMoviePlayerColorSummary
    L = cls.lcdGeometry(240, 160, 'large', 'side', True, None, 70, 100, lcd.lcdSideOptions([('clock', 100)], True))
    assert not L['side']


def _rows_xml(lcd, w, h, rows, **settings):
    _set(lcd, **settings)
    summary = _summary(lcd, w, h)
    opts = lcd.lcdSideOptions(rows, True)
    L = summary.lcdGeometry(w, h, 'large', 'side', True, None, 70, 100, opts)
    xml = summary.sideRowsXml(L, opts, True)
    return L, opts, ET.fromstring('<screen>%s</screen>' % xml)


def _font(element):
    return int(element.get('font').split(';')[1])


def _box(element):
    x, y = [int(v) for v in element.get('position').split(',')]
    w, h = [int(v) for v in element.get('size').split(',')]
    return (x, y, w, h)


@pytest.mark.parametrize("skinFonts,expected", [((), 'Regular'), (('VFD',), 'VFD'), (('FdLcD',), 'FdLcD'),
                                                 (('FdLcD', 'SemiboldLCD'), 'SemiboldLCD')])
def test_rows_fit_the_column(lcd, skinFonts, expected):
    sys.modules['skin'].fonts = dict((name, None) for name in skinFonts)
    L, opts, root = _rows_xml(lcd, 800, 480, [('clock', 100), ('end', 100), ('remaining', 100)])
    values = root.findall('widget')
    assert len(values) == 3
    assert values[0].get('font').startswith(expected + ';')
    if expected == 'FdLcD':
        # the wide openATV font keeps its own character width
        assert [charEm for kind, chars, charEm, pct in opts['rows']] == [0.54, 0.54, 0.54]
    for (kind, chars, charEm, pct), value in zip(opts['rows'], values):
        box = _box(value)
        assert _inside(box, L['sideRect'])
        assert chars * charEm * _font(value) <= box[2] + 1
        assert value.get('halign') == 'right' and value.get('valign') == 'center'
        assert value.get('backgroundColor') is None
    # two lines between three rows, no labels
    assert len([e for e in root.findall('eLabel') if e.get('text') is None]) == 2
    assert not [e for e in root.findall('eLabel') if e.get('text')]


def test_font_loaded_by_the_display_skin(lcd):
    # openATV: <font filename="nmsbd.ttf" name="FdLcD"/> is a font face (enigma.getFontFaces), not a skin.fonts alias
    sys.modules['enigma'].getFontFaces = lambda: ['Regular', 'FdLcD']
    try:
        assert lcd.lcdSideOptions([('clock', 100)], True)['font'] == 'FdLcD'
    finally:
        del sys.modules['enigma'].getFontFaces


def test_labels_alignment_lines_and_sizes(lcd):
    rows = [('clock', 100), ('end', 50), ('remaining', 100), ('percent', 100)]
    L, opts, root = _rows_xml(lcd, 800, 480, rows, lcd_side_labels=True, lcd_side_align='center', lcd_side_lines=False)
    labels = [e for e in root.findall('eLabel') if e.get('text')]
    assert [e.get('text') for e in labels] == ['TIME', 'ENDS', 'REMAINING', 'DONE']
    assert not [e for e in root.findall('eLabel') if e.get('text') is None]
    values = root.findall('widget')
    assert all(e.get('halign') == 'center' for e in values + labels)
    assert all(e.get('valign') == 'top' for e in values)
    # row 2 at 50 %: smaller than row 1 (same characters)
    assert _font(values[1]) < _font(values[0])
    for label, value in zip(labels, values):
        assert _font(label) < _font(value)
        assert _box(label)[1] + _box(label)[3] == _box(value)[1]


def test_larger_rows_widen_the_column(lcd):
    _L, _o, _r = _rows_xml(lcd, 800, 480, [('clock', 100), ('end', 100), ('remaining', 100)])
    L2, _o2, _r2 = _rows_xml(lcd, 800, 480, [('clock', 100), ('end', 100), ('remaining', 150)])
    assert L2['sideRect'][2] >= _L['sideRect'][2]


def test_skin_cover_xml(lcd):
    _set(lcd, lcd_cover=True, lcd_cover_size='side', lcd_long_titles='pages', lcd_side_row4='percent')
    summary = _summary(lcd, 800, 480)
    summary.computeLayout(True)
    root = ET.fromstring(summary.skinCover)
    sources = [e.get('source') for e in root.findall('widget')]
    assert 'global.CurrentTime' in sources and 'lcdEndTime' in sources and 'parent.lcdPercent' in sources
    assert summary.sideMode
    # 4 rows: 3 lines between them, 1 line above the title
    lines = [e for e in root.findall('eLabel') if e.get('text') is None]
    assert len(lines) == 4
    ET.fromstring(summary.skinPlain)
