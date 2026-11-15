# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# TLC (tlc.de) - Mediathek of the German free-TV channel TLC (Warner Bros. Discovery).
#   The code is shared with DMAX, HGTV and TELE 5: libs/wbdmediathek.py
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.libs.wbdmediathek import WBDMediathek, WBDMediathekHost
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://tlc.de/'


class TLC(WBDMediathek):
    CHANNEL_NAME = 'TLC'
    CHANNEL_KEY = 'tlc'
    CHANNEL_URL = gettytul()
    CHANNEL_ENV = 'tlcde'
    CHANNEL_NEW_EPISODES = True
    CHANNEL_SHOWS = 'sendungen'


class IPTVHost(WBDMediathekHost):

    def __init__(self):
        WBDMediathekHost.__init__(self, TLC())
