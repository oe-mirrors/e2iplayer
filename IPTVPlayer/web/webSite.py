# -*- coding: utf-8 -*-
# The pages of the web interface. Each one is a frame from webParts.py; what changes on a page comes
# from the JSON interface (webApi.py), so reloading a page never repeats an action.

import os
import time

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
			# n=1, 2 ... = the rotated older files, newest first (webApi.rotatedLogs)
			try:
				n = int(req.args.get(b'n', [b'0'])[0])
			except ValueError:
				n = 0
			if path and n > 0:
				from Plugins.Extensions.IPTVPlayer.tools.iptvtools import _rotatedGlob
				rotated = list(reversed(_rotatedGlob(path)))
				path = rotated[n - 1] if n <= len(rotated) else ''
			if path and os.path.isfile(path):
				return self._file(req, os.path.basename(path) if n else 'iptv_dbg.txt', open(path, 'rb').read())
		elif command == b'support':
			from Plugins.Extensions.IPTVPlayer.version import IPTV_VERSION
			return self._file(req, 'e2iplayer-support-%s-%s.txt' % (IPTV_VERSION, time.strftime('%Y%m%d-%H%M')), supportPackage())
		return _Page.render_GET(self, req)

	@staticmethod
	def _file(req, name, data):
		req.setHeader(b'Content-Type', b'text/plain; charset=utf-8')
		req.setHeader(b'Content-Disposition', ('attachment; filename="%s"' % name.replace('"', '')).encode('utf-8'))
		return data
########################################################


SUPPORT_LOG_BYTES = 256 * 1024


def supportPackage():
	# everything a problem report needs in one text file: versions, system, binaries, the enabled hosts and
	# the end of the debug log
	from Plugins.Extensions.IPTVPlayer.components import iptvplayerinfoview
	from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetHostsList, IsHostEnabled
	from Plugins.Extensions.IPTVPlayer.version import IPTV_VERSION
	parts = ['E2iPlayer support package - %s - %s' % (IPTV_VERSION, time.strftime('%Y-%m-%d %H:%M:%S')), '']
	try:
		si = iptvplayerinfoview._SystemInfo()
		si._systemBinaries = iptvplayerinfoview._PROBE_CACHE or ''
		parts.append(iptvplayerinfoview._SystemInfo.toPlain(si.buildSystemText(withBinaries=bool(si._systemBinaries))))
	except Exception as e:
		parts.append('system info: %s' % e)
	try:
		parts += ['', '--- %s ---' % _('Enabled hosts'), ', '.join(name for name in GetHostsList() if IsHostEnabled(name))]
	except Exception as e:
		parts.append('hosts: %s' % e)
	path = GetDebugLogPath()
	parts += ['', '--- %s: %s ---' % (_('Debug log'), path or '-')]
	if path and os.path.isfile(path):
		size = os.path.getsize(path)
		with open(path, 'rb') as f:
			f.seek(max(0, size - SUPPORT_LOG_BYTES))
			data = f.read().decode('utf-8', 'replace')
		if size > SUPPORT_LOG_BYTES:
			data = data.split('\n', 1)[-1]
		parts.append(data)
	else:
		parts.append(_('Debug option is disabled - nothing to display'))
	return '\n'.join(parts).encode('utf-8')
