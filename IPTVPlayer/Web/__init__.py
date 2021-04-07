# -*- coding: utf-8 -*-
# WebComponent will use own translation files to simplify management.
from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
import gettext

PluginLanguageDomain = "IPTVPlayerWebComponent"
PluginLanguagePath = "Extensions/IPTVPlayer/Web/locale"


def localeInit():
	gettext.bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))


def _(txt):
	t = gettext.dgettext(PluginLanguageDomain, txt)
	if t == txt:
		t = gettext.dgettext("IPTVPlayer", txt)
		if t == txt:
			t = gettext.gettext(txt)
	return t


localeInit()
language.addCallback(localeInit)
