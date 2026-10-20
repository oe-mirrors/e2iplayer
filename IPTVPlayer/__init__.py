# -*- coding: utf-8 -*-

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CONFIG
from gettext import bindtextdomain, dgettext, gettext

try:
    from enigma import eListbox
    from Components.SystemInfo import BoxInfo
    GRIDSUPPORT_NATIVE = eListbox.orGrid is not None and BoxInfo.getItem("distro") in ("openatv", "egami", "pure2")
except (AttributeError, ImportError):  # no grid listbox, or an image without BoxInfo
    GRIDSUPPORT_NATIVE = False


def _forceLegacyGrid():
    # config.plugins.iptvplayer.force_legacy_grid (skin settings): this module is loaded before the
    # plugin's config is defined, so the saved value is read from the settings file (only written
    # there while it is on, "True" on openATV, "true" on other images) - a change takes effect after a GUI restart.
    # Only with the icon grid ("Hosts list type" G, the default, not in the file): the option is shown only there
    force = False
    try:
        with open(resolveFilename(SCOPE_CONFIG, "settings")) as f:
            for rawLine in f:
                line = rawLine.strip().lower()
                if line == "config.plugins.iptvplayer.force_legacy_grid=true":
                    force = True
                elif line.startswith("config.plugins.iptvplayer.hostslisttype=") and line != "config.plugins.iptvplayer.hostslisttype=g":
                    return False
    except Exception:
        pass
    return force


# the native grid list (openATV & co.) unless the old hand-made icon grid is forced
GRIDSUPPORT = GRIDSUPPORT_NATIVE and not _forceLegacyGrid()

PluginLanguageDomain = "IPTVPlayer"
PluginLanguagePath = "Extensions/IPTVPlayer/locale"


def localeInit():
    bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))


def _(txt):
    if (t := dgettext(PluginLanguageDomain, txt)) != txt:
        return t
    else:
        return gettext(txt)


localeInit()
language.addCallback(localeInit)
