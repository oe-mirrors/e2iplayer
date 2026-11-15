# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# TELE 5 (tele5.de) - Mediathek of the German free-TV channel TELE 5 (Warner Bros. Discovery).
#   The code is shared with DMAX, HGTV and TLC: libs/wbdmediathek.py
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.libs.wbdmediathek import WBDMediathek, WBDMediathekHost
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://tele5.de/'


class TELE5(WBDMediathek):
    CHANNEL_NAME = 'TELE 5'
    CHANNEL_KEY = 'tele5'
    CHANNEL_URL = gettytul()
    CHANNEL_ENV = 'tele5'
    CHANNEL_NEW_EPISODES = True
    CHANNEL_SHOWS = 'mediathek'
    CHANNEL_PAGES = (('Movies', 'filme'), ('Series', 'serien'))  # (title msgid, page slug)


class IPTVHost(WBDMediathekHost):

    def __init__(self):
        WBDMediathekHost.__init__(self, TELE5())
