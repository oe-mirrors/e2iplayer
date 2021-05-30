# -*- coding: utf-8 -*-

WebInterfaceVersion = '0.9'
MaxLogLinesToShow = 1000
excludedCFGs = ['fakeUpdate', 'fakeHostsList', 'fakExtMoviePlayerList']
activeHost = {}
activeHostsHTML = {}
currItem = {}
retObj = None

configsHTML = {}
tempLogsHTML = ''
NewHostListShown = True

StopThreads = False

hostsWithNoSearchOption = []
GlobalSearchListShown = True
GlobalSearchTypes = ["VIDEO"]
GlobalSearchQuery = ''
GlobalSearchResults = {}
searchingInHost = None
