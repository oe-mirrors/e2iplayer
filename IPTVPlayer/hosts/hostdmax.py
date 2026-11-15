# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# DMAX (dmax.de) - Mediathek of the German free-TV channel DMAX (Warner Bros. Discovery).
#   The code is shared with HGTV, TELE 5 and TLC: libs/wbdmediathek.py
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.libs.wbdmediathek import WBDMediathek, WBDMediathekHost
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://dmax.de/'


class DMAX(WBDMediathek):
    CHANNEL_NAME = 'DMAX'
    CHANNEL_KEY = 'dmax'
    CHANNEL_URL = gettytul()
    CHANNEL_ENV = 'dmaxde'
    CHANNEL_NEW_EPISODES = True
    CHANNEL_SHOWS = 'sendungen'


class IPTVHost(WBDMediathekHost):

    def __init__(self):
        WBDMediathekHost.__init__(self, DMAX())
