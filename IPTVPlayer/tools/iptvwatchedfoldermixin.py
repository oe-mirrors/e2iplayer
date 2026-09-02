# -*- coding: utf-8 -*-
# Shared generic "watched flag" wiring for the recursive folder-style hosts
# (ARD / ZDF / ARTE / ORF / SRG mediatheken).
#
# Unlike filmpalast / serienstream these hosts have NO explicit
# series/season/episode data model - a "show" is just a folder whose episodes are
# fetched through the same generic listing code as everything else. So episodes
# are marked normally (watched / started / MENU toggle via WatchedFlagHostMixin)
# and a folder's dot/checkmark is derived by walking a breadcrumb chain of folder
# keys that is accumulated while the user browses: every addDir()/addVideo()/
# addAudio() records parent<-child, and when an episode's state changes the chain
# is recomputed upwards (episode -> season folder -> show folder -> ...), as far
# as it is known in the current session.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, RetHost
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin
###################################################

# query-string params that only page/slice a listing - they must not make the
# same logical folder look like two different folders
_WF_VOLATILE_QS = ('page', 'pageNumber', 'pageNo', 'pageSize', 'offset', 'limit',
                   'loadSize', 'size', 'vodPageNumber', 'showPageNumber', 'maxLength',
                   'embedded')


class GenericFolderWatchedScraperMixin(object):
    # host scraper side - mix in BEFORE CBaseHostClass.
    # Requires the including class to provide:
    #   self.watchedHelper           (IPTVWatchedHelper instance)
    #   self.wfInitFolderCache()     called from __init__
    #   _getWatchedKeyForItem(cItem) -> '' | 'video:<stable-id>' | 'folder:<stable-id>'

    def wfInitFolderCache(self):
        self.wfFolderChildren = {}
        self.wfFolderParent = {}

    @staticmethod
    def wfNormalizeUrlKey(url):
        # drop volatile pagination params so page 2+ of a folder keys the same as page 1
        url = str(url or '').strip()
        if url == '':
            return ''
        try:
            base, sep, qs = url.partition('?')
            if sep:
                kept = [p for p in qs.split('&') if p and p.split('=', 1)[0] not in _WF_VOLATILE_QS]
                url = base + ('?' + '&'.join(kept) if kept else '')
        except Exception:
            printExc()
        return url

    def wfRegister(self, params):
        # links the folder tree (parent <- child) and stamps parent_key on the
        # child for later propagation; a no-op for items without a watched key
        # (nav tabs, "Next page", live streams, search, ...).
        # MUST run after CBaseHostClass.addX() so params['type'] is already set.
        try:
            if not isinstance(params, dict) or getattr(self, 'watchedHelper', None) is None:
                return params
            childKey = self._getWatchedKeyForItem(params)
            if childKey == '':
                return params
            parentKey = self._getWatchedKeyForItem(getattr(self, 'currItem', {}) or {})
            params['parent_key'] = parentKey
            if parentKey != '' and parentKey != childKey:
                children = self.wfFolderChildren.setdefault(parentKey, [])
                if childKey not in children:
                    children.append(childKey)
                self.wfFolderParent[childKey] = parentKey
        except Exception:
            printExc()
        return params

    def addDir(self, params):
        CBaseHostClass.addDir(self, params)
        self.wfRegister(params)

    def addVideo(self, params):
        CBaseHostClass.addVideo(self, params)
        self.wfRegister(params)

    def addAudio(self, params):
        CBaseHostClass.addAudio(self, params)
        self.wfRegister(params)

    def _propagateEpisodeWatchedState(self, item):
        # called by WatchedFlagHostMixin on play start / completion and by
        # GenericFolderWatchedHostMixin.performCustomAction on a MENU toggle
        try:
            if not isinstance(item, dict) or getattr(self, 'watchedHelper', None) is None:
                return
            key = self._getWatchedKeyForItem(item)
            startKey = self.wfFolderParent.get(key, '') or str(item.get('parent_key', '') or '')
            if startKey != '':
                self.watchedHelper.propagateFolderChain(startKey, self.wfFolderChildren, self.wfFolderParent)
        except Exception:
            printExc()


class GenericFolderWatchedHostMixin(WatchedFlagHostMixin):
    # IPTVHost side - mix in BEFORE CHostBase.
    # Requires __init__ to set self.cachedRet, self.refreshAfterWatchedFlagChange
    # and self.watchedHelper (same IPTVWatchedHelper host name as the scraper).

    def performCustomAction(self, privateData):
        ret = self.watchedHelper.performCustomAction(privateData)
        if ret.status == RetHost.OK:
            self.refreshAfterWatchedFlagChange = True
            try:
                idx = privateData.get('item_index', -1)
                if 0 <= idx < len(self.host.currList):
                    self.host._propagateEpisodeWatchedState(self.host.currList[idx])
            except Exception:
                printExc()
        return ret
