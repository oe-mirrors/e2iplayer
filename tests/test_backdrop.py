# -*- coding: utf-8 -*-
# components/iptvbackdrop.py: where the backdrop url comes from and how the picture is prepared
import importlib.util
import os
import sys
import types

import pytest

# Pillow is on every box; a PC / CI without it skips the tests that draw pictures
needsPil = pytest.mark.skipif(importlib.util.find_spec("PIL") is None, reason="Pillow not installed")

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


@pytest.fixture
def backdrop(monkeypatch, tmp_path):
    setting = types.SimpleNamespace(value="online")
    pause = types.SimpleNamespace(value=False)
    configMod = types.ModuleType("Components.config")
    configMod.config = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(backdrop=setting, backdrop_pause=pause)))
    screen = types.ModuleType("Screens.Screen")
    screen.Screen = object
    enigma = types.ModuleType("enigma")
    enigma.getDesktop = None
    tools = types.ModuleType("Plugins.Extensions.IPTVPlayer.tools.iptvtools")
    tools.printDBG = tools.printExc = lambda *args: None
    tools.GetCacheSubDir = lambda dirName, fileName='': os.path.join(str(tmp_path), fileName)
    cover = types.ModuleType("Plugins.Extensions.IPTVPlayer.components.cover")
    cover.Cover = object
    calls = []
    moviemeta = types.ModuleType("Plugins.Extensions.IPTVPlayer.libs.moviemeta")
    moviemeta.queries = {}

    def getInfoQuery(cItem):
        return moviemeta.queries.get(cItem.get('url'))

    def getImage169(*args):
        calls.append(args)
        return 'https://img/backdrop.jpg'
    # what the INFO page's lookup found: {(type, title, year): meta}
    moviemeta.found = {}

    def getMeta(mediaType, title, year='', skip=(), maxYearDiff=None):
        return moviemeta.found.get((mediaType, title, year), {})
    moviemeta.getInfoQuery, moviemeta.getImage169, moviemeta.getMeta = getInfoQuery, getImage169, getMeta
    for name in ("Components", "Screens", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                 "Plugins.Extensions.IPTVPlayer.tools", "Plugins.Extensions.IPTVPlayer.components", "Plugins.Extensions.IPTVPlayer.libs"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    for name, module in (("Components.config", configMod), ("Screens.Screen", screen), ("enigma", enigma),
                         ("Plugins.Extensions.IPTVPlayer.tools.iptvtools", tools),
                         ("Plugins.Extensions.IPTVPlayer.components.cover", cover),
                         ("Plugins.Extensions.IPTVPlayer.libs.moviemeta", moviemeta)):
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("iptvbackdrop_under_test", os.path.join(ROOT, "components", "iptvbackdrop.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.setting, module.pause, module.calls, module.moviemeta, module.tmp = setting, pause, calls, moviemeta, tmp_path
    return module


def test_the_hosts_backdrop_comes_first(backdrop):
    # the host's INFO page, then the list item; no lookup then
    assert backdrop.backdropUrl({'url': 'a', 'backdrop': 'https://host/item.jpg'}, [{'backdrop': 'https://host/info.jpg'}]) == 'https://host/info.jpg'
    assert backdrop.backdropUrl({'url': 'a', 'backdrop': 'https://host/item.jpg'}, [{'title': 'x'}]) == 'https://host/item.jpg'
    assert backdrop.calls == []
    # not a picture url
    backdrop.setting.value = 'host'
    assert backdrop.backdropUrl({'url': 'a', 'backdrop': 'item.jpg'}, []) == ''


def test_online_only_by_the_imdb_id_of_the_info_pages_title(backdrop):
    # the INFO page found the title by title + year: its IMDb id gives the picture, no search by title
    backdrop.moviemeta.queries['a'] = {'type': 'movie', 'title': 'Forgotten Island', 'year': '2026'}
    backdrop.moviemeta.found[('movie', 'Forgotten Island', '2026')] = {'info': {'year': '2026'}, 'imdb_id': 'tt36583977'}
    assert backdrop.backdropUrl({'url': 'a'}, []) == 'https://img/backdrop.jpg'
    assert backdrop.calls[-1] == ('movie', '', '', '', '', 'tt36583977', 1280)
    # the INFO page asked by IMDb id
    backdrop.moviemeta.queries['b'] = {'type': 'tv', 'title': '', 'year': '', 'imdb': 'tt123'}
    backdrop.backdropUrl({'url': 'b'}, [])
    assert backdrop.calls[-1] == ('tv', '', '', '', '', 'tt123', 1280)
    # the host's own IMDb id of the item
    backdrop.backdropUrl({'url': 'c', 'meta_type': 'movie', 'meta_imdb': 'tt0113277'}, [])
    assert backdrop.calls[-1] == ('movie', '', '', '', '', 'tt0113277', 1280)


@pytest.mark.parametrize("query,found", [
    # forum 25.11.: "The Substitute" without a year - a namesake series' picture
    ({'type': 'tv', 'title': 'The Substitute', 'year': ''}, {'info': {'year': '2019'}, 'imdb_id': 'tt1'}),
    # the found title is of another year
    ({'type': 'movie', 'title': 'Heat', 'year': '2013'}, {'info': {'year': '1995'}, 'imdb_id': 'tt0113277'}),
    # a service that names no IMDb id, or nothing found
    ({'type': 'movie', 'title': 'Heat', 'year': '1995'}, {'info': {'year': '1995'}, 'imdb_id': ''}),
    ({'type': 'movie', 'title': 'Heat', 'year': '1995'}, {}),
])
def test_no_backdrop_without_a_sure_match(backdrop, query, found):
    backdrop.moviemeta.queries['a'] = query
    backdrop.moviemeta.found[(query['type'], query['title'], query['year'])] = found
    assert backdrop.backdropUrl({'url': 'a'}, []) == ''
    assert backdrop.calls == []


def test_year_off_by_one_still_matches_and_no_info_lookup_means_no_backdrop(backdrop):
    backdrop.moviemeta.queries['a'] = {'type': 'movie', 'title': 'Heat', 'year': '1996'}
    backdrop.moviemeta.found[('movie', 'Heat', '1996')] = {'info': {'year': '1995'}, 'imdb_id': 'tt0113277'}
    assert backdrop.backdropUrl({'url': 'a'}, []) == 'https://img/backdrop.jpg'
    # the INFO page found nothing: the host's meta_* fields alone are no reason for a search
    calls = len(backdrop.calls)
    assert backdrop.backdropUrl({'url': 'd', 'meta_type': 'movie', 'meta_title': 'Heat', 'meta_year': '1995'}, []) == ''
    assert len(backdrop.calls) == calls


def test_settings(backdrop):
    backdrop.moviemeta.queries['a'] = {'type': 'movie', 'title': 'X', 'year': ''}
    backdrop.setting.value = 'host'
    assert backdrop.backdropUrl({'url': 'a'}, []) == ''
    backdrop.setting.value = 'off'
    assert backdrop.backdropUrl({'url': 'a', 'backdrop': 'https://host/item.jpg'}, []) == ''
    assert backdrop.calls == []
    backdrop.pause.value = True
    assert backdrop.backdropOnPause() is False
    backdrop.setting.value = 'online'
    assert backdrop.backdropOnPause() is True


@needsPil
def test_cut_and_dim(backdrop):
    from PIL import Image
    source = str(backdrop.tmp / 'src.jpg')
    target = str(backdrop.tmp / 'out.jpg')
    # a 4:3 white picture: cut to 16:9 (no black bars) and darkened
    Image.new('RGB', (800, 600), (255, 255, 255)).save(source)
    assert backdrop.cutAndDim(source, target, 320, 180) is True
    with Image.open(target) as img:
        assert img.size == (320, 180)
        assert abs(img.getpixel((160, 90))[0] - 255 * backdrop.BACKDROP_BRIGHTNESS) <= 3
    assert not os.path.exists(target + '.part')


def test_prepared_picture_is_reused_and_old_ones_go(backdrop, monkeypatch):
    target = backdrop.backdropPath('https://img/a.jpg', 1280, 720)
    open(target, 'w').close()
    assert backdrop.makeBackdropFile(target, 'https://img/a.jpg', 1280, 720) == target
    for idx in range(backdrop.BACKDROP_KEEP + 3):
        path = backdrop.backdropPath('https://img/%d.jpg' % idx, 1280, 720)
        open(path, 'w').close()
        os.utime(path, (idx, idx))
    backdrop._prune(backdrop.BACKDROP_KEEP)
    assert len([n for n in os.listdir(str(backdrop.tmp)) if n.startswith('backdrop_')]) == backdrop.BACKDROP_KEEP
