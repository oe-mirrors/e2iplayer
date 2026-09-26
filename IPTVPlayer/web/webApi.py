# -*- coding: utf-8 -*-
# JSON interface of the web interface pages: /iptvplayer/api/<name>
# GET only reads, everything that changes something is a POST with a JSON body.

import os
import json

from twisted.web import resource

from . import settings
from . import webHost
from . import webThreads
from .webTools import (isThreadRunning, stopRunningThread, initActiveHost, isEditableConfigName, isLockedConfigName, isConfigPinProtected,
						isPluginPinProtected, isDownloadsFile, fileDownloadLocation, getHostTitle, hostLogoUrl, hostDisplayTitle, cleanText)

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (GetHostsList, SortHostsList, IsHostEnabled, getDebugMode, GetDebugLogPath,
															printDBG, printExc)
from Components.config import config, configfile

LOG_FIRST_BYTES = 128 * 1024   # what a freshly opened log page shows
LOG_MAX_BYTES = 512 * 1024     # most one poll returns
MEDIA_EXTENSIONS = ('.mp4', '.mkv', '.ts', '.flv', '.avi', '.mov', '.wmv', '.mpg', '.mpeg', '.m2ts', '.vob', '.divx', '.webm',
					'.mp3', '.m4a', '.aac', '.ogg', '.wma', '.wav', '.flac')

########################################################
# information


_systemInfo = None


def _getSystemInfo():
	global _systemInfo
	if _systemInfo is None:
		from Plugins.Extensions.IPTVPlayer.components.iptvplayerinfoview import _SystemInfo
		_systemInfo = _SystemInfo()
	return _systemInfo


def apiBinaries(req, params):
	# the binaries probe runs once (asynchronous, cached by the info view module); the page asks again
	# until the text is there
	from Plugins.Extensions.IPTVPlayer.components import iptvplayerinfoview
	if iptvplayerinfoview._PROBE_CACHE:
		return {'text': iptvplayerinfoview._SystemInfo.toPlain(iptvplayerinfoview._PROBE_CACHE)}
	si = _getSystemInfo()
	if si._probe is None:
		if getattr(si, 'webProbeStarted', False):
			# the probe ended without a result (see runProbe) - show what it has instead of starting it again
			return {'text': iptvplayerinfoview._SystemInfo.toPlain(si._systemBinaries or '?')}
		si.webProbeStarted = True
		si.runProbe(lambda: None)
	return {'pending': True}


def apiReset(req, params):
	# the web interface's own state only: open host, search, running threads - nothing on the box
	stillRunning = []
	for name in (webHost.WORKER, 'doGlobalSearch'):
		if stopRunningThread(name):
			stillRunning.append(name)
	initActiveHost(None)
	settings.hostView = {}
	settings.GlobalSearchQuery = ''
	settings.GlobalSearchResults = []
	settings.GlobalSearchProgress = {'done': 0, 'total': 0}
	settings.searchingInHost = None
	settings.hostsWithNoSearchOption = []
	settings.StopThreads = False
	return {'ok': True, 'stillRunning': stillRunning}

########################################################
# debug log


def _logState():
	mode = getDebugMode()
	if not mode:
		return {'state': 'off'}
	if mode == 'console':
		return {'state': 'console'}
	path = GetDebugLogPath()
	if not path or not os.path.isfile(path):
		return {'state': 'nofile', 'path': path}
	return {'state': 'ok', 'path': path, 'size': os.path.getsize(path)}


def apiLog(req, params):
	# the new part of the log from byte position "pos" on; pos -1 = the end of the file.
	# A file that got smaller (deleted, rotated) starts again from its beginning.
	state = _logState()
	if state['state'] != 'ok':
		return state
	try:
		pos = int(params.get('pos', -1))
	except Exception:
		pos = -1
	size = state['size']
	reset = pos < 0 or pos > size
	if reset:
		start = max(0, size - LOG_FIRST_BYTES) if pos < 0 else 0
	else:
		start = pos
	data = b''
	if size > start:
		with open(state['path'], 'rb') as f:
			f.seek(start)
			data = f.read(min(size - start, LOG_MAX_BYTES))
	if reset and start > 0:
		# the tail of the file: begin with a whole line
		cut = data.find(b'\n')
		if cut >= 0:
			start += cut + 1
			data = data[cut + 1:]
	# a line that is still being written stays for the next poll (unless it alone fills a whole poll)
	end = data.rfind(b'\n')
	if end >= 0:
		data = data[:end + 1]
	elif len(data) < LOG_MAX_BYTES:
		data = b''
	state.update({'pos': start + len(data), 'text': data.decode('utf-8', 'replace'), 'reset': reset})
	if reset:
		state['rotated'] = rotatedLogs(state['path'])
	return state


def rotatedLogs(path):
	# the older files of the debug log rotation (tools/iptvtools.py: <base>-<date><ext>), newest first
	from Plugins.Extensions.IPTVPlayer.tools.iptvtools import _rotatedGlob
	files = []
	try:
		for idx, name in enumerate(reversed(_rotatedGlob(path))):
			files.append({'n': idx + 1, 'name': os.path.basename(name), 'size': os.path.getsize(name)})
	except Exception:
		printExc()
	return files


def apiLogDelete(req, params):
	state = _logState()
	if state['state'] != 'ok':
		return {'ok': False, 'error': _('Debug file does not exist - nothing to delete')}
	try:
		os.remove(state['path'])
		return {'ok': True}
	except Exception as e:
		return {'ok': False, 'error': _('Error during deletion of the debug file.') + ' ' + str(e)}

########################################################
# settings


def _configName(element):
	for name, value in config.plugins.iptvplayer.dict().items():
		if value is element:
			return name
	return None


def _elementKind(element):
	names = [cls.__name__ for cls in type(element).__mro__]
	if 'ConfigBoolean' in names:
		return 'bool'
	if 'ConfigPassword' in names:
		return 'password'
	if 'ConfigSelection' in names:
		return 'select'
	if 'ConfigInteger' in names:
		return 'int'
	if 'ConfigDirectory' in names or 'ConfigText' in names:
		return 'text'
	return 'readonly'


def _choices(element):
	res = []
	try:
		for key in element.choices:
			res.append([str(key), cleanText(element.description[key])])
	except Exception:
		printExc()
	return res


def _elementText(element):
	try:
		return cleanText(element.getText())
	except Exception:
		try:
			return cleanText(element.value)
		except Exception:
			return ''


RESTART_OPTIONS = ('IPTVWebIterface', 'showinPluginBrowser', 'showinextensions', 'showinMainMenu', 'showinSystemMenu', 'plugin_autostart',
				'plugin_autostart_method', 'disable_live', 'pluginProtectedByPin', 'skin', 'skinforceinternal', 'skinforceallinternal')


def _rows(entries, editable, readOnly):
	rows = []
	for entry in entries:
		label = entry[0] if len(entry) else ''
		indent = (len(label) - len(label.lstrip(' '))) // 4
		label = label.strip()
		if len(entry) < 2 or entry[1] is None:
			rows.append({'header': label.strip('=- ').strip()})
			continue
		element = entry[1]
		name = _configName(element)
		if name is None:
			continue
		kind = _elementKind(element)
		row = {'name': name, 'label': label, 'indent': indent, 'kind': kind, 'restart': name in RESTART_OPTIONS}
		if readOnly or name not in editable:
			row['kind'] = 'readonly'
			row['note'] = _('only on the receiver') if isLockedConfigName(name) or kind == 'readonly' else ''
			row['value'] = '' if kind == 'password' else _elementText(element)
		elif kind == 'bool':
			row['value'] = bool(element.value)
		elif kind == 'select':
			row['value'] = str(element.value)
			row['choices'] = _choices(element)
		elif kind == 'int':
			row['value'] = int(element.value)
			try:
				row['min'], row['max'] = element.limits[0]
			except Exception:
				pass
		elif kind == 'password':
			row['value'] = ''
		else:
			row['value'] = cleanText(element.value)
		rows.append(row)
	return rows


def apiSettingsSections(req, params):
	from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu
	_editableCache['names'] = None  # the page is (re)opened: hosts may have been added or removed
	return {'locked': isConfigPinProtected(), 'restartPending': settings.restartPending,
			'sections': [{'id': sectionId, 'label': ConfigMenu.getSectionLabel(header)} for sectionId, header, fill in ConfigMenu.getSections()]}


def apiSettingsSection(req, params):
	from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu
	sectionId = params.get('id', '')
	entries = []
	ConfigMenu.fillConfigList(entries, sectionId)
	editable = settingsEditableNames()
	return {'rows': _rows(entries, editable, isConfigPinProtected())}


def apiSettingsHosts(req, params):
	hosts = []
	for hostName in SortHostsList(GetHostsList()):
		title = getHostTitle(hostName)
		if title is None:
			continue  # broken host
		hasOptions = False
		try:
			_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['GetConfigList'], 0)
			hasOptions = len(_temp.GetConfigList()) > 0
		except Exception:
			pass
		hosts.append({'name': hostName, 'title': hostDisplayTitle(title), 'logo': hostLogoUrl(hostName), 'enabled': IsHostEnabled(hostName),
					'hasOptions': hasOptions})
	return {'locked': isConfigPinProtected(), 'hosts': hosts}


def apiSettingsHost(req, params):
	hostName = params.get('name', '')
	if hostName not in GetHostsList():
		return {'rows': []}
	try:
		_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['GetConfigList'], 0)
		entries = _temp.GetConfigList()
	except Exception:
		entries = []
	return {'rows': _rows(entries, settingsEditableNames(), isConfigPinProtected())}


_editableCache = {'names': None}


def settingsEditableNames():
	names = _editableCache['names']
	if names is None:
		from .webTools import getEditableConfigNames
		names = getEditableConfigNames()
		_editableCache['names'] = names
	return names


def apiSettingsSet(req, params):
	name = str(params.get('name', ''))
	value = params.get('value')
	if isConfigPinProtected():
		return {'ok': False, 'error': _('The settings are protected by a PIN, change them on the receiver.')}
	_editableCache['names'] = None  # conditional options may show up after a change
	if not isEditableConfigName(name):
		printDBG("[webApi] refused to change '%s'" % name)
		return {'ok': False, 'error': _('This option cannot be changed from the web interface.')}
	element = getattr(config.plugins.iptvplayer, name)
	kind = _elementKind(element)
	try:
		if kind == 'bool':
			element.value = bool(value)
		elif kind == 'select':
			for key in element.choices:
				if str(key) == str(value):
					element.value = key
					break
			else:
				return {'ok': False, 'error': _('Invalid value.')}
		elif kind == 'int':
			value = int(value)
			try:
				low, high = element.limits[0]
				if not low <= value <= high:
					return {'ok': False, 'error': _('The value must be between %d and %d.') % (low, high)}
			except (AttributeError, IndexError, TypeError):
				pass
			element.value = value
		elif kind in ('text', 'password'):
			element.value = str(value)
		else:
			return {'ok': False, 'error': _('This option cannot be changed from the web interface.')}
		element.save()
		configfile.save()
	except Exception as e:
		printExc()
		return {'ok': False, 'error': str(e)}
	if name in RESTART_OPTIONS:
		settings.restartPending = True
	return {'ok': True, 'restart': name in RESTART_OPTIONS}


def apiRestart(req, params):
	# restart of the enigma2 GUI (like Standby -> Restart GUI); answered first, then started
	if settings.session is None:
		return {'ok': False, 'error': _('Not possible (no enigma2 session).')}
	from twisted.internet import reactor

	def _restart():
		from Screens.Standby import TryQuitMainloop
		settings.session.open(TryQuitMainloop, 3)
	printDBG('[E2iPlayer web] GUI restart requested')
	reactor.callLater(1, _restart)
	return {'ok': True}

########################################################
# hosts


def _hostGroups():
	from Plugins.Extensions.IPTVPlayer.tools.iptvhostgroups import IPTVHostsGroups
	groupsObj = IPTVHostsGroups()
	groups = [{'name': 'all', 'title': _('All')}]
	try:
		groups += [{'name': item.name, 'title': cleanText(item.title)} for item in groupsObj.getGroupsList() if item.name != 'all']
	except Exception:
		printExc()
	return groupsObj, groups


def apiHosts(req, params):
	if isPluginPinProtected():
		return {'pinBlocked': True, 'hosts': [], 'groups': []}
	groupsObj, groups = _hostGroups()
	group = params.get('group', 'all')
	if group not in [g['name'] for g in groups]:
		group = 'all'
	if group == 'all':
		hostNames = SortHostsList(GetHostsList(fromList=False, fromHostFolder=True))
	else:
		# the group's own order, as the GUI shows it
		try:
			hostNames = groupsObj.getHostsList(group)
		except Exception:
			printExc()
			hostNames = []
	hosts = []
	for hostName in hostNames:
		if hostName in ['localmedia', 'urllist']:  # local hosts, nothing to do via web interface
			continue
		if not IsHostEnabled(hostName):
			continue
		title = getHostTitle(hostName)
		if title is None:
			continue  # broken host
		site = title if title.startswith('http') else ''
		hosts.append({'name': hostName, 'title': hostDisplayTitle(title), 'site': site, 'logo': hostLogoUrl(hostName)})
	return {'pinBlocked': False, 'hosts': hosts, 'groups': groups, 'group': group}


def apiHostState(req, params):
	return webHost.getState()


def apiHostAction(req, params):
	error = webHost.doAction(params)
	return {'ok': not error, 'error': error}

########################################################
# global search


def apiSearchState(req, params):
	busy = isThreadRunning('doGlobalSearch')
	return {'busy': busy, 'query': settings.GlobalSearchQuery, 'host': settings.searchingInHost if busy else None,
			'done': settings.GlobalSearchProgress.get('done', 0), 'total': settings.GlobalSearchProgress.get('total', 0),
			'results': settings.GlobalSearchResults, 'pinBlocked': isPluginPinProtected()}


def apiSearchStart(req, params):
	query = str(params.get('query', '')).strip()
	if not query:
		return {'ok': False, 'error': _('Please enter a search text.')}
	if isThreadRunning('doGlobalSearch'):
		return {'ok': False, 'error': _('A search is already running.')}
	settings.GlobalSearchQuery = query
	webThreads.doGlobalSearch().start()
	return {'ok': True}


def apiSearchStop(req, params):
	stopRunningThread('doGlobalSearch')
	return {'ok': True}

########################################################
# download manager


_STATUS = {DMHelper.STS.WAITING: 'waiting', DMHelper.STS.DOWNLOADING: 'downloading', DMHelper.STS.DOWNLOADED: 'downloaded',
		DMHelper.STS.INTERRUPTED: 'interrupted', DMHelper.STS.ERROR: 'error', DMHelper.STS.POSTPROCESSING: 'postprocessing'}


def _dmItem(item):
	fileName = item.fileName or ''
	status = _STATUS.get(item.status, str(item.status))
	exists = status in ('downloaded', 'interrupted', 'downloading') and isDownloadsFile(fileName)
	return {'idx': item.downloadIdx, 'file': os.path.basename(fileName), 'path': fileName, 'url': str(item.url)[:500], 'status': status,
			'size': item.fileSize, 'done': item.downloadedSize, 'percent': item.downloadedProcent, 'speed': item.downloadedSpeed,
			'duration': item.totalFileDuration, 'doneDuration': item.downloadedFileDuration,
			'downloader': getattr(item, 'downloaderName', ''), 'href': fileDownloadLocation(fileName) if exists else ''}


def apiDM(req, params):
	dm = webHost.getDownloadManager()
	if dm is None:
		return {'initialized': False}
	try:
		dm.updateDownloadItemsStatus()
	except Exception:
		printExc()
	return {'initialized': True, 'running': dm.isRunning(), 'items': [_dmItem(item) for item in dm.getList()]}


def apiDMArchive(req, params):
	folder = config.plugins.iptvplayer.DownloadsDir.value
	dm = webHost.getDownloadManager()
	inQueue = set(os.path.normpath(item.fileName) for item in dm.getList()) if dm else set()
	files = []
	try:
		for name in os.listdir(folder):
			path = os.path.join(folder, name)
			if name.startswith('.') or not name.lower().endswith(MEDIA_EXTENSIONS) or not os.path.isfile(path):
				continue
			if os.path.normpath(path) in inQueue:
				continue
			stat = os.stat(path)
			files.append({'file': name, 'path': path, 'size': stat.st_size, 'mtime': int(stat.st_mtime), 'href': fileDownloadLocation(path)})
	except Exception as e:
		return {'folder': folder, 'files': [], 'error': str(e)}
	files.sort(key=lambda x: x['file'].lower())
	return {'folder': folder, 'files': files}


def _dmAddUrl(url, name):
	from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
	from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmapi import DMItem
	from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import IsUrlDownloadable
	if not url.startswith(('http://', 'https://', 'rtmp', 'mms', 'rtsp')):
		return {'ok': False, 'error': _('Please enter a valid link (http:// or https://).')}
	url = urlparser.decorateUrl(url)
	if not IsUrlDownloadable(url):
		return {'ok': False, 'error': _("File can not be downloaded. Protocol [%s] is unsupported") % url.meta.get('iptv_proto', '')}
	if not name:
		name = os.path.basename(url.split('?', 1)[0].rstrip('/')) or 'download'
	for char in '/\\:*?"<>|':
		name = name.replace(char, '-')
	base, ext = os.path.splitext(name)
	if ext.lower() not in MEDIA_EXTENSIONS:
		name += webHost.getFileExt(url, 'VIDEO')
	fullFilePath = config.plugins.iptvplayer.DownloadsDir.value + '/' + name
	dm = webHost.getDownloadManager(True)
	if not dm.addToDQueue(DMItem(url, fullFilePath)):
		return {'ok': False, 'error': _("File [%s] is already in the downloading queue.") % name}
	printDBG('[E2iPlayer web] download of a pasted link [%s] -> [%s]' % (url, fullFilePath))
	return {'ok': True, 'file': name, 'running': dm.isRunning()}


def apiDMCommand(req, params):
	cmd = params.get('cmd', '')
	if cmd == 'init':
		webHost.getDownloadManager(True)
		return {'ok': True}
	if cmd == 'addUrl':
		return _dmAddUrl(str(params.get('url', '')).strip(), str(params.get('name', '')).strip())
	if cmd == 'deleteFile':
		path = str(params.get('path', ''))
		if not isDownloadsFile(path):
			return {'ok': False, 'error': _('Only files in the downloads folder can be deleted.')}
		os.remove(path)
		return {'ok': True}
	dm = webHost.getDownloadManager()
	if dm is None:
		return {'ok': False, 'error': _('Download manager is not initialized')}
	try:
		idx = int(params.get('idx', -1))
	except Exception:
		idx = -1
	commands = {'start': dm.runWorkThread, 'stop': dm.stopWorkThread,
				'stopItem': lambda: dm.stopDownloadItem(idx), 'resume': lambda: dm.continueDownloadItem(idx),
				'retry': lambda: dm.retryDownloadItem(idx), 'remove': lambda: dm.removeDownloadItem(idx),
				'removeQueued': lambda: dm.deleteDownloadItem(idx), 'top': lambda: dm.moveToTopDownloadItem(idx)}
	if cmd not in commands:
		return {'ok': False, 'error': _('Unknown action.')}
	commands[cmd]()
	return {'ok': True}

########################################################


GET_ROUTES = {'binaries': apiBinaries, 'log': apiLog, 'settings/sections': apiSettingsSections, 'settings/section': apiSettingsSection,
			'settings/hosts': apiSettingsHosts, 'settings/host': apiSettingsHost, 'hosts': apiHosts, 'host/state': apiHostState,
			'search/state': apiSearchState, 'dm': apiDM, 'dm/archive': apiDMArchive}
POST_ROUTES = {'reset': apiReset, 'log/delete': apiLogDelete, 'settings/set': apiSettingsSet, 'host/action': apiHostAction,
			'search/start': apiSearchStart, 'search/stop': apiSearchStop, 'dm': apiDMCommand, 'restart': apiRestart}


class ApiResource(resource.Resource):
	isLeaf = True

	def _answer(self, req, routes, params):
		path = '/'.join(p.decode('utf-8', 'ignore') for p in req.postpath if p)
		req.setHeader(b'Content-Type', b'application/json; charset=utf-8')
		req.setHeader(b'Cache-Control', b'no-store')
		fnc = routes.get(path)
		if fnc is None:
			req.setResponseCode(404)
			return json.dumps({'ok': False, 'error': 'unknown api %s' % path}).encode('utf-8')
		try:
			ret = fnc(req, params)
		except Exception as e:
			printExc()
			req.setResponseCode(500)
			ret = {'ok': False, 'error': str(e)}
		return json.dumps(ret).encode('utf-8')

	@staticmethod
	def _refusedPost(req):
		contentType = (req.getHeader(b'content-type') or b'').decode('latin-1').split(';', 1)[0].strip().lower()
		if contentType != 'application/json':
			return 'content type %s' % contentType
		origin = (req.getHeader(b'origin') or b'').decode('latin-1')
		if origin:
			host = (req.getHeader(b'host') or b'').decode('latin-1').lower()
			originHost = origin.split('://', 1)[-1].split('/', 1)[0].lower()
			if originHost != host:
				return 'origin %s' % origin
		return ''

	def render_GET(self, req):
		params = dict((k.decode('utf-8', 'ignore'), v[0].decode('utf-8', 'ignore')) for k, v in req.args.items() if v)
		return self._answer(req, GET_ROUTES, params)

	def render_POST(self, req):
		# a form of another web site can send a POST to the box, but only as form or text content and
		# with its own Origin - the pages of the web interface send JSON from the box's own address
		refused = self._refusedPost(req)
		if refused:
			printDBG('[E2iPlayer web] refused POST: %s' % refused)
			req.setResponseCode(403)
			req.setHeader(b'Content-Type', b'application/json; charset=utf-8')
			return json.dumps({'ok': False, 'error': refused}).encode('utf-8')
		try:
			params = json.loads(req.content.read().decode('utf-8') or '{}')
			if not isinstance(params, dict):
				params = {}
		except Exception:
			params = {}
		return self._answer(req, POST_ROUTES, params)
