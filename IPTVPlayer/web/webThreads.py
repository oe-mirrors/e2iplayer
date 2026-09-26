# -*- coding: utf-8 -*-


from . import settings
import threading
import inspect
import ctypes

from .webTools import isHostUsableFromWeb, getHostTitle, hostLogoUrl, hostDisplayTitle

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetHostsList, SortHostsList, printExc

########################################################


def _async_raise(tid, exctype):
	"""raises the exception, performs cleanup if needed"""
	if not inspect.isclass(exctype):
		raise TypeError("Only types can be raised (not instances)")
	res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(exctype))
	if res == 0:
		raise ValueError("invalid thread id")
	elif res != 1:
		# """if it returns a number greater than one, you're in trouble,
		# and you should call it again with exc=NULL to revert the effect"""
		ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), None)
		raise SystemError("PyThreadState_SetAsyncExc failed")

########################################################


class WebThread(threading.Thread):
	# a thread the web interface runs host code in. Messages a host would open on the TV land in
	# self.e2iWebNotices instead (components/asynccall.py MainSessionWrapper)
	def __init__(self, name):
		threading.Thread.__init__(self)
		self.name = name
		self.daemon = True
		self.e2iWebNotices = []
		# what asynccall.AsyncCall gives the GUI's worker threads: without it IsThreadTerminated() says
		# "terminated" and pCommon's PyCurl requests are never sent
		self._iptvplayer_ext = {'kill_lock': threading.Lock(), 'killable': True, 'terminated': False, 'iptv_execute': None}

	def start(self):
		startMainQueuePump()
		threading.Thread.start(self)

	def raise_exc(self, exctype):
		"""raises the given exception type in the context of this thread"""
		_async_raise(self.ident, exctype)

	def terminate(self):
		# like asynccall.AsyncCall.kill: a running PyCurl request stops at once (its progress callback asks
		# IsThreadTerminated); code marked not killable ends by itself at SetThreadKillable(True)
		with self._iptvplayer_ext['kill_lock']:
			killable = self._iptvplayer_ext['killable']
			self._iptvplayer_ext['terminated'] = True
		if not killable:
			return
		execute = self._iptvplayer_ext.get('iptv_execute')
		if execute is not None:
			try:
				execute.terminate()
			except Exception:
				printExc()
		self.raise_exc(SystemExit)
########################################################
# Hosts hand work to the main thread (asynccall.DelegateToMainThread: external programs, the JS
# interpreters, ...). The queue for that is only created and worked off by the E2iPlayer screen on the TV,
# so without it a web action either gets nothing back or waits forever. The web interface creates the queue
# itself when needed and works it off while its threads run and the screen does not.


def ensureMainQueue():
	# called in the main thread (web requests are handled by the enigma2 main loop)
	from Plugins.Extensions.IPTVPlayer.components import asynccall
	if asynccall.gMainFunctionsQueueTab[0] is None and settings.session is not None:
		asynccall.gMainFunctionsQueueTab[0] = asynccall.CFunctionProxyQueue(settings.session)
	return asynccall.gMainFunctionsQueueTab[0]


_pump = {'running': False}


def startMainQueuePump():
	ensureMainQueue()
	if not _pump['running']:
		_pump['running'] = True
		from twisted.internet import reactor
		reactor.callLater(0.05, _pumpMainQueue)


def _pumpMainQueue():
	from twisted.internet import reactor
	from .webTools import isThreadRunning
	queue = ensureMainQueue()
	# procFun set = the E2iPlayer screen is open and works the queue off with its own timer
	if queue is not None and queue.procFun is None:
		try:
			queue.processQueue()
		except Exception:
			printExc()
	if any(isThreadRunning(name) for name in ('doUseHostAction', 'doGlobalSearch')):
		reactor.callLater(0.1, _pumpMainQueue)
	else:
		_pump['running'] = False
########################################################


class WebActionError(Exception):
	# a message for the page, not a bug: no traceback in the debug log
	pass


class WebWorker(WebThread):
	# runs fnc(*args); onDone(error, notices) is called at the end in this thread
	def __init__(self, name, fnc, args, onDone):
		WebThread.__init__(self, name)
		self.fnc = fnc
		self.args = args
		self.onDone = onDone

	def run(self):
		error = ''
		try:
			self.fnc(*self.args)
		except SystemExit:
			error = 'cancelled'
		except WebActionError as e:
			error = str(e)
		except Exception as e:
			printExc()
			error = str(e) or e.__class__.__name__
		try:
			self.onDone(error, self.e2iWebNotices)
		except Exception:
			printExc()
########################################################


def searchItemToDict(item, index):
	from .webTools import cleanText, iconUrl
	return {'i': index, 'type': item.type, 'name': cleanText(item.name), 'desc': cleanText(item.description, True)[:400],
			'icon': iconUrl(item.iconimage, item.type)}


class doGlobalSearch(WebThread):
	def __init__(self):
		WebThread.__init__(self, 'doGlobalSearch')
		settings.searchingInHost = None
		settings.GlobalSearchResults = []
		settings.GlobalSearchProgress = {'done': 0, 'total': 0}
		settings.StopThreads = False
		self.host = None

	def stopIfRequested(self):
		if settings.StopThreads is True:
			raise SystemExit()

	def run(self):
		try:
			self._run()
		except SystemExit:
			pass
		except Exception:
			printExc()
		settings.searchingInHost = None

	def _run(self):
		if settings.GlobalSearchQuery == '':
			return
		hosts = []
		for hostName in SortHostsList(GetHostsList()):
			if hostName in ['localmedia', 'urllist', 'favourites', 'e2iplayerinfo', 'iptvplayerinfo']:  # nothing to search there
				continue
			elif hostName in ['seriesonline']:  # those hosts have issues wth global search, need more investigation
				continue
			elif not isHostUsableFromWeb(hostName):
				continue
			hosts.append(hostName)
		settings.GlobalSearchProgress = {'done': 0, 'total': len(hosts)}

		for hostName in hosts:
			self.stopIfRequested()
			settings.searchingInHost = hostDisplayTitle(getHostTitle(hostName) or hostName)
			self._searchHost(hostName)
			settings.GlobalSearchProgress['done'] += 1

	def _searchHost(self, hostName):
		try:
			_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], 0)
			self.host = _temp.IPTVHost()
		except Exception as e:
			print("doGlobalSearch: Exception initializing iptvhost for %s: %s" % (hostName, str(e)))
			return
		try:
			if self.host.isProtectedByPinCode():
				return  # PIN protected hosts are GUI only
			self.host.getSupportedFavoritesTypes()
			self.host.getInitList()
			searchTypes = self.host.getSearchTypes()
		except SystemExit:
			raise
		except Exception as e:
			print("doGlobalSearch: Exception in getInitList for %s: %s" % (hostName, str(e)))
			settings.hostsWithNoSearchOption.append(hostName)
			return
		# one entry per host: the results of every search type of the host together
		results = []
		for searchType in (searchTypes if len(searchTypes) else [('', '')]):
			try:
				ret = self.host.getSearchResults(settings.GlobalSearchQuery, searchType[1])
				if ret.value:
					results.extend(ret.value)
			except SystemExit:
				raise
			except Exception as e:
				print("doGlobalSearch: Exception in getSearchResults for %s: %s" % (hostName, str(e)))
			self.stopIfRequested()
		items = [searchItemToDict(item, idx) for idx, item in enumerate(results) if item.type not in ('SEARCH', 'MARKER', 'MORE')]
		if items:
			settings.GlobalSearchResults.append({'host': hostName, 'title': hostDisplayTitle(getHostTitle(hostName) or hostName),
												'logo': hostLogoUrl(hostName), 'searchType': searchTypes[0][1] if len(searchTypes) else '',
												'items': items})
