# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, RetHost
###################################################
# FOREIGN import
###################################################
from Components.config import config


class WatchedFlagHostMixin(object):
    # Shared IPTVHost boilerplate for wiring a per-site host into the centralized
    # watched-flag/favourite-hash system (IPTVWatchedHelper). Include alongside
    # CHostBase, e.g. class IPTVHost(WatchedFlagHostMixin, CHostBase).
    # Requires the including class's __init__ to set up:
    #   self.watchedHelper (IPTVWatchedHelper instance, named after the host)
    #   self.cachedRet, self.refreshAfterWatchedFlagChange

    def fixWatchedFlag(self, ret):
        if config.plugins.iptvplayer.favourites_use_watched_flag.value:
            ret = self.watchedHelper.fixHostRet(ret, self.host.currList, self.host._getWatchedKeyForItem)
        self.cachedRet = ret
        return ret

    def getLinksForVideo(self, Index=0, selItem=None):
        # this resolves links for both actually streaming AND downloading, and can
        # also fail - so, unlike the old behaviour, it does NOT touch watched/started
        # state at all. That only happens once iptvplayerwidget.py's playVideo() has
        # confirmed the links resolved and it's really about to open a player (see
        # markItemAsStarted) - marking/instant UI feedback here used to fire for
        # downloads too, which is wrong.
        return CHostBase.getLinksForVideo(self, Index, selItem)

    def getCustomActions(self, Index=0):
        return self.watchedHelper.getCustomActionsForRet(self.cachedRet, self.host.currList, self.host._getWatchedKeyForItem, Index)

    def markItemAsStarted(self, Index=0):
        # called from iptvplayerwidget.py's playVideo() right before a player is
        # actually opened for the item at Index - not on download, and not if
        # resolving/opening failed before getting here
        try:
            if config.plugins.iptvplayer.favourites_use_watched_flag.value and 0 <= Index < len(self.host.currList):
                cItem = self.host.currList[Index]
                if self.watchedHelper.markHostItemAsStarted(self.host, cItem, self.host._getWatchedKeyForItem):
                    propagate = getattr(self.host, '_propagateEpisodeWatchedState', None)
                    if callable(propagate):
                        propagate(cItem)
                    # instant UI feedback: reflect it into the already-rendered list
                    # without needing a full refetch
                    if self.cachedRet is not None and hasattr(self.cachedRet, 'value') and 0 <= Index < len(self.cachedRet.value):
                        if not self.cachedRet.value[Index].isWatched:
                            self.cachedRet.value[Index].isStarted = True
                        self.refreshAfterWatchedFlagChange = True
        except Exception:
            printExc()

    def markItemAsViewed(self, Index=0):
        # called from leaveMoviePlayer() once playback crosses the completion
        # threshold, to upgrade an item from "started" to fully watched
        retCode = RetHost.ERROR
        retlist = []
        try:
            if config.plugins.iptvplayer.favourites_use_watched_flag.value and 0 <= Index < len(self.host.currList):
                cItem = self.host.currList[Index]
                if self.watchedHelper.markHostItemAsWatched(self.host, cItem, self.host._getWatchedKeyForItem):
                    propagate = getattr(self.host, '_propagateEpisodeWatchedState', None)
                    if callable(propagate):
                        propagate(cItem)
                    self.refreshAfterWatchedFlagChange = True
                    retCode = RetHost.OK
                    retlist = ['refresh']
        except Exception:
            printExc()
        return RetHost(retCode, value=retlist)

    def getListForItem(self, Index=0, refresh=0, selItem=None):
        ret = CHostBase.getListForItem(self, Index, refresh, selItem)
        return self.fixWatchedFlag(ret)

    def getPrevList(self, refresh=0):
        ret = CHostBase.getPrevList(self, refresh)
        return self.fixWatchedFlag(ret)

    def getCurrentList(self, refresh=0):
        if refresh == 1 and self.refreshAfterWatchedFlagChange and self.cachedRet is not None:
            ret = self.cachedRet
        else:
            ret = CHostBase.getCurrentList(self, refresh)
        ret = self.fixWatchedFlag(ret)
        self.refreshAfterWatchedFlagChange = False
        return ret

    def getMoreForItem(self, Index=0):
        ret = CHostBase.getMoreForItem(self, Index)
        return self.fixWatchedFlag(ret)
