# -*- coding: utf-8 -*-
# State of the web interface. There is one state for the box: every browser tab sees the same host
# session and search. "Reset web interface" (Information page) puts everything back to these values.

WebInterfaceVersion = '1.0'
excludedCFGs = ['fakeUpdate', 'fakeHostsList', 'fakExtMoviePlayerList']

# host session (webHost.py)
activeHost = {}
retObj = None
currItem = {}
hostView = {}

# global search (webThreads.doGlobalSearch)
GlobalSearchQuery = ''
GlobalSearchResults = []
GlobalSearchProgress = {'done': 0, 'total': 0}
searchingInHost = None
hostsWithNoSearchOption = []

StopThreads = False

# a setting that needs a GUI restart was changed from the web interface
restartPending = False

# the enigma2 session (plugin.py sessionstart) - needed to work off the main thread queue (webThreads.py)
session = None
