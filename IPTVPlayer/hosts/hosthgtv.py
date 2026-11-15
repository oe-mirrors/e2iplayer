# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# HGTV (de.hgtv.com) - Mediathek of the German free-TV channel HGTV (Warner Bros. Discovery).
#   The code is shared with DMAX, TELE 5 and TLC: libs/wbdmediathek.py
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.libs.wbdmediathek import WBDMediathek, WBDMediathekHost
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://de.hgtv.com/'


class HGTV(WBDMediathek):
    CHANNEL_NAME = 'HGTV'
    CHANNEL_KEY = 'hgtv'
    CHANNEL_URL = gettytul()
    CHANNEL_ENV = 'hgtvde'
    CHANNEL_NEW_EPISODES = False
    CHANNEL_SHOWS = 'sendungen'


class IPTVHost(WBDMediathekHost):

    def __init__(self):
        WBDMediathekHost.__init__(self, HGTV())
