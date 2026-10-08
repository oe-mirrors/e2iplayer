# Offline tests for IPTVPlayer/components/iptvhostpin.py: the PIN protection every host has, and the
# takeover of hostxxx's old PIN settings. Components.config is replaced by a small copy of the image's
# ConfigSubsection (stored values are loaded when an element is added).
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
HOSTS = ('xxx', 'ted', 'youtube')


class ConfigElement(object):
    def __init__(self, default):
        self.default = default
        self.value = default

    def load(self, stored):
        self.value = stored

    def save(self):
        pass


class ConfigYesNo(ConfigElement):
    def load(self, stored):
        # Enigma2's ConfigBoolean: any case of these words means True
        self.value = stored.lower() in ('1', 'enable', 'enabled', 'on', 'true', 'yes')


class ConfigText(ConfigElement):
    def __init__(self, default="", fixed_size=True):
        ConfigElement.__init__(self, default)


class ConfigSelection(ConfigElement):
    def __init__(self, default=None, choices=None):
        ConfigElement.__init__(self, default)


class ConfigSubsection(object):
    def __init__(self, stored):
        object.__setattr__(self, 'content', types.SimpleNamespace(stored_values=dict(stored)))

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        stored = self.content.stored_values.get(name)
        if stored is not None:
            value.load(stored)


@pytest.fixture
def hostpin(monkeypatch):
    def load(stored=None, remember=True):
        section = ConfigSubsection(stored or {})
        section.pin = ConfigText("1111")
        section.host_pin_remember = ConfigYesNo(remember)
        for hostName in HOSTS:
            # the host on/off entries of the host list (iptvconfig.py)
            setattr(section, 'host' + hostName, ConfigYesNo(True))
        configMod = types.ModuleType("Components.config")
        configMod.config = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=section))
        configMod.configfile = types.SimpleNamespace(save=lambda: None)
        configMod.getConfigListEntry = lambda *args: args
        configMod.ConfigSelection, configMod.ConfigText, configMod.ConfigYesNo = ConfigSelection, ConfigText, ConfigYesNo
        tools = types.ModuleType("Plugins.Extensions.IPTVPlayer.tools.iptvtools")
        tools.printDBG = tools.printExc = lambda *args: None
        init = types.ModuleType("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit")
        init.TranslateTXT = lambda text: text
        box = types.ModuleType("Screens.MessageBox")
        box.MessageBox = types.SimpleNamespace(TYPE_INFO=0)
        pinWidget = types.ModuleType("Plugins.Extensions.IPTVPlayer.components.iptvpin")
        pinWidget.IPTVPinWidget = object
        for name in ("Components", "Screens", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                     "Plugins.Extensions.IPTVPlayer.tools", "Plugins.Extensions.IPTVPlayer.components"):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        for name, module in (("Components.config", configMod), ("Screens.MessageBox", box),
                             ("Plugins.Extensions.IPTVPlayer.tools.iptvtools", tools),
                             ("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit", init),
                             ("Plugins.Extensions.IPTVPlayer.components.iptvpin", pinWidget)):
            monkeypatch.setitem(sys.modules, name, module)
        spec = importlib.util.spec_from_file_location("iptvhostpin_under_test", os.path.join(ROOT, "components", "iptvhostpin.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def test_other_hosts_unprotected_by_default(hostpin):
    pin = hostpin()
    assert not pin.IsHostPinProtected('youtube')
    assert pin.GetHostPinCode('youtube') == ''
    assert pin.GetExpectedHostPin('youtube') == '1111'
    assert not pin.IsHostPinProtected('')


def test_unknown_host_gets_no_settings(hostpin):
    pin = hostpin({'pinhost_gone': 'True'})
    assert not pin.IsHostPinProtected('gone')
    assert not hasattr(sys.modules["Components.config"].config.plugins.iptvplayer, 'pinhost_gone')


def test_xxx_protected_like_before(hostpin):
    # hostxxx was protected by default; switched off before -> stays off
    assert hostpin().IsHostPinProtected('xxx')
    assert not hostpin({'xxxwymagajpin': 'False'}).IsHostPinProtected('xxx')
    assert not hostpin({'xxxwymagajpin': 'false'}).IsHostPinProtected('xxx')


def test_xxx_own_pin_taken_over(hostpin):
    pin = hostpin({'xxxownpin': 'True', 'xxxpincode': '4321'})
    assert pin.GetHostPinCode('xxx') == '4321'
    assert pin.GetExpectedHostPin('xxx') == '4321'
    # an own pin "0000" (the old default) was never written to the settings file
    assert hostpin({'xxxownpin': 'true'}).GetHostPinCode('xxx') == '0000'
    assert hostpin({'xxxpincode': '4321'}).GetHostPinCode('xxx') == ''


def test_new_settings_win_over_legacy(hostpin):
    pin = hostpin({'xxxwymagajpin': 'True', 'pinhost_xxx': 'False'})
    assert not pin.IsHostPinProtected('xxx')


def test_own_pin_needs_four_digits(hostpin):
    pin = hostpin({'pinhost_ted': 'True', 'pinhostown_ted': 'True', 'pinhostcode_ted': '12'})
    assert pin.IsHostPinProtected('ted')
    assert pin.GetExpectedHostPin('ted') == '1111'


def test_unlock_until_cleared(hostpin):
    pin = hostpin({'pinhost_ted': 'True'})
    assert pin.HostNeedsPin('ted')
    pin.SetHostUnlocked('ted')
    assert not pin.HostNeedsPin('ted')
    pin.ClearUnlockedHosts()
    assert pin.HostNeedsPin('ted')


def test_host_name_of(hostpin):
    pin = hostpin()
    host = type('IPTVHost', (), {'__module__': 'Plugins.Extensions.IPTVPlayer.hosts.hostyoutube'})()
    assert pin.HostNameOf(host) == 'youtube'
    assert pin.HostNameOf(object()) == ''


def test_config_rows(hostpin):
    pin = hostpin()
    assert len(pin.GetHostPinConfigList('ted')) == 1
    pin = hostpin({'pinhost_ted': 'True'})
    assert len(pin.GetHostPinConfigList('ted')) == 2
    pin = hostpin({'pinhost_ted': 'True', 'pinhostown_ted': 'True'})
    rows = pin.GetHostPinConfigList('ted')
    assert len(rows) == 3 and rows[2][1].iptv_host_action == pin.HOST_PIN_ACTION
    assert rows[2][0].strip() == "Set own pin"


class Session(object):
    # answers every dialog at once: the PIN dialog with self.pin, a message box with None
    def __init__(self, pin):
        self.pin = pin
        self.messages = 0

    def openWithCallback(self, callback, screen, *args, **kwargs):
        if screen is object:
            callback(self.pin)
        else:
            self.messages += 1
            callback(None)


@pytest.mark.parametrize("remember", [True, False])
def test_ask_host_pin(hostpin, remember):
    pin = hostpin({'pinhost_ted': 'True'}, remember=remember)
    calls = []
    pin.AskHostPin(Session('1111'), 'ted', lambda: calls.append(pin.HostNeedsPin('ted')))
    # unlocked while the opening runs, afterwards only when remembered
    assert calls == [False]
    assert pin.HostNeedsPin('ted') is not remember


def test_ask_host_pin_wrong(hostpin):
    pin = hostpin({'pinhost_ted': 'True'})
    calls = []
    session = Session('9999')
    pin.AskHostPin(session, 'ted', lambda: calls.append('ok'), onWrong=lambda: calls.append('wrong'))
    assert calls == ['wrong'] and session.messages == 1 and pin.HostNeedsPin('ted')
