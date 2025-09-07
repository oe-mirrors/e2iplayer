# -*- coding: utf-8 -*-

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from gettext import bindtextdomain, dgettext, gettext

try:
	from enigma import eListbox
	from Components.SystemInfo import BoxInfo
	GRIDSUPPORT = eListbox.orGrid is not None and BoxInfo.getItem("distro") in ("openatv",)
except AttributeError:
	GRIDSUPPORT = False

PluginLanguageDomain = "IPTVPlayer"
PluginLanguagePath = "Extensions/IPTVPlayer/locale"


def localeInit():
	bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))


def _(txt):
	if t := dgettext(PluginLanguageDomain, txt):
		return t
	else:
		return gettext(txt)


localeInit()
language.addCallback(localeInit)
