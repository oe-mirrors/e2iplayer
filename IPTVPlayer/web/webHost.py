# -*- coding: utf-8 -*-
# The host session of the web interface: one host at a time, browsed by actions the page sends
# (POST /iptvplayer/api/host/action) and a state the page reads (GET /iptvplayer/api/host/state).
# Reading the state never changes anything, so reloading the page or going back in the browser
# cannot repeat a click.

import time

from . import settings
from .webThreads import WebWorker, WebActionError
from .webTools import initActiveHost, isActiveHostInitiated, isThreadRunning, stopRunningThread, cleanText, iconUrl, hostLogoUrl, hostDisplayTitle

import Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget as iptvplayerwidget
from Plugins.Extensions.IPTVPlayer.components.ihost import RetHost, CUrlItem, CDisplayListItem, CFavItem
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmapi import IPTVDMApi, DMItem
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import IsUrlDownloadable
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Components.config import config

WORKER = 'doUseHostAction'
FOLDER_TYPES = (CDisplayListItem.TYPE_CATEGORY,)
LINK_TYPES = (CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_PICTURE, CDisplayListItem.TYPE_DATA)
PLAYABLE_TYPES = (CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO)
HISTORY_TYPE_SEP = '|--TYPE--|'  # tools/iptvtools.py CSearchHistoryHelper.TYPE_SEP

########################################################


def _view():
	if not settings.hostView:
		settings.hostView.update({'view': 'list', 'path': [], 'links': [], 'linksTitle': '', 'linksType': '', 'article': None,
								'notices': [], 'error': '', 'action': '', 'started': 0})
	return settings.hostView


def _currentList():
	try:
		return settings.retObj.value if isinstance(settings.retObj.value, list) else []
	except Exception:
		return []


def _setList(ret):
	if ret is None or not isinstance(getattr(ret, 'value', None), list):
		raise WebActionError(_('The host did not return a list.'))
	settings.retObj = ret
	_view()['view'] = 'list'
########################################################


def _itemToDict(item, index):
	return {'i': index, 'type': item.type, 'name': cleanText(item.name), 'desc': cleanText(item.description, True),
			'icon': iconUrl(item.iconimage, item.type), 'pin': bool(getattr(item, 'pinLocked', False))}


def _linkToDict(link, index, playable):
	url = str(link.url)
	resolve = int(link.urlNeedsResolve) == 1
	return {'i': index, 'name': cleanText(link.name) or url, 'url': url, 'resolve': resolve,
			'watch': not resolve and url.startswith(('http://', 'https://')), 'play': not resolve and playable}


def _searchHistory():
	# the host's own search history (newest first), as the GUI offers it
	try:
		history = settings.activeHost['Obj'].host.history
	except Exception:
		return []
	entries = []
	try:
		for value in history.getHistoryList()[:15]:
			pattern, _sep, searchType = value.partition(HISTORY_TYPE_SEP)
			if pattern.strip():
				entries.append({'pattern': pattern, 'type': searchType})
	except Exception:
		printExc()
	return entries


def getState():
	v = _view()
	busy = isThreadRunning(WORKER)
	state = {'busy': busy, 'cancelling': busy and v.get('cancelling', False), 'action': v['action'],
			'elapsed': int(time.time() - v['started']) if busy else 0,
			'error': v['error'], 'notices': v['notices'], 'host': None}
	if not isActiveHostInitiated():
		return state
	host = settings.activeHost
	items = _currentList()
	playable = v['linksType'] in PLAYABLE_TYPES and settings.session is not None
	state.update({
		'host': {'name': host['Name'], 'title': hostDisplayTitle(host['Title']), 'logo': hostLogoUrl(host['Name'])},
		'view': v['view'], 'path': v['path'],
		'items': [_itemToDict(item, idx) for idx, item in enumerate(items)],
		'searchTypes': [[cleanText(label), value] for label, value in (host.get('SearchTypes') or [])],
		'hasSearch': any(item.type == CDisplayListItem.TYPE_SEARCH for item in items),
		'links': [_linkToDict(link, idx, playable) for idx, link in enumerate(v['links'])] if v['view'] == 'links' else [],
		'linksTitle': v['linksTitle'], 'article': v['article'] if v['view'] == 'article' else None,
		'favTypes': list(host.get('SupportedTypes') or []),
		'favPending': {'title': v['fav']['title'], 'groups': v['fav']['groups']} if v.get('fav') else None,
	})
	if state['hasSearch'] and not busy:
		state['history'] = _searchHistory()
	return state
########################################################


def _onDone(error, notices):
	v = _view()
	printDBG('[E2iPlayer web] action "%s" done after %.1fs, error: %s, messages: %d' % (v['action'], time.time() - v['started'], error or '-', len(notices)))
	if error == 'cancelled':
		error = _('Cancelled.')
	v['error'] = error
	for notice in notices:
		screen = notice.get('screen', '')
		if screen == 'MessageBox':
			text = cleanText(notice.get('text', ''), True)
		elif 'aptcha' in screen:
			text = _('The host asks for a captcha. It can only be solved on the receiver (or with MyE2i there).')
		else:
			text = _('The host wanted to open a window on the TV (%s) - that only works on the receiver.') % screen
		if text:
			v['notices'].append(text)


def _start(action, fnc, *args):
	v = _view()
	v.update({'action': action, 'started': time.time(), 'error': '', 'notices': [], 'cancelling': False})
	printDBG('[E2iPlayer web] action "%s" %r host "%s"' % (action, args, settings.activeHost.get('Name', '')))
	WebWorker(WORKER, fnc, args, _onDone).start()
########################################################
# the actions, run in the worker thread


def _open(hostName):
	v = _view()
	v.update({'view': 'list', 'path': [], 'links': [], 'article': None})
	if not initActiveHost(hostName):
		raise WebActionError(_('The host "%s" cannot be used from the web interface (disabled, unknown or protected by PIN).') % hostName)


def _selectItem(index):
	items = _currentList()
	if not 0 <= index < len(items):
		raise WebActionError(_('The list has changed, please try again.'))
	item = items[index]
	obj = settings.activeHost['Obj']
	v = _view()
	if item.type in FOLDER_TYPES:
		if getattr(item, 'pinLocked', False):
			raise WebActionError(_('This folder is protected by a PIN, open it on the receiver.'))
		_setList(obj.getListForItem(index, 0, item))
		v['path'].append(cleanText(item.name))
	elif item.type == CDisplayListItem.TYPE_MORE:
		_setList(obj.getMoreForItem(index))
	elif item.type in LINK_TYPES:
		_loadLinks(obj, index, item)
	elif item.type == CDisplayListItem.TYPE_ARTICLE:
		_loadArticle(obj, index, item)
	else:
		raise WebActionError(_('This entry cannot be opened.'))


def _loadLinks(obj, index, item):
	v = _view()
	try:
		ret = obj.getLinksForVideo(index, item)
	except Exception:
		printExc()
		ret = RetHost(RetHost.NOT_IMPLEMENTED, value=[])
	links = []
	if ret.status == RetHost.OK and isinstance(ret.value, list):
		links = [link for link in ret.value if isinstance(link, CUrlItem)]
	elif ret.status == RetHost.NOT_IMPLEMENTED:
		# hosts without getLinksForVideo: the links of the list item itself
		for idx, link in enumerate(getattr(item, 'urlItems', []) or []):
			links.append(CUrlItem(link.name or ('link %d' % (idx + 1)), link.url, link.urlNeedsResolve))
	if not links:
		raise WebActionError(_('No valid links available.'))
	v.update({'view': 'links', 'links': links, 'linksTitle': cleanText(item.name), 'linksType': item.type})


def _loadArticle(obj, index, item):
	ret = obj.getArticleContent(index)
	if ret.status != RetHost.OK or not ret.value:
		raise WebActionError(_('No description available.'))
	art = ret.value[0]
	images = []
	for img in getattr(art, 'images', []) or []:
		url = img.get('url', '') if isinstance(img, dict) else ''
		if url.startswith('http'):
			images.append(url)
	other = []
	for key, value in (getattr(art, 'richDescParams', {}) or {}).items():
		if value:
			label = art.RICH_DESC_LABELS.get(key, key) if hasattr(art, 'RICH_DESC_LABELS') else key
			other.append([_(label), cleanText(value)])
	_view().update({'view': 'article', 'article': {'title': cleanText(art.title or item.name), 'text': cleanText(art.text, True),
												'images': images, 'other': other}})


def _resolve(index):
	v = _view()
	if v['view'] != 'links' or not 0 <= index < len(v['links']):
		raise WebActionError(_('The list has changed, please try again.'))
	ret = settings.activeHost['Obj'].getResolvedURL(v['links'][index].url)
	links = []
	if ret.status == RetHost.OK and isinstance(ret.value, list):
		for link in ret.value:
			if isinstance(link, CUrlItem):
				link.urlNeedsResolve = 0  # protection from recursion
				links.append(link)
			elif isinstance(link, str):
				links.append(CUrlItem(link, link, 0))
	if not links:
		raise WebActionError(_('The link could not be resolved.'))
	v['links'] = links


def _back():
	v = _view()
	if v['view'] != 'list':
		v['view'] = 'list'
		return
	if v['path']:
		_setList(settings.activeHost['Obj'].getPrevList())
		v['path'].pop()


def _home():
	_setList(settings.activeHost['Obj'].getInitList())
	_view()['path'] = []


def _refresh():
	_setList(settings.activeHost['Obj'].getCurrentList(1))


def _search(pattern, searchType):
	_setList(settings.activeHost['Obj'].getSearchResults(pattern, searchType))
	_view()['path'].append(_('Search') + ': ' + pattern)


def _openSearch(hostName, pattern, searchType):
	_open(hostName)
	_search(pattern, searchType)


def _favourite(index):
	# like the GUI (iptvplayerwidget.handleFavouriteItemCallback): the host builds the favourite, the
	# page then picks the group (favouriteAdd)
	from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
	from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetFavouritesDir
	items = _currentList()
	if not 0 <= index < len(items):
		raise WebActionError(_('The list has changed, please try again.'))
	ret = settings.activeHost['Obj'].getFavouriteItem(index)
	if ret.status != RetHost.OK or not isinstance(ret.value, list) or len(ret.value) != 1 or not isinstance(ret.value[0], CFavItem):
		raise WebActionError(_('This entry cannot be added to the favourites.'))
	favItem = ret.value[0]
	if CFavItem.RESOLVER_SELF == favItem.resolver:
		favItem.resolver = settings.activeHost['Name']
	if '' == favItem.hostName:
		favItem.hostName = settings.activeHost['Name']
	favourites = IPTVFavourites(GetFavouritesDir())
	if not favourites.load(groupsOnly=True):
		raise WebActionError(favourites.getLastError())
	groups = [[group['group_id'], cleanText(group.get('title', group['group_id']))] for group in favourites.getGroups()]
	_view()['fav'] = {'item': favItem, 'title': cleanText(items[index].name), 'groups': groups}


def _favouriteAdd(groupId, newGroup):
	from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
	from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetFavouritesDir, IsValidFileName
	v = _view()
	fav = v.get('fav')
	if not fav:
		raise WebActionError(_('The list has changed, please try again.'))
	favourites = IPTVFavourites(GetFavouritesDir())
	if not favourites.load(groupsOnly=True):
		raise WebActionError(favourites.getLastError())
	groupTitle = ''
	if newGroup:
		# same rules as IPTVFavouritesAddNewGroupWidget
		if not IsValidFileName(newGroup):
			raise WebActionError(_("Name is not valid.\nPlease remove special characters."))
		group = {'title': newGroup, 'group_id': newGroup.lower(), 'desc': ' '}
		if not favourites.addGroup(group) or not favourites.save(True):
			raise WebActionError(favourites.getLastError())
		groupId, groupTitle = group['group_id'], newGroup
	else:
		for group in favourites.getGroups():
			if group['group_id'] == groupId:
				groupTitle = group.get('title', groupId)
		if not groupTitle:
			raise WebActionError(_('Please select a group of favourites.'))
	if not (favourites.loadGroupItems(groupId, force=False) and favourites.addGroupItem(fav['item'], groupId) and favourites.saveGroupItems(groupId)):
		raise WebActionError(favourites.getLastError())
	v['fav'] = None
	v['notices'].append(_('"%s" has been added to the favourites group "%s".') % (fav['title'], cleanText(groupTitle)))


def playOnTv(index):
	# runs in the main thread: opens E2iPlayer's own movie player on the TV, the same one and the same
	# way the GUI does for a link without buffering (iptvplayerwidget.playVideo)
	from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
	from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetMoviePlayer
	from Plugins.Extensions.IPTVPlayer.components.asynccall import gMainFunctionsQueueTab
	from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetE2VideoMode, SetE2VideoMode
	v = _view()
	session = settings.session
	if session is None:
		return _('Playing on the TV is not possible (no enigma2 session).')
	if v['view'] != 'links' or not 0 <= index < len(v['links']) or v['linksType'] not in PLAYABLE_TYPES:
		return _('The list has changed, please try again.')
	link = v['links'][index]
	if int(link.urlNeedsResolve) == 1:
		return _('Please select the link first.')
	url = urlparser.decorateUrl(link.url)
	protocol = url.meta.get('iptv_proto', '')
	if protocol == '':
		return _("Unknown protocol [%s]") % url
	if protocol in ('f4m', 'uds'):
		return _('This stream can only be played with buffering - please start it on the receiver.')
	title = v['linksTitle'] or link.name
	prevVideoMode = GetE2VideoMode()
	params = {'defaul_videomode': prevVideoMode, 'host_name': settings.activeHost.get('Name', ''),
			'external_sub_tracks': url.meta.get('external_sub_tracks', []), 'iptv_refresh_cmd': url.meta.get('iptv_refresh_cmd', '')}
	if v['linksType'] == CDisplayListItem.TYPE_AUDIO:
		params.update({'show_iframe': config.plugins.iptvplayer.show_iframe.value, 'iframe_file_start': config.plugins.iptvplayer.iframe_file.value,
					'iframe_file_end': config.plugins.iptvplayer.clear_iframe_file.value, 'iframe_continue': False})
	# with the E2iPlayer screen open on the TV the screen brings the live TV back itself
	queue = gMainFunctionsQueueTab[0]
	guiOpen = queue is not None and queue.procFun is not None
	prevService = None if guiOpen else session.nav.getCurrentlyPlayingServiceReference()

	def _closed(*args, **kwargs):
		try:
			if prevVideoMode and GetE2VideoMode() != prevVideoMode:
				SetE2VideoMode(prevVideoMode)
			if prevService is not None:
				session.nav.playService(prevService)
		except Exception:
			printExc()

	player = GetMoviePlayer(False, False).value
	printDBG('[E2iPlayer web] play on TV [%s] player[%s]' % (title, player))
	session.nav.stopService()
	if player == 'mini':
		from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVMiniMoviePlayer
		session.openWithCallback(_closed, IPTVMiniMoviePlayer, url, title)
	elif player == 'standard':
		from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVStandardMoviePlayer
		session.openWithCallback(_closed, IPTVStandardMoviePlayer, url, title)
	else:
		from Plugins.Extensions.IPTVPlayer.components.iptvextmovieplayer import IPTVExtMoviePlayer
		if player == 'extgstplayer':
			playerVal = 'gstplayer'
			params.update({'download-buffer-path': '', 'ring-buffer-max-size': 0, 'buffer-duration': 18000, 'buffer-size': 10240})
		else:
			playerVal = 'eplayer'
		session.openWithCallback(_closed, IPTVExtMoviePlayer, url, title, None, playerVal, params)
	v['notices'] = [_('"%s" is playing on the TV.') % title]
	return ''


def _download(index):
	from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
	v = _view()
	if v['view'] != 'links' or not 0 <= index < len(v['links']):
		raise WebActionError(_('The list has changed, please try again.'))
	url = urlparser.decorateUrl(v['links'][index].url)
	if not IsUrlDownloadable(url):
		raise WebActionError(_("File can not be downloaded. Protocol [%s] is unsupported") % url.meta.get('iptv_proto', ''))
	title = v['linksTitle'] or 'download'
	for char in '/:*?"<>|':
		title = title.replace(char, '-')
	fullFilePath = config.plugins.iptvplayer.DownloadsDir.value + '/' + title + getFileExt(url, v['linksType'])
	dm = getDownloadManager(True)
	if not dm.addToDQueue(DMItem(url, fullFilePath)):
		raise WebActionError(_("File [%s] is already in the downloading queue.") % title)
	text = _("File [%s] has been added to the downloading queue.") % title
	if not dm.isRunning():
		text += '\n' + _('The download manager is stopped, start it on the download page.')
	v['notices'].append(text)
########################################################


def getFileExt(url, itemType):
	# same as the GUI (iptvplayerwidget.getFileExt)
	fmt = url.meta.get('iptv_format', '')
	if fmt:
		return '.' + fmt
	protocol = url.meta.get('iptv_proto', '')
	tmp = url.lower().split('?', 1)[0]
	for ext in ['avi', 'flv', 'mp4', 'ts', 'mov', 'wmv', 'mpeg', 'mpg', 'mkv', 'vob', 'divx', 'm2ts', 'mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac']:
		if tmp.endswith('.' + ext):
			return '.' + ext
	if protocol in ['mms', 'mmsh', 'rtsp']:
		return '.wmv'
	if protocol in ['f4m', 'uds', 'rtmp']:
		return '.flv'
	return '.mp3' if itemType == CDisplayListItem.TYPE_AUDIO else '.mp4'


def getDownloadManager(create=False):
	widget = iptvplayerwidget
	if widget.gDownloadManager is None and create:
		printDBG('============ web interface: Initialize Download Manager ============')
		widget.gDownloadManager = IPTVDMApi(2, int(config.plugins.iptvplayer.IPTVDMMaxDownloadItem.value))
		if config.plugins.iptvplayer.IPTVDMRunAtStart.value:
			widget.gDownloadManager.runWorkThread()
	return widget.gDownloadManager
########################################################


def _toInt(value):
	try:
		return int(value)
	except Exception:
		return -1


def doAction(params):
	# returns '' or the reason the action was refused
	action = params.get('action', '')
	v = _view()
	if action == 'cancel':
		# the host stops at its next Python line - a network request that is running is waited for
		if isThreadRunning(WORKER):
			v['cancelling'] = True
			stopRunningThread(WORKER)
		return ''
	if action == 'dismiss':
		v['notices'] = []
		v['error'] = ''
		return ''
	if isThreadRunning(WORKER):
		return _('Please wait, the previous action is still running.')
	v['error'] = ''
	v['notices'] = []
	if action in ('item', 'back', 'home', 'refresh', 'search'):
		v['fav'] = None  # a pending favourite belongs to the list it came from
	if action == 'close':
		initActiveHost(None)
		settings.hostView = {}
		return ''
	if action == 'open':
		_start(action, _open, str(params.get('host', '')))
		return ''
	if action == 'openSearch':
		_start(action, _openSearch, str(params.get('host', '')), settings.GlobalSearchQuery, str(params.get('searchType', '')))
		return ''
	if not isActiveHostInitiated():
		return _('No host is open.')
	if action == 'back' and v['view'] != 'list':
		v['view'] = 'list'  # just the list below, nothing to ask the host
		return ''
	if action == 'play':
		try:
			return playOnTv(_toInt(params.get('index')))
		except Exception as e:
			printExc()
			return str(e)
	if action == 'favouriteCancel':
		v['fav'] = None
		return ''
	actions = {'item': (_selectItem, _toInt(params.get('index'))),
			'resolve': (_resolve, _toInt(params.get('index'))),
			'download': (_download, _toInt(params.get('index'))),
			'favourite': (_favourite, _toInt(params.get('index'))),
			'favouriteAdd': (_favouriteAdd, str(params.get('group', '')), str(params.get('newGroup', '')).strip()),
			'back': (_back,), 'home': (_home,), 'refresh': (_refresh,),
			'search': (_search, str(params.get('pattern', '')).strip(), str(params.get('searchType', '')))}
	if action not in actions:
		return _('Unknown action.')
	if action == 'search' and not actions['search'][1]:
		return _('Please enter a search text.')
	_start(action, *actions[action])
	return ''
