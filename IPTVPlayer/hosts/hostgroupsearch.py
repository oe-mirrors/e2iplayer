# -*- coding: utf-8 -*-
LAST_MODIFIED = "30.10.2026"
# 30.10.2026 - new host: one search over all hosts of a group
#   - pick a group, enter the search term: every host of the group that has a search is asked, SEARCH_WORKERS at a time
#   - one row per host with hits; OK opens that host's own result list, the host then works on as if it was opened itself
import threading
import time
try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

from Plugins.Extensions.IPTVPlayer.components.asynccall import AsyncMethod
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CDisplayListItem, CHostBase, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvhostpin import GetHostDisplayTitle, IsHostUnlocked
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import GetIPTVNotify, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvhostgroups import IPTVHostsGroups
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetHostsList, GetIconDir, IsHostEnabled, getHostsPath, printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return _("Group search")


# hosts asked at the same time
SEARCH_WORKERS = 6
# seconds one host may take, a host that does not answer must not hold the search
HOST_SECONDS = 45
# nothing to search there, no search of the common kind (hostxxx has its own over its sites), this host itself,
# YouTube (finds the term in any language and has several search types, it would swamp the result of a group)
SKIPPED_HOSTS = ('groupsearch', 'favourites', 'localmedia', 'urllist', 'e2iplayerinfo', 'iptvplayerinfo', 'seriesonline', 'xxx', 'youtube')
# rows of a result list that are no result
NO_RESULT_TYPES = (CDisplayListItem.TYPE_SEARCH, CDisplayListItem.TYPE_SEARCH_HISTORY, CDisplayListItem.TYPE_SEARCH_HISTORY_EDITOR, CDisplayListItem.TYPE_SEARCH_HISTORY_DELETE,
                   CDisplayListItem.TYPE_MARKER, CDisplayListItem.TYPE_MORE, CDisplayListItem.TYPE_NEXT)
PAGER_IMAGE_TYPES = (CDisplayListItem.TYPE_NEXT, CDisplayListItem.TYPE_FIRST, CDisplayListItem.TYPE_PREVIOUS, CDisplayListItem.TYPE_LAST, CDisplayListItem.TYPE_JUMP)
TITLES_IN_DESC = 8


def _hasSearch(hostName):
    # read from the host file, the host is not loaded for it; a host without a .py (compiled feed) is asked
    try:
        with open(getHostsPath('host%s.py' % hostName), 'rb') as f:
            return b'search' in f.read().lower()
    except Exception:
        return True


def _groupHosts(groupObj, groupName):
    if groupName == 'all':
        hosts = [hostName for hostName in GetHostsList(fromList=False, fromHostFolder=True) if IsHostEnabled(hostName)]
    else:
        hosts = groupObj.getHostsList(groupName)
    return [hostName for hostName in hosts if hostName not in SKIPPED_HOSTS]


def _isResult(item):
    return item.type not in NO_RESULT_TYPES and item.imageType not in PAGER_IMAGE_TYPES


def _newHost(hostName):
    # the host at its main list, None when it can not be asked (old API, locked by its PIN)
    module = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], 0)
    host = module.IPTVHost()
    if not isinstance(host, CHostBase) or (host.isProtectedByPinCode() and not IsHostUnlocked(hostName)):
        return None
    host.getSupportedFavoritesTypes()
    host.getInitList()
    return host


def _searchHost(hostName, pattern):
    # -> [{name, host, base, title, count, titles}]: one entry per search type of the host with hits, each with a host
    # object of its own that stands at its result list
    entries = []
    hostTitle = GetHostDisplayTitle(hostName)
    host = _newHost(hostName)
    if host is None:
        return entries
    searchTypes = host.getSearchTypes()
    for typeTitle, searchType in (searchTypes if len(searchTypes) else [('', None)]):
        if host is None:
            host = _newHost(hostName)
        # this search is not one the user made in the host: nothing for its search history
        withHistory, host.withSearchHistrory = host.withSearchHistrory, False
        try:
            ret = host.getSearchResults(pattern, searchType)
        finally:
            host.withSearchHistrory = withHistory
        results = [item for item in (ret.value or []) if _isResult(item)] if ret.status == RetHost.OK else []
        if results:
            entries.append({'name': hostName, 'host': host, 'base': len(host.listOfprevList), 'count': len(results),
                            'title': '%s - %s' % (hostTitle, typeTitle) if typeTitle else hostTitle, 'titles': [item.name for item in results[:TITLES_IN_DESC]]})
            host = None
        elif len(host.listOfprevList):
            host.getPrevList()
    return entries


class GroupSearch(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'groupsearch'})
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/groupsearch135.png')
        self.entries = []  # the hosts of the last result list, its rows point into it
        self.guest = None  # the entry that is open
        self.searchState = None  # the search running now, for getAbortedList()

    def listGroups(self):
        groupObj = IPTVHostsGroups()
        groups = [(item.name, item.title) for item in groupObj.getGroupsList()]
        if 'all' not in [group[0] for group in groups]:
            groups.append(('all', _('All')))
        for name, title in groups:
            try:
                count = len(_groupHosts(groupObj, name))
            except Exception:
                printExc()
                continue
            if count:
                self.addDir({'name': 'category', 'category': 'group', 'group': name, 'group_title': title, 'title': '%s (%d)' % (title, count)})

    def _addResults(self, state):
        self.entries = []
        self.currList = []
        for hostName in state['hosts']:
            for entry in state['found'].get(hostName, []):
                self.addDir({'name': 'category', 'category': 'open_host', 'entry': len(self.entries), 'title': '%s (%d)' % (entry['title'], entry['count']),
                             'desc': '\n'.join(entry['titles']), 'icon': 'file://' + GetIconDir('PlayerSelector/%s135.png' % entry['name'])})
                self.entries.append(entry)
        summary = _('%d of %d hosts asked, %d with results') % (state['asked'], len(state['hosts']), len(state['found']))
        if state['late']:
            summary += ' | %s: %d' % (_('Time limit'), state['late'])
        self.addMarker({'title': summary, 'desc': ''})

    def listAbortedSearch(self):
        # EXIT cut the search off: what the hosts asked until then found
        state, self.searchState = self.searchState, None
        if state is None or not state['found']:
            return False
        self._addResults(state)
        return True

    def searchGroup(self, cItem, pattern):
        printDBG("GroupSearch.searchGroup [%s] [%s]" % (cItem.get('group'), pattern))
        hosts = [hostName for hostName in _groupHosts(IPTVHostsGroups(), cItem['group']) if _hasSearch(hostName)]
        state = {'hosts': hosts, 'found': {}, 'asked': 0, 'late': 0}
        self.searchState = state
        waiting, running, done = list(hosts), {}, Queue()

        def work(hostName):
            # a message box or captcha of a host would wait for the remote control: collected (asynccall.MainSessionWrapper)
            threading.current_thread().e2iWebNotices = []
            entries = None
            try:
                entries = _searchHost(hostName, pattern)
            except Exception:
                printExc()
            finally:
                done.put((hostName, entries))

        try:
            while waiting or running:
                while waiting and len(running) < SEARCH_WORKERS:
                    hostName = waiting.pop(0)
                    running[hostName] = (time.time(), AsyncMethod(work)(hostName))  # pCommon's pycurl requests need the thread data of an AsyncMethod thread
                try:
                    hostName, entries = done.get(timeout=0.5)
                except Empty:
                    hostName = None
                if hostName is not None and running.pop(hostName, None) is not None:
                    state['asked'] += 1
                    if entries:
                        state['found'][hostName] = entries
                    self._showProgress(state, hostName)
                now = time.time()
                for hostName in [name for name in running if now - running[name][0] > HOST_SECONDS]:
                    printDBG("GroupSearch: no answer from host [%s] in time" % hostName)
                    running.pop(hostName)[1].kill()
                    state['asked'] += 1
                    state['late'] += 1
        finally:
            # EXIT kills this thread (SystemExit, also while it waits here)
            for started, thread in list(running.values()):
                try:
                    thread.kill()
                except Exception:
                    printExc()
        self.searchState = None
        self._addResults(state)
        SetIPTVPlayerLastHostError()  # an error of a single host says nothing about this list

    @staticmethod
    def _showProgress(state, hostName):
        text = _('Search: %d of %d - now %s (%d found so far)') % (state['asked'], len(state['hosts']), GetHostDisplayTitle(hostName), len(state['found']))
        if hasattr(GetIPTVNotify(), 'setStatus'):
            GetIPTVNotify().setStatus(text)
        else:
            GetIPTVNotify().push(text, 'info', 5, messageHash='groupsearch')

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('GroupSearch.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        self.currList = []
        if name is None:
            self.listGroups()
        elif category == 'group':
            self.listsTab(self.searchItems(), {'group': self.currItem['group'], 'group_title': self.currItem['group_title']})
        elif category == 'search':
            self.searchGroup(self.currItem, searchPattern)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search', 'group': self.currItem['group'], 'group_title': self.currItem['group_title']}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    # a host that is open works on its own list levels; this host only keeps the list of the search below them
    # (self.host.guest: its host stands at its result list at the level 'base')

    def __init__(self):
        CHostBase.__init__(self, GroupSearch(), True, [])

    def _guest(self):
        entry = self.host.guest
        return entry['host'] if entry else None

    def getGuestHostName(self):
        # the host the rows of the current list belong to (favourites, download marker, player): '' = this host
        entry = self.host.guest
        return entry['name'] if entry else ''

    def _fixRet(self, ret, guest):
        # the widget only knows the favourite types of the host it opened
        types = guest.getSupportedFavoritesTypes().value
        if ret.status == RetHost.OK and isinstance(ret.value, list) and isinstance(types, list):
            for item in ret.value:
                if isinstance(item, CDisplayListItem) and item.type in types:
                    item.isGoodForFavourites = True
        return ret

    def getInitList(self):
        self.host.guest = None
        return CHostBase.getInitList(self)

    def getListForItem(self, Index=0, refresh=0, selItem=None):
        guest = self._guest()
        if guest is not None:
            return self._fixRet(guest.getListForItem(Index, refresh, selItem), guest)
        if 0 <= Index < len(self.host.currList) and self.host.currList[Index].get('category') == 'open_host':
            entry = self.host.entries[self.host.currList[Index]['entry']]
            self.host.guest = entry
            return self._fixRet(entry['host'].getCurrentList(0), entry['host'])
        return CHostBase.getListForItem(self, Index, refresh, selItem)

    def getPrevList(self, refresh=0):
        guest = self._guest()
        if guest is None:
            return CHostBase.getPrevList(self, refresh)
        if len(guest.listOfprevList) > self.host.guest['base']:
            return self._fixRet(guest.getPrevList(refresh), guest)
        # out of the host's result list: the list of the hosts, which was not left on this host's own levels
        self.host.guest = None
        return CHostBase.getCurrentList(self, 0)

    def getCurrentList(self, refresh=0):
        guest = self._guest()
        if guest is not None:
            return self._fixRet(guest.getCurrentList(refresh), guest)
        return CHostBase.getCurrentList(self, refresh)

    def getMoreForItem(self, Index=0):
        guest = self._guest()
        if guest is not None:
            return self._fixRet(guest.getMoreForItem(Index), guest)
        return CHostBase.getMoreForItem(self, Index)

    def getSearchResults(self, searchpattern, searchType=None):
        guest = self._guest()
        if guest is not None:
            return self._fixRet(guest.getSearchResults(searchpattern, searchType), guest)
        return CHostBase.getSearchResults(self, searchpattern, searchType)

    def getAbortedList(self):
        guest = self._guest()
        if guest is not None:
            getAborted = getattr(guest, 'getAbortedList', None)
            return getAborted() if callable(getAborted) else RetHost(RetHost.ERROR, value=[])
        if self.host.listAbortedSearch():
            return CHostBase.getCurrentList(self, 0)
        return RetHost(RetHost.ERROR, value=[])

    def getLinksForVideo(self, Index=0, item=None):
        guest = self._guest()
        return guest.getLinksForVideo(Index, item) if guest is not None else RetHost(RetHost.ERROR, value=[])

    def getResolvedURL(self, url):
        guest = self._guest()
        return guest.getResolvedURL(url) if guest is not None else RetHost(RetHost.ERROR, value=[])

    def getArticleContent(self, Index=0):
        guest = self._guest()
        return guest.getArticleContent(Index) if guest is not None else RetHost(RetHost.ERROR, value=[])

    def getFavouriteItem(self, Index=0):
        guest = self._guest()
        return guest.getFavouriteItem(Index) if guest is not None else RetHost(RetHost.ERROR, value=[])

    def getFavouriteDataOfRow(self, Index):
        guest = self._guest()
        return guest.getFavouriteDataOfRow(Index) if guest is not None else None

    def getRowUrl(self, Index):
        guest = self._guest()
        return guest.getRowUrl(Index) if guest is not None else ''

    def _getRawRow(self, Index):
        guest = self._guest()
        return guest._getRawRow(Index) if guest is not None else None

    def getCustomActions(self, Index=0):
        guest = self._guest()
        return guest.getCustomActions(Index) if guest is not None else RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    def performCustomAction(self, privateData):
        guest = self._guest()
        return guest.performCustomAction(privateData) if guest is not None else RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    def markItemAsViewed(self, Index=0):
        guest = self._guest()
        return guest.markItemAsViewed(Index) if guest is not None else RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    def markItemAsStarted(self, Index=0):
        guest = self._guest()
        if guest is not None and hasattr(guest, 'markItemAsStarted'):
            guest.markItemAsStarted(Index)

    def getSuggestionsProvider(self, Index=0):
        guest = self._guest()
        return guest.getSuggestionsProvider(Index) if guest is not None else RetHost(RetHost.NOT_IMPLEMENTED, value=[])
