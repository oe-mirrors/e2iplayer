# -*- coding: utf-8 -*-

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Components.SystemInfo import BoxInfo

GRIDSUPPORT = BoxInfo.getItem("distro") in ("openatv", )

import gettext

PluginLanguageDomain = "IPTVPlayer"
PluginLanguagePath = "Extensions/IPTVPlayer/locale"


def localeInit():
	gettext.bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))


def _(txt):
	t = gettext.dgettext(PluginLanguageDomain, txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t


localeInit()
language.addCallback(localeInit)
