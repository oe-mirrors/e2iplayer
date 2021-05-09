# -*- coding: utf-8 -*-
import os
import settings
import threading
import inspect
import ctypes
import time

from webTools import *

from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu
import Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmapi import IPTVDMApi, DMItem
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import IsUrlDownloadable
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetHostsList, IsHostEnabled, SaveHostsOrderList, SortHostsList, GetLogoDir, GetHostsOrderList, getDebugMode, formatBytes, printDBG
from Components.config import config

########################################################


def _async_raise(tid, exctype):
	"""raises the exception, performs cleanup if needed"""
	if not inspect.isclass(exctype):
		raise TypeError("Only types can be raised (not instances)")
	res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
	if res == 0:
		print 'res=%d' % res
		raise ValueError("invalid thread id")
	elif res != 1:
		print 'res=%d' % res
		# """if it returns a number greater than one, you're in trouble,
		# and you should call it again with exc=NULL to revert the effect"""
		ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
		raise SystemError("PyThreadState_SetAsyncExc failed")

########################################################


class buildActiveHostsHTML(threading.Thread):
	def __init__(self, args=[]):
		''' Constructor. '''
		threading.Thread.__init__(self)
		self.name = 'buildActiveHostsHTML'
		self.args = args

	def raise_exc(self, exctype):
		"""raises the given exception type in the context of this thread"""
		_async_raise(self.ident, exctype)

	def terminate(self):
		"""raises SystemExit in the context of the given thread, which should
		cause the thread to exit silently (unless caught)"""
		self.raise_exc(SystemExit)

	def run(self):
		for hostName in SortHostsList(GetHostsList()):
			if hostName in ['localmedia', 'urllist']: # those are local hosts, nothing to do via web interface
				continue
			if not IsHostEnabled(hostName):
				continue
			# column 1 containing logo and link if available
			try:
				_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], -1)
				title = _temp.gettytul()
				_temp = None
			except Exception:
				continue # we do NOT use broken hosts!!!

			logo = getHostLogo(hostName)

			if title[:4] == 'http' and logo == "":
				try:
					hostNameWithURLandLOGO = '<br><a href="./usehost?activeHost=%s" target="_blank"><font size="2" color="#58D3F7">%s</font></a>' % (hostName, '.'.join(title.replace('://', '.').replace('www.', '').split('.')[1:-1]))
				except Exception:
					hostNameWithURLandLOGO = '<br><a href="%s" target="_blank"><font size="2" color="#58D3F7">%s</font></a>' % (title, title)
			elif title[:4] == 'http' and logo != "":
				try:
					hostNameWithURLandLOGO = '<a href="./usehost?activeHost=%s">%s</a><br><a href="%s" target="_blank"><font size="2" color="#58D3F7">%s</font></a>' % (hostName, logo, title, '.'.join(title.replace('://', '.').replace('www.', '').split('.')[1:-1]))
				except Exception, e:
					print str(e)
					hostNameWithURLandLOGO = '<a href="%s" target="_blank">%s</a><br><a href="%s" target="_blank"><font size="2" color="#58D3F7">%s</font></a>' % (title, logo, title, _('visit site'))
			elif title[:4] != 'http' and logo != "":
				hostNameWithURLandLOGO = '<a href="./usehost?activeHost=%s">%s</a><br><a href="%s" target="_blank"><font size="2" color="#58D3F7">%s</font></a>' % (hostName, logo, title, title)
			else:
				hostNameWithURLandLOGO = '<br><a>%s</a>' % (title)
			# Column 2 TBD

			#build table row
			hostHTML = '<td align="center">%s</td>' % hostNameWithURLandLOGO
			settings.activeHostsHTML[hostName] = hostHTML
########################################################


class buildtempLogsHTML(threading.Thread):
	def __init__(self, DebugFileName):
		''' Constructor. '''
		threading.Thread.__init__(self)
		self.name = 'buildtempLogsHTML'
		self.DebugFileName = DebugFileName

	def raise_exc(self, exctype):
		"""raises the given exception type in the context of this thread"""
		_async_raise(self.ident, exctype)

	def terminate(self):
		"""raises SystemExit in the context of the given thread, which should
		cause the thread to exit silently (unless caught)"""
		self.raise_exc(SystemExit)

	def run(self):
		with open(self.DebugFileName, 'r') as f:
			last_bit = f.readlines()[-settings.MaxLogLinesToShow:]
			for L in last_bit:
				if L.find('E2iPlayerWidget.__init__') > 0:
					LogText = ''
				settings.tempLogsHTML += L + '<br>\n'
########################################################


class buildConfigsHTML(threading.Thread):
	def __init__(self, args=[]):
		''' Constructor. '''
		threading.Thread.__init__(self)
		self.name = 'buildConfigsHTML'
		self.args = args

	def raise_exc(self, exctype):
		"""raises the given exception type in the context of this thread"""
		_async_raise(self.ident, exctype)

	def terminate(self):
		"""raises SystemExit in the context of the given thread, which should
		cause the thread to exit silently (unless caught)"""
		self.raise_exc(SystemExit)
	########################################################

	def buildSettingsTable(self, List1, List2, exclList, direction):  #direction = '1>2'|'2>1'
		def getCFGType(option):
			cfgtype = ''
			try:
				CFGElements = option.doException()
			except Exception, e:
				cfgtype = str(e).split("'")[1]
			return cfgtype
		########################################################
		if direction == '2>1':
			tmpList = List1
			List1 = List2
			List2 = tmpList
			tmpList = None
		tableCFG = []
		for itemL1 in List1:
			if itemL1[0] in exclList or itemL1[0] in settings.excludedCFGs:
				continue
			for itemL2 in List2:
				if itemL2[1] == itemL1[1]:
					if direction == '1>2':
						confKey = itemL1
						ConfName = itemL1[0]
						ConfDesc = itemL2[0]
					elif direction == '2>1':
						confKey = itemL2
						ConfName = itemL2[0]
						ConfDesc = itemL1[0]
					CFGtype = getCFGType(itemL1[1])
					#print ConfName, '=' , CFGtype
					if CFGtype in ['ConfigYesNo', 'ConfigOnOff', 'ConfigEnableDisable', 'ConfigBoolean']:
						if int(confKey[1].getValue()) == 0:
							CFGElements = '<input type="radio" name="cmd" value="ON:%s">%s</input>' % (ConfName, _('Yes'))
							CFGElements += '<input type="radio" name="cmd" value="OFF:%s" checked="checked">%s</input>' % (ConfName, _('No'))
						else:
							CFGElements = '<input type="radio" name="cmd" value="ON:%s" checked="checked">%s</input>' % (ConfName, _('Yes'))
							CFGElements += '<input type="radio" name="cmd" value="OFF:%s">%s</input>' % (ConfName, _('No'))
					elif CFGtype in ['ConfigInteger']:
						CFGElements = '<input type="number" name="%s" value="%d" />' % ('INT:' + ConfName, int(confKey[1].getValue()))
					else:
						try:
							CFGElements = confKey[1].getHTML('CFG:' + ConfName)
						except Exception, e:
							CFGElements = 'ERROR:%s' % str(e)
					tableCFG.append([ConfName, ConfDesc, CFGElements])
		return tableCFG
	########################################################

	def run(self):
		usedCFG = []
		#configs for hosts
		for hostName in SortHostsList(GetHostsList()):
			# column 1 containing logo and link if available
			try:
				_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], -1)
				title = _temp.gettytul()
			except Exception:
				continue # we do NOT use broken hosts!!!
			usedCFG.append("host%s" % hostName)

			logo = getHostLogo(hostName)
			if logo == "":
				logo = title

			if title[:4] == 'http':
				hostNameWithURLandLOGO = '<a href="%s" target="_blank">%s</a>' % (title, logo)
			else:
				hostNameWithURLandLOGO = '<a>%s</a>' % (logo)
			# Column 2 TBD

			# Column 3 enable/disable host in GUI
			if IsHostEnabled(hostName):
				OnOffState = formSUBMITvalue([('cmd', 'OFF:host' + hostName)], _('Disable'))
			else:
				OnOffState = formSUBMITvalue([('cmd', 'ON:host' + hostName)], _('Enable'))

			# Column 4 host configuration options
			try:
				_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['GetConfigList'], -1)
				OptionsList = _temp.GetConfigList()
			except Exception:
				OptionsList = []

			#build table row
			hostsCFG = '<tr>'
			hostsCFG += '<td style="width:120px">%s</td>' % hostNameWithURLandLOGO
			hostsCFG += '<td>%s</td>' % OnOffState
			if len(OptionsList) == 0:
				hostsCFG += '<td><a>%s</a></td>' % "" # _('Host does not have configuration options')
			else:
				hostsCFG += '<td><table border="1" style="width:100%">'
				for item in self.buildSettingsTable(List2=OptionsList, List1=config.plugins.iptvplayer.dict().items(), exclList=usedCFG, direction='2>1'):
					usedCFG.append(item[0])
					#print 'hostsCFG:',item[0], item[1],item[2]
					if item[0] == 'fake_separator':
						hostsCFG += '<tr><td colspan="2" align="center"><tt>%s</tt></td></tr>\n' % (item[1])
					else:
						hostsCFG += '<tr><td nowrap style="width:50%%"><tt>%s</tt></td><td>%s</td></tr>\n' % (item[1], formGET(item[2]))
				hostsCFG += '</table></td>'
			hostsCFG += '</tr>\n'
			settings.configsHTML[hostName] = hostsCFG
		#now configs for plugin
		OptionsList = []
		ConfigMenu.fillConfigList(OptionsList, hiddenOptions=False)
		for item in self.buildSettingsTable(List1=config.plugins.iptvplayer.dict().items(), List2=OptionsList, exclList=usedCFG, direction='2>1'):
			settings.configsHTML[item[1]] = '<tr><td><tt>%s</tt></td><td>%s</td></tr>\n' % (item[1], formGET(item[2]))
########################################################


class doUseHostAction(threading.Thread):
	def __init__(self, key, arg, searchType):
		''' Constructor. '''
		threading.Thread.__init__(self)
		self.name = 'doUseHostAction'
		self.key = key
		self.arg = arg
		self.searchType = searchType

	def raise_exc(self, exctype):
		"""raises the given exception type in the context of this thread"""
		_async_raise(self.ident, exctype)

	def terminate(self):
		"""raises SystemExit in the context of the given thread, which should
		cause the thread to exit silently (unless caught)"""
		self.raise_exc(SystemExit)

	def run(self):
		print "doUseHostAction received: '%s'='%s'" % (self.key, str(self.arg))
		if self.key == 'activeHost' and isActiveHostInitiated() == False:
			initActiveHost(self.arg)
		elif self.key == 'activeHost' and self.arg != settings.activeHost['Name']:
			initActiveHost(self.arg)
		elif self.key == 'cmd' and self.arg == 'RefreshList':
			settings.retObj = settings.activeHost['Obj'].getCurrentList()
			settings.activeHost['ListType'] = 'ListForItem'
			settings.currItem = {}
		elif self.key == 'DownloadURL' and self.arg.isdigit():
			myID = int(self.arg)
			url = settings.retObj.value[myID].url
			if url != '' and IsUrlDownloadable(url):
				titleOfMovie = settings.currItem['itemTitle'].replace('/', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', '-').replace('<', '-').replace('>', '-').replace('|', '-')
				fullFilePath = config.plugins.iptvplayer.NaszaSciezka.value + '/' + titleOfMovie + '.mp4'
				if None == Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager:
					printDBG('============webThreads.py Initialize Download Manager============')
					Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager = IPTVDMApi(2, int(config.plugins.iptvplayer.IPTVDMMaxDownloadItem.value))
				ret = Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget.gDownloadManager.addToDQueue(DMItem(url, fullFilePath))
				#print ret
		elif self.key == 'ResolveURL' and self.arg.isdigit():
			myID = int(self.arg)
			url = "NOVALIDURLS"
			linkList = []
			ret = settings.activeHost['Obj'].getResolvedURL(settings.retObj.value[myID].url)
			if ret.status == RetHost.OK and isinstance(ret.value, list):
				for item in ret.value:
					if isinstance(item, CUrlItem):
						item.urlNeedsResolve = 0 # protection from recursion
						linkList.append(item)
					elif isinstance(item, basestring):
						linkList.append(CUrlItem(item, item, 0))
					else:
						print "selectResolvedVideoLinks: wrong resolved url type!"
				settings.retObj = RetHost(RetHost.OK, value=linkList)
			else:
				print "selectResolvedVideoLinks: wrong status or value"

		elif self.key == 'ListForItem' and self.arg.isdigit():
			myID = int(self.arg)
			settings.activeHost['selectedItemType'] = settings.retObj.value[myID].type
			if settings.activeHost['selectedItemType'] in ['CATEGORY']:
				settings.activeHost['Status'] += '>' + settings.retObj.value[myID].name
				settings.currItem = {}
				settings.retObj = settings.activeHost['Obj'].getListForItem(myID, 0, settings.retObj.value[myID])
				settings.activeHost['PathLevel'] += 1
			elif settings.activeHost['selectedItemType'] in ['VIDEO']:
				settings.currItem['itemTitle'] = settings.retObj.value[myID].name
				try:
					links = settings.retObj.value[myID].urlItems
				except Exception, e:
					print "ListForItem>urlItems exception:", str(e)
					links = 'NOVALIDURLS'
				try:
					settings.retObj = settings.activeHost['Obj'].getLinksForVideo(myID, settings.retObj.value[myID]) #returns "NOT_IMPLEMENTED" when host is using curlitem
				except Exception, e:
					print "ListForItem>getLinksForVideo exception:", str(e)
					settings.retObj = RetHost(RetHost.NOT_IMPLEMENTED, value=[])

				if settings.retObj.status == RetHost.NOT_IMPLEMENTED and links != 'NOVALIDURLS':
					print "getLinksForVideo not implemented, using CUrlItem"
					tempUrls = []
					iindex = 1
					for link in links:
						if link.name == '':
							tempUrls.append(CUrlItem('link %d' % iindex, link.url, link.urlNeedsResolve))
						else:
							tempUrls.append(CUrlItem(link.name, link.url, link.urlNeedsResolve))
						iindex += 1
					settings.retObj = RetHost(RetHost.OK, value=tempUrls)
				elif settings.retObj.status == RetHost.NOT_IMPLEMENTED:
					settings.retObj = RetHost(RetHost.NOT_IMPLEMENTED, value=[(CUrlItem("No valid urls", "fakeUrl", 0))])
		elif self.key == 'ForSearch' and None is not self.arg and self.arg != '':
			settings.retObj = settings.activeHost['Obj'].getSearchResults(self.arg, self.searchType)
		elif self.key == 'activeHostSearchHistory' and self.arg != '':
			initActiveHost(self.arg)
			settings.retObj = settings.activeHost['Obj'].getSearchResults(settings.GlobalSearchQuery, '')
########################################################


class doGlobalSearch(threading.Thread):
	def __init__(self):
		''' Constructor. '''
		threading.Thread.__init__(self)
		self.name = 'doGlobalSearch'
		settings.searchingInHost = None
		self.host = None
		settings.GlobalSearchResults = {}
		settings.StopThreads = False
		print 'doGlobalSearch:init'

	def raise_exc(self, exctype):
		"""raises the given exception type in the context of this thread"""
		_async_raise(self.ident, exctype)

	def terminate(self):
		"""raises SystemExit in the context of the given thread, which should
		cause the thread to exit silently (unless caught)"""
		self.raise_exc(SystemExit)

	def stopIfRequested(self):
		if settings.StopThreads == True:
			self.terminate()

	def run(self):
		if settings.GlobalSearchQuery == '':
			print "End settings.GlobalSearchQuery is empty"
			return
		for hostName in SortHostsList(GetHostsList()):
			self.stopIfRequested()
			if hostName in ['localmedia', 'urllist']: # those are local hosts, nothing to do via web interface
				continue
                        elif hostName in ['localmedia', 'urllist']: # those are local hosts, nothing to do via web interface
                                continue
			elif hostName in ['seriesonline']: # those hosts have issues wth global search, need more investigation
				continue
			elif not IsHostEnabled(hostName):
				continue
			#print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ---------------- %s ---------------- !!!!!!!!!!!!!!!!!!!!!!!!!" % hostName
			try:
				_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], -1)
			except Exception:
				print "doGlobalSearch: Exception importing %s" % hostName
				continue
			try:
				self.host = _temp.IPTVHost()
			except Exception, e:
				print "doGlobalSearch: Exception initializing iptvhost for %s: %s" % (hostName, str(e))
				continue
			#print "settings.GlobalSearchQuery=",settings.GlobalSearchQuery, 'hostName=', hostName
			settings.searchingInHost = hostName
			time.sleep(0.2) #
			try:
				self.host.getSupportedFavoritesTypes()
				ret = self.host.getInitList()
				searchTypes = self.host.getSearchTypes()
			except Exception, e:
				print "doGlobalSearch: Exception in getInitList for %s: %s" % (hostName, str(e))
				settings.hostsWithNoSearchOption.append(hostName)
				continue
			if len(searchTypes) == 0:
				ret = self.host.getSearchResults(settings.GlobalSearchQuery, '')
				self.stopIfRequested()
				if len(ret.value) > 0:
					settings.GlobalSearchResults[hostName] = (None, ret.value)
			else:
				for SearchType in searchTypes:
					ret = self.host.getSearchResults(settings.GlobalSearchQuery, SearchType[1])
					self.stopIfRequested()
					print SearchType[1], ' searched ', ret.value

		settings.searchingInHost = None
