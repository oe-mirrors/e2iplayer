# -*- coding: utf-8 -*-


import os
import re
import time
import threading
import urllib.parse
from html import escape as _html_escape

from . import settings
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetPluginDir, IsSameOrSubDir
########################################################


def htmlEscape(value):
	# text from hosts, web pages, file names and logs must never be taken as HTML by the browser
	try:
		return _html_escape(value if isinstance(value, str) else str(value), quote=True)
	except Exception:
		return ''
########################################################


_COLOR_TAG_RE = re.compile(r'\\c[0-9a-fA-F]{8}|\[/?color[^\]]*\]', re.I)


def cleanText(text, multiLine=False):
	# host titles and descriptions for display: E2 colour markup out, HTML entities the hosts left in
	# decoded, line breaks only where wanted
	try:
		text = text if isinstance(text, str) else str(text)
	except Exception:
		return ''
	text = _COLOR_TAG_RE.sub('', text)
	text = text.replace('[/br]', '\n').replace('\r', '')
	text = text.replace('&quot;', '"').replace('&#34;', '"').replace('&nbsp;', ' ').replace('&#160;', ' ')
	text = text.replace('&oacute;', 'ó').replace('&Oacute;', 'Ó').replace('&amp;', '&')
	if not multiLine:
		text = ' '.join(text.split())
	else:
		text = '\n'.join(' '.join(line.split()) for line in text.split('\n')).strip()
	return text
########################################################


_TYPE_ICONS = {'CATEGORY': 'CategoryItem.png', 'VIDEO': 'VideoItem.png', 'AUDIO': 'AudioItem.png', 'SEARCH': 'SearchItem.png',
               'ARTICLE': 'ArticleItem.png', 'PICTURE': 'PictureItem.png', 'MORE': 'MoreItem.png', 'MARKER': 'MarkerItem.png',
               'DATA': 'DataItem.png'}


def iconUrl(icon, itemType=''):
	# remote icons go to the browser as they are, the plugin's own ones through /iptvplayer/icons
	try:
		icon = icon if isinstance(icon, str) else str(icon)
	except Exception:
		icon = ''
	if icon.startswith('http://') or icon.startswith('https://'):
		return icon
	iconsDir = GetPluginDir('icons/')
	if icon and icon.startswith(iconsDir) and os.path.isfile(icon):
		return '/iptvplayer/icons/' + urllib.parse.quote(icon[len(iconsDir):])
	return typeIconUrl(itemType)


def typeIconUrl(itemType):
	name = _TYPE_ICONS.get(itemType, '')
	return ('/iptvplayer/icons/' + name) if name else ''


def hostDisplayTitle(title):
	# hosts named by their address: "https://www.site.example/" -> "site"
	title = cleanText(title)
	if title.startswith('http'):
		return '.'.join(title.replace('://', '.').replace('www.', '').split('.')[1:-1]) or title
	return title


def hostLogoUrl(hostName):
	if os.path.isfile(GetPluginDir('icons/logos/%slogo.png' % hostName)):
		return '/iptvplayer/icons/logos/%slogo.png' % hostName
	return ''
########################################################


def isDownloadsFile(path):
	# a file inside the downloads folder - paths in requests are never trusted beyond that
	try:
		from Components.config import config
		return bool(path) and os.path.isfile(path) and IsSameOrSubDir(path, config.plugins.iptvplayer.DownloadsDir.value)
	except Exception:
		return False


def fileDownloadLocation(path):
	# OpenWebif's own file download handler
	return "/file?action=download&file=%s" % urllib.parse.quote(path)
########################################################


def getHostTitle(hostName):
	try:
		_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], 0)
		return _temp.gettytul()
	except Exception:
		return None
########################################################


def initActiveHost(hostName):
	settings.activeHost = {}
	settings.retObj = None
	settings.currItem = {}

	if hostName is None:
		return False
	if not isHostUsableFromWeb(hostName):
		print('[E2iPlayer web] host "%s" refused: not enabled, unknown or PIN protected' % hostName)
		return False
	_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], 0)
	hostObj = _temp.IPTVHost()
	if hostObj.isProtectedByPinCode():
		# the web interface has no way to ask for the PIN - such hosts stay GUI only
		print('[E2iPlayer web] host "%s" refused: PIN protected' % hostName)
		return False
	settings.activeHost['Name'] = hostName
	settings.activeHost['Title'] = _temp.gettytul()
	settings.activeHost['Obj'] = hostObj
	settings.activeHost['SupportedTypes'] = hostObj.getSupportedFavoritesTypes().value
	settings.retObj = hostObj.getInitList()
	settings.activeHost['SearchTypes'] = hostObj.getSearchTypes()
	return True
########################################################


# PIN settings are never changed from the web interface
_WEB_LOCKED_CONFIG_NAMES = ('pin', 'fakePin', 'pluginProtectedByPin', 'configProtectedByPin', 'configOwnPin', 'configPincode',
                            'fakeConfigPin', 'xxxownpin', 'xxxpincode', 'xxxwymagajpin', 'xxx_pin_action')


def isLockedConfigName(name):
	return name in _WEB_LOCKED_CONFIG_NAMES or name in settings.excludedCFGs


def getEditableConfigNames():
	# names (config.plugins.iptvplayer.<name>) of the options the settings page shows: the host on/off
	# switches, the global settings and the hosts' own options
	from Components.config import config
	from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu
	from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetHostsList
	namesById = dict((id(value), name) for name, value in config.plugins.iptvplayer.dict().items())
	names = set()
	entries = []
	ConfigMenu.fillConfigList(entries)
	for hostName in GetHostsList():
		names.add('host' + hostName)
		try:
			_temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['GetConfigList'], 0)
			entries.extend(_temp.GetConfigList())
		except Exception:
			pass
	for item in entries:
		if len(item) > 1 and id(item[1]) in namesById:
			names.add(namesById[id(item[1])])
	return set(name for name in names if not isLockedConfigName(name))


def isEditableConfigName(name):
	try:
		return name in getEditableConfigNames()
	except Exception as e:
		print('EXCEPTION in webTools:isEditableConfigName - ', str(e))
	return False
########################################################


def isPluginPinProtected():
	try:
		from Components.config import config
		return bool(config.plugins.iptvplayer.pluginProtectedByPin.value)
	except Exception:
		return False


def isConfigPinProtected():
	# the settings are behind a PIN on the box - the web interface then only shows them
	try:
		from Components.config import config
		return bool(config.plugins.iptvplayer.configProtectedByPin.value or config.plugins.iptvplayer.pluginProtectedByPin.value)
	except Exception:
		return False


def isHostUsableFromWeb(hostName):
	# only enabled hosts of the host list, same as the host overview shows; the whole player
	# behind a PIN means no host browsing from the web interface at all
	try:
		from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetHostsList, IsHostEnabled
		if isPluginPinProtected():
			return False
		return hostName in GetHostsList() and IsHostEnabled(hostName)
	except Exception as e:
		print('EXCEPTION in webTools:isHostUsableFromWeb - ', str(e))
	return False
########################################################


def isActiveHostInitiated():
	try:
		return len(settings.activeHost) > 0
	except Exception:
		return False
########################################################


def isThreadRunning(name):
	for i in threading.enumerate():
		if name == i.name and i.is_alive():
			return True
	return False
########################################################


def stopRunningThread(name):
	settings.StopThreads = True
	for myThread in threading.enumerate():
		if name == myThread.name and myThread.is_alive():
			try:
				myThread.terminate()
			except Exception as e:
				print('EXCEPTION in webTools:stopRunningThread - ', str(e))
	time.sleep(0.2)  # time for thread to close
	return isThreadRunning(name)
