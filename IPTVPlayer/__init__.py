# -*- coding: utf-8 -*-

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from gettext import bindtextdomain, dgettext, gettext

from enigma import eListbox
try:
	GRIDSUPPORT = eListbox.orGrid is not None
except AttributeError:
	GRIDSUPPORT = False

PluginLanguageDomain = "IPTVPlayer"
PluginLanguagePath = "Extensions/IPTVPlayer/locale"


def localeInit():
	bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))


def _(txt):
	t = dgettext(PluginLanguageDomain, txt)
	if t == txt:
		t = gettext(txt)
	return t


localeInit()
language.addCallback(localeInit)
