# -*- coding: utf-8 -*-
# HTML of the web interface pages. The pages are a frame: menu, a container and the texts the
# script needs; assets/e2i.js fills them through the JSON interface (webApi.py).

import json

from . import settings
from .webTools import htmlEscape, isActiveHostInitiated, hostDisplayTitle

from Plugins.Extensions.IPTVPlayer.version import IPTV_VERSION
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Components.Language import language

########################################################

# texts assets/e2i.js shows, translated on the box
JS_TEXTS = [
	'Loading data, please wait', 'Please wait', 'Cancel', 'Save', 'Saved', 'Error', 'Close', 'Yes', 'No', 'OK',
	'Search', 'Search text', 'Search in all active hosts', 'Searching in %s', 'Searching, please wait',
	'%d of %d hosts', 'No results.', 'Stop', 'Only exact matches', 'Folders', 'Videos', 'Music', 'All materials',
	'Cancelling - waiting for the host to finish its current request', 'Back', 'Initial list', 'Reload list', 'Return to hosts list', 'Links for', 'Select', 'Watch', 'Add to downloader',
	'Copy link', 'Link copied', 'Description', 'No host is open.', 'Open a host from the host list.',
	'Filter', 'No hosts are enabled.', 'The whole plugin is protected by a PIN - hosts can only be used on the receiver.',
	'Protected by PIN', 'entries', 'Open in host',
	'Pause', 'Resume', 'Follow', 'Clear view', 'Only errors and warnings', 'Download log file', 'Delete log file',
	'Delete the debug log file?', 'Debug file has been deleted', 'Debug option is disabled - nothing to display',
	'Debug option set to console - nothing to display', 'Debug file does not exist yet, waiting for it',
	'The log file was started again.', 'lines',
	'Hosts', 'Enabled', 'Options', 'only on the receiver', 'The value must be between %d and %d.',
	'The settings are protected by a PIN on the receiver - here they can only be viewed.',
	'Filter settings', 'Nothing found.', '(unchanged - type a new one to change it)',
	'Download manager is not initialized', 'Initialize Download Manager', 'Start', 'Manager status:', 'STARTED', 'STOPPED',
	'Downloads', 'Archive', 'No materials waiting in the downloader queue', 'Nothing has been downloaded yet.',
	'PENDING', 'DOWNLOADING', 'DOWNLOADED', 'ABORTED', 'DOWNLOAD ERROR', 'POSTPROCESSING',
	'Stop download', 'Resume download', 'Download again', 'Delete', 'Remove from queue', 'Move to top', 'Delete the file %s?',
	'Up to date', '%d commits behind %s', 'Installed version %s has no release tag (local build?)', 'Update check not possible',
	'New since the installed version', 'Checking for updates',
	'Play on TV', 'Add to favourites', 'Add "%s" to the favourites', 'Favourites group', 'New group', 'Name of the new group',
	'Recent searches', 'Groups', 'Add link', 'Link (http:// or https://)', 'File name (optional)', 'has been added to the downloading queue.',
	'The download manager is stopped, start it on the download page.', 'Older log files', 'Support package',
	'needs a GUI restart', 'Some settings will be applied only after GUI restart.', 'Restart GUI now', 'Restart GUI',
	'Restart the enigma2 GUI now? Running recordings, playbacks and downloads are stopped.', 'The GUI is restarting ...',
	'Web interface has been reset.', 'Still running:', 'Reading...',
]


def jsTexts():
	return dict((text, _(text)) for text in JS_TEXTS)
########################################################


def menu(pageId):
	entries = [('info', '/iptvplayer/', _('Information')),
			('hosts', '/iptvplayer/hosts', _('Hosts'))]
	if isActiveHostInitiated():
		entries.append(('usehost', '/iptvplayer/usehost', '▶ ' + hostDisplayTitle(settings.activeHost.get('Title', ''))[:30]))
	entries += [('search', '/iptvplayer/search', _('Search')),
				('downloader', '/iptvplayer/downloader', _('Download manager')),
				('settings', '/iptvplayer/settings', _('Settings')),
				('logs', '/iptvplayer/logs', _('Logs'))]
	links = []
	for entryId, href, label in entries:
		cls = []
		if entryId == pageId:
			cls.append('active')
		if entryId == 'usehost':
			cls.append('hostlink')
		links.append('<a href="%s" class="%s">%s</a>' % (href, ' '.join(cls), htmlEscape(label)))
	return """<header class="topbar">
	<a class="brand" href="/iptvplayer/"><img src="/iptvplayer/icons/HD/iptvlogo.png" alt="E2iPlayer"></a>
	<nav>%s</nav>
	<span class="ver">E2iPlayer %s</span>
	<button class="themebtn" id="themeToggle" type="button" title="%s" aria-label="%s">&#9788;</button>
</header>""" % ('\n\t\t'.join(links), htmlEscape(IPTV_VERSION), htmlEscape(_('Light / dark design')), htmlEscape(_('Light / dark design')))


def page(pageId, title, content):
	config = {'page': pageId, 'version': IPTV_VERSION, 'txt': jsTexts()}
	return """<!DOCTYPE html>
<html lang="%(lang)s">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>E2iPlayer - %(title)s</title>
	<link rel="stylesheet" href="/iptvplayer/assets/e2i.css?v=%(ver)s">
	<script>(function () { var t = null; try { t = localStorage.getItem('e2i.theme'); } catch (e) {}
		if (t !== 'light' && t !== 'dark') { t = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'; }
		document.documentElement.setAttribute('data-theme', t); })();</script>
</head>
<body data-page="%(page)s">
%(menu)s
<main>
%(content)s
</main>
<div id="toast"></div>
<script>window.E2I = %(config)s;</script>
<script src="/iptvplayer/assets/e2i.js?v=%(ver)s"></script>
</body>
</html>
""" % {'lang': htmlEscape(language.getLanguage()[:2]), 'title': htmlEscape(title), 'ver': htmlEscape(IPTV_VERSION), 'page': pageId,
		'menu': menu(pageId), 'content': content, 'config': json.dumps(config).replace('</', '<\\/')}
########################################################


def _kvSections(text):
	# "--- Title ---" / "label|value" lines of the info view's system text as HTML
	html = []
	open_ = False
	for line in text.split('\n'):
		line = line.rstrip()
		if not line:
			continue
		if line.startswith('---') and line.endswith('---'):
			if open_:
				html.append('</dl>')
			html.append('<div class="kv-title">%s</div><dl class="kv">' % htmlEscape(line.strip('- ')))
			open_ = True
		elif '|' in line:
			if not open_:
				html.append('<dl class="kv">')
				open_ = True
			label, value = line.split('|', 1)
			html.append('<dt>%s</dt><dd>%s</dd>' % (htmlEscape(label), htmlEscape(value)))
	if open_:
		html.append('</dl>')
	return '\n'.join(html)


WIKI_PAGES = [('Install E2iPlayer', 'Install'),
			('Create debug logs', 'How-to-create-debug-logs'),
			('Solve Cloudflare, hCaptcha and reCAPTCHA with MyE2i', 'Solve-Cloudflare-hCaptcha-reCAPTCHA-with-MyE2i'),
			('Solve Google reCAPTCHA v2 with My JDownloader', 'Solve-Google-reCAPTCHA-v2')]


def infoPage():
	from Plugins.Extensions.IPTVPlayer.components.iptvplayerinfoview import aboutBlocks, _SystemInfo
	about = []
	for head, body in aboutBlocks():
		body = htmlEscape(body).replace('\n', '<br>')
		if body.startswith('https://'):
			body = '<a href="%s" target="_blank" rel="noopener">%s</a>' % (body, body)
		about.append('<dt>%s</dt><dd>%s</dd>' % (htmlEscape(head.rstrip(':')), body))
	try:
		systemHtml = _kvSections(_SystemInfo().buildSystemText(withBinaries=False))
	except Exception as e:
		systemHtml = '<p class="muted">%s</p>' % htmlEscape(str(e))
	wiki = ''.join('<li><a href="https://github.com/oe-mirrors/e2iplayer/wiki/%s" target="_blank" rel="noopener">%s</a></li>'
				% (page_, htmlEscape(_(title))) for title, page_ in WIKI_PAGES)
	return """
<h1>%(title)s</h1>
<div class="grid">
	<div class="card">
		<h2>E2iPlayer</h2>
		<dl class="kv">%(about)s</dl>
		<p class="muted">%(remember)s</p>
	</div>
	<div class="card">
		<h2>%(updates)s</h2>
		<div id="updates" class="muted"><span class="spinner"></span> %(checking)s</div>
	</div>
	<div class="card">
		<h2>%(system)s</h2>
		%(systemHtml)s
		<div class="kv-title">%(binaries)s</div>
		<pre id="binaries" class="plain muted">%(reading)s</pre>
	</div>
	<div class="card">
		<h2>%(help)s</h2>
		<ul class="plain">%(wiki)s
			<li><a href="https://github.com/oe-mirrors/e2iplayer/issues" target="_blank" rel="noopener">%(issues)s</a></li>
			<li><a href="https://www.opena.tv/viewtopic.php?t=42312" target="_blank" rel="noopener">%(forum)s</a></li>
		</ul>
	</div>
	<div class="card">
		<h2>%(trouble)s</h2>
		<p class="muted">%(resetText)s</p>
		<button class="btn" id="resetBtn">%(reset)s</button>
		<div id="resetResult" class="muted" style="margin-top:8px"></div>
		<p class="muted">%(supportText)s</p>
		<div class="toolbar"><a class="btn" href="/iptvplayer/logs?cmd=support">%(support)s</a>
			<button class="btn danger" id="restartBtn">%(restart)s</button></div>
	</div>
</div>
""" % {'title': htmlEscape(_('Information')), 'about': '\n'.join(about),
		'remember': htmlEscape(_('E2iPlayer is only a specialized web browser. It does not host any materials.')),
		'updates': htmlEscape(_('Updates')), 'checking': htmlEscape(_('Checking for updates')),
		'system': htmlEscape(_('System')), 'systemHtml': systemHtml, 'binaries': htmlEscape(_('Binaries')), 'reading': htmlEscape(_('Reading...')),
		'help': htmlEscape(_('Help')), 'wiki': wiki, 'issues': htmlEscape(_('Report a problem (GitHub issues)')),
		'forum': htmlEscape(_('Support forum (opena.tv)')),
		'trouble': htmlEscape(_('Troubleshooting')), 'reset': htmlEscape(_('Reset web interface')),
		'support': htmlEscape(_('Support package')), 'restart': htmlEscape(_('Restart GUI')),
		'supportText': htmlEscape(_('The support package holds the versions, the system information, the enabled hosts and the end of the '
									'debug log in one text file for a problem report. Look through it before posting it - the log can '
									'contain addresses of the sites you opened.')),
		'resetText': htmlEscape(_('Closes the host opened in the web interface, clears the search results and stops what the web interface '
								'still runs in the background. Use it when a page keeps loading. Settings, downloads and the E2iPlayer '
								'on the TV are not touched.'))}
########################################################


def hostsPage():
	return """
<div class="toolbar"><h1 style="margin:0">%s</h1><span class="spacer"></span>
	<input type="search" id="hostFilter" placeholder="%s"></div>
<div id="hostsMsg"></div>
<div class="toolbar" id="hostGroups"></div>
<div id="hosts" class="hostgrid"><div class="empty"><span class="spinner"></span></div></div>
""" % (htmlEscape(_('Hosts')), htmlEscape(_('Filter')))


def useHostPage():
	return '<div id="host"><div class="empty"><span class="spinner"></span></div></div>'


def searchPage():
	return """
<h1>%s</h1>
<form id="searchForm" class="searchform card">
	<input type="search" id="searchText" placeholder="%s" value="%s">
	<button class="btn primary" type="submit">%s</button>
	<button class="btn hidden" type="button" id="searchStop">%s</button>
</form>
<div id="searchStatus"></div>
<div class="toolbar" id="searchFilters"></div>
<div id="searchResults"></div>
""" % (htmlEscape(_('Search in all active hosts')), htmlEscape(_('Search text')), htmlEscape(settings.GlobalSearchQuery),
		htmlEscape(_('Search')), htmlEscape(_('Stop')))


def downloaderPage():
	return """
<div class="toolbar"><h1 style="margin:0">%s</h1><span class="spacer"></span><span id="dmStatus"></span></div>
<div class="toolbar" id="dmToolbar"></div>
<form class="searchform card" id="dmAdd"></form>
<div id="dmList"><div class="empty"><span class="spinner"></span></div></div>
""" % htmlEscape(_('Download manager'))


def settingsPage():
	return """
<div class="toolbar"><h1 style="margin:0">%s</h1><span class="spacer"></span>
	<input type="search" id="settingsFilter" placeholder="%s"></div>
<div id="settingsMsg"></div>
<div id="settings"><div class="empty"><span class="spinner"></span></div></div>
""" % (htmlEscape(_('Settings')), htmlEscape(_('Filter settings')))


def logsPage():
	return """
<div class="toolbar">
	<h1 style="margin:0">%s</h1>
	<span class="spacer"></span>
	<span id="logInfo" class="muted"></span>
</div>
<div class="toolbar" id="logToolbar"></div>
<div id="logMsg"></div>
<div id="log" class="logbox"></div>
<div class="toolbar" id="logFiles" style="margin-top:12px"></div>
""" % htmlEscape(_('Logs'))
