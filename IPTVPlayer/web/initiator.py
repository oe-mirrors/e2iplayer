import os
from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

from .webSite import RootPage, StartPage, HostsPage, UseHostPage, DownloaderPage, SettingsPage, LogsPage, SearchPage
from .webApi import ApiResource
from twisted.web import static

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetPluginDir
from . import settings

# only the pages, the JSON interface, the web assets and the plugin icons are served - not the plugin files
IPTVwebRoot = RootPage()
IPTVwebRoot.putChild(b"icons", static.File(GetPluginDir('icons/').encode()))
IPTVwebRoot.putChild(b"assets", static.File(GetPluginDir('web/assets/').encode()))
IPTVwebRoot.putChild(b"api", ApiResource())
IPTVwebRoot.putChild(b"", StartPage())
IPTVwebRoot.putChild(b"hosts", HostsPage())
IPTVwebRoot.putChild(b"usehost", UseHostPage())
IPTVwebRoot.putChild(b"downloader", DownloaderPage())
IPTVwebRoot.putChild(b"settings", SettingsPage())
IPTVwebRoot.putChild(b"logs", LogsPage())
IPTVwebRoot.putChild(b"search", SearchPage())


# registration for old webinterface
if os.path.exists(resolveFilename(SCOPE_PLUGINS, 'Extensions/WebInterface/web/external.xml')):
	try:
		addExternalChild(("iptvplayer", IPTVwebRoot, "E2iPlayer", settings.WebInterfaceVersion, True))
	except Exception:
		addExternalChild(("iptvplayer", IPTVwebRoot))
# registration for openwebif
elif os.path.exists(resolveFilename(SCOPE_PLUGINS, 'Extensions/OpenWebif/pluginshook.src')):
	try:
		addExternalChild(("iptvplayer", IPTVwebRoot, "E2iPlayer", settings.WebInterfaceVersion, True))
	except Exception:
		print("[E2iPlayer] exception registering Web interface in NATIVE mode")
else:
	print("No known webinterface available")
