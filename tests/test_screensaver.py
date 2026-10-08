# Offline tests for the key hook / timer logic of IPTVPlayer/components/iptvscreensaver.py
# (IPTVIdleScreenSaver, shared by the audio and the menu screensaver). Enigma2 is replaced by stubs.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class Timer(object):
    def __init__(self):
        self.timeout = object()
        self.ms = None

    def start(self, ms, singleShot=False):
        self.ms = ms

    def stop(self):
        self.ms = None


class ActionMap(object):
    hooks = []

    @classmethod
    def getInstance(cls):
        return cls

    @classmethod
    def bindAction(cls, context, prio, fnc):
        cls.hooks.append(fnc)

    @classmethod
    def unbindAction(cls, context, fnc):
        cls.hooks.remove(fnc)


@pytest.fixture
def saver(monkeypatch):
    enigma = types.ModuleType("enigma")
    enigma.eTimer, enigma.eActionMap = Timer, ActionMap
    enigma.getDesktop = enigma.ePoint = None
    standby = types.ModuleType("Screens.Standby")
    standby.inStandby = None
    screens = types.ModuleType("Screens")
    screens.Standby = standby
    screen = types.ModuleType("Screens.Screen")
    screen.Screen = object
    label = types.ModuleType("Components.Label")
    label.Label = object
    configMod = types.ModuleType("Components.config")
    delay = types.SimpleNamespace(value="60")
    configMod.config = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
        screensaver_audio=delay, screensaver_menu=delay)))
    tools = types.ModuleType("Plugins.Extensions.IPTVPlayer.tools.iptvtools")
    tools.printDBG = tools.printExc = lambda *args: None
    tools.eConnectCallback = lambda signal, fnc: object()
    cover = types.ModuleType("Plugins.Extensions.IPTVPlayer.components.cover")
    cover.Cover = object
    for name in ("Components", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                 "Plugins.Extensions.IPTVPlayer.tools", "Plugins.Extensions.IPTVPlayer.components"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    for name, module in (("enigma", enigma), ("Screens", screens), ("Screens.Standby", standby), ("Screens.Screen", screen),
                         ("Components.Label", label), ("Components.config", configMod),
                         ("Plugins.Extensions.IPTVPlayer.tools.iptvtools", tools),
                         ("Plugins.Extensions.IPTVPlayer.components.cover", cover)):
        monkeypatch.setitem(sys.modules, name, module)
    ActionMap.hooks = []
    spec = importlib.util.spec_from_file_location("iptvscreensaver_under_test", os.path.join(ROOT, "components", "iptvscreensaver.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Saver(module.IPTVIdleScreenSaver):
        active = False

        def isActive(self):
            return self.active

        def activate(self):
            self.active = True

        def deactivate(self):
            self.active = False
            self.restartTimer()

    s = Saver(None, delay)
    s.standby, s.delaySetting = standby, delay
    return s


def test_timer_starts_and_key_restarts(saver):
    saver.start()
    assert ActionMap.hooks == [saver.keyHook] and saver.timer.ms == 60000
    saver.timer.ms = None
    assert saver.keyHook(1, 0) == 0
    assert saver.timer.ms == 60000


def test_first_key_only_ends_it(saver):
    saver.start()
    saver.timeout()
    assert saver.isActive()
    assert saver.keyHook(1, 0) == 1 and not saver.isActive()
    assert saver.keyHook(1, 2) == 1  # repeat of the same key
    assert saver.keyHook(1, 1) == 1  # its break
    assert saver.keyHook(2, 0) == 0  # the next key works


def test_switched_on_later_without_restart(saver):
    saver.delaySetting.value = "0"
    saver.start()
    assert saver.timer.ms is None and ActionMap.hooks
    saver.delaySetting.value = "120"
    saver.keyHook(1, 0)
    assert saver.timer.ms == 120000


def test_standby_key_never_swallowed(saver):
    saver.start()
    saver.timeout()
    saver.standby.inStandby = object()
    assert saver.keyHook(116, 0) == 0 and not saver.isActive()
    saver.timeout()
    assert not saver.isActive()


def test_stop_unbinds(saver):
    saver.start()
    saver.close()
    assert ActionMap.hooks == [] and saver.timer.ms is None and saver.timer_conn is None
