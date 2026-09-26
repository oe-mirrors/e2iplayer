# -*- coding: utf-8 -*-
# The pages of the web interface. Each one is a frame from webParts.py; what changes on a page comes
# from the JSON interface (webApi.py), so reloading a page never repeats an action.

import os

from twisted.web import resource, util

from . import webParts
from .webTools import isActiveHostInitiated, hostDisplayTitle

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetDebugLogPath

########################################################


class _Page(resource.Resource):
	isLeaf = True
	pageId = ''

	def title(self):
		return ''

	def content(self, req):
		return ''

	def render_GET(self, req):
		req.setHeader(b'Content-Type', b'text/html; charset=utf-8')
		req.setHeader(b'Cache-Control', b'no-store')
		return webParts.page(self.pageId, self.title(), self.content(req)).encode('utf-8')


class RootPage(resource.Resource):
	# /iptvplayer without the slash
	def render_GET(self, req):
		return util.redirectTo(b'/iptvplayer/', req)


class StartPage(_Page):
	pageId = 'info'

	def title(self):
		return _('Information')

	def content(self, req):
		return webParts.infoPage()


class HostsPage(_Page):
	pageId = 'hosts'

	def title(self):
		return _('Hosts')

	def content(self, req):
		return webParts.hostsPage()


class UseHostPage(_Page):
	pageId = 'usehost'

	def title(self):
		from . import settings
		return hostDisplayTitle(settings.activeHost.get('Title', '')) if isActiveHostInitiated() else _('Host')

	def content(self, req):
		return webParts.useHostPage()


class SearchPage(_Page):
	pageId = 'search'

	def title(self):
		return _('Search')

	def content(self, req):
		return webParts.searchPage()


class DownloaderPage(_Page):
	pageId = 'downloader'

	def title(self):
		return _('Download manager')

	def content(self, req):
		return webParts.downloaderPage()


class SettingsPage(_Page):
	pageId = 'settings'

	def title(self):
		return _('Settings')

	def content(self, req):
		return webParts.settingsPage()


class LogsPage(_Page):
	pageId = 'logs'

	def title(self):
		return _('Logs')

	def content(self, req):
		return webParts.logsPage()

	def render_GET(self, req):
		command = req.args.get(b'cmd', [b''])[0]
		if command == b'downloadLog':
			path = GetDebugLogPath()
			if path and os.path.isfile(path):
				req.setHeader(b'Content-Type', b'text/plain; charset=utf-8')
				req.setHeader(b'Content-Disposition', b'attachment; filename="iptv_dbg.txt"')
				with open(path, 'rb') as f:
					return f.read()
		return _Page.render_GET(self, req)
