

import os
from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

from .webSite import StartPage, redirectionPage, hostsPage, useHostPage, downloaderPage, settingsPage, logsPage, searchPage
from twisted.web import static

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetPluginDir
from . import settings

IPTVwebRoot = static.File(GetPluginDir('Web/').encode()) #webRoot = pluginDir to get access to icons and logos
IPTVwebRoot.putChild(b"icons", static.File(GetPluginDir('icons/').encode()))
IPTVwebRoot.putChild(b"", StartPage())
IPTVwebRoot.putChild(b"hosts", hostsPage())
IPTVwebRoot.putChild(b"usehost", useHostPage())
IPTVwebRoot.putChild(b"downloader", downloaderPage())
IPTVwebRoot.putChild(b"settings", settingsPage())
IPTVwebRoot.putChild(b"logs", logsPage())
IPTVwebRoot.putChild(b"search", searchPage())


# registration for old webinterface
if os.path.exists(resolveFilename(SCOPE_PLUGINS, 'Extensions/WebInterface/web/external.xml')):
	try:
		addExternalChild(("e2iplayer", IPTVwebRoot, "E2iPlayer", settings.WebInterfaceVersion, True))
		addExternalChild(("iptvplayer", IPTVwebRoot, "E2iPlayer", settings.WebInterfaceVersion, True))
	except Exception:
		addExternalChild(("e2iplayer", IPTVwebRoot))
		addExternalChild(("iptvplayer", IPTVwebRoot))
# registration for openwebif
elif os.path.exists(resolveFilename(SCOPE_PLUGINS, 'Extensions/OpenWebif/pluginshook.src')):
	try:
		addExternalChild(("iptvplayer", IPTVwebRoot, "E2iPlayer", settings.WebInterfaceVersion, True))
		addExternalChild(("e2iplayer", IPTVwebRoot, "E2iPlayer", settings.WebInterfaceVersion, True))
	except Exception:
		print("[E2iPlayer] exception registering Web interface in NATIVE mode")
else:
	print("No known webinterface available")
