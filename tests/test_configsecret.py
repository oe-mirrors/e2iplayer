# Offline tests for IPTVPlayer/components/configsecret.py: what a config list shows for passwords / API keys
# and logins. Components.config is replaced by a small copy of the image's ConfigText / ConfigPassword.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class ConfigText(object):
    """the parts of Enigma2's ConfigText the display uses (OpenPLi: (type, text, marks); read-only OpenATV: 2 items)"""
    readOnly = False

    def __init__(self, default="", fixed_size=True, visible_width=False):
        self.text = default
        self.marked_pos = 0

    @property
    def value(self):
        return self.text

    @value.setter
    def value(self, val):
        self.text = val

    def getMulti(self, selected):
        if self.readOnly:
            return ("text", self.text)
        return ("mtext"[1 - selected:], self.text + " ", [self.marked_pos])


class ConfigPassword(ConfigText):
    def __init__(self, default="", fixed_size=False, visible_width=False, censor="*"):
        ConfigText.__init__(self, default, fixed_size, visible_width)
        self.hidden = True

    def getMulti(self, selected):
        mtext, text, mark = ConfigText.getMulti(self, selected)
        return mtext, ("*" * len(text)) if self.hidden else text, mark


@pytest.fixture
def secret():
    saved = dict(sys.modules)
    mod = types.ModuleType("Components.config")
    mod.ConfigText, mod.ConfigPassword = ConfigText, ConfigPassword
    sys.modules["Components"] = types.ModuleType("Components")
    sys.modules["Components.config"] = mod
    spec = importlib.util.spec_from_file_location("configsecret_under_test", os.path.join(ROOT, "components", "configsecret.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def test_secret_never_shown(secret):
    s = secret.ConfigSecret(default="", fixed_size=False)
    assert s.getMulti(False) == ("text", "*****", [])
    assert s.getMulti(True) == ("mtext", "*****", [])
    s.value = "abc123"
    # also in the selected row (the images' ConfigPassword shows the text there)
    assert s.getMulti(False)[1] == "******" and s.getMulti(True)[1] == "******"
    assert isinstance(s, ConfigPassword) and s.value == "abc123"


def test_login_placeholder_only_when_empty(secret):
    login = secret.ConfigLogin(default="", fixed_size=False)
    assert login.getMulti(False) == ("text", "xxxxx", [])
    login.value = "me@example.org"
    assert login.getMulti(False) == ("text", "me@example.org ", [0])


def test_read_only_two_items(secret):
    s = secret.ConfigSecret()
    s.readOnly = True
    s.value = "key"
    assert s.getMulti(False) == ("text", "***")
