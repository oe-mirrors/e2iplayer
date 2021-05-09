# -*- coding: utf-8 -*-
#
#  IPTV download manager API
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import m3u8
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.m3u8downloader import M3U8Downloader
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from enigma import eConsoleAppContainer
from time import sleep, time
import re
import datetime
###################################################

###################################################
# One instance of this class can be used only for
# one download
###################################################


class EM3U8Downloader(M3U8Downloader):

    def __init__(self):
        printDBG('EM3U8Downloader.__init__ ----------------------------------')
        M3U8Downloader.__init__(self)

        # M3U8list link provider
        self.EM3U8linkProv = eConsoleAppContainer()
        self.EM3U8linkProv_appClosed_conn = eConnectCallback(self.EM3U8linkProv.appClosed, self._updateEM3U8Finished)
        #self.EM3U8linkProv_stdoutAvail_conn = eConnectCallback(self.EM3U8linkProv.stdoutAvail, self._updateEM3U8DataAvail)
        self.EM3U8linkProv_stderrAvail_conn = eConnectCallback(self.EM3U8linkProv.stderrAvail, self._updateEM3U8DataAvail)

        self.EM3U8ListData = ''
        self.em3u8Started = False

        self.em3u8_url = ''
        self.em3u8_filePath = ''
        self.em3i8_params = {}

        self.maxTriesAtStart = 12

    def __del__(self):
        printDBG("EM3U8Downloader.__del__ ----------------------------------")

    def start(self, url, filePath, params={}):
        self.em3u8_url = strwithmeta(url)
        self.em3u8_filePath = filePath
        self.em3i8_params = params

        printDBG("===================EM3U8Downloader===================")
        printDBG(self.em3u8_url.meta)
        printDBG(self.em3u8_url.meta.get('iptv_refresh_cmd', ''))
        printDBG("=====================================================")
        self.EM3U8linkProv.execute(self.em3u8_url.meta.get('iptv_refresh_cmd', ''))

        return BaseDownloader.CODE_OK

    def _updateEM3U8Finished(self, code=0):
        printDBG('EM3U8Downloader._updateEM3U8Finished update code[%d]--- ' % (code))
        if not self.em3u8Started:
            self.status = DMHelper.STS.ERROR
            M3U8Downloader._terminate(self)
            self.onFinish()

    def _updateEM3U8DataAvail(self, data):
        if None != data and 0 < len(data):
            self.EM3U8ListData += data
            if self.EM3U8ListData.endswith('\n'):
                printDBG(self.EM3U8ListData)
                data = self.EM3U8ListData.split('\n')
                url = ''
                for item in data:
                    if item.startswith('http'):
                        url = item.strip()
                if url.startswith('http'):
                    if not self.em3u8Started:
                        url = strwithmeta(url, self.em3u8_url.meta)
                        M3U8Downloader.start(self, url, self.em3u8_filePath, self.em3i8_params)
                        self.em3u8Started = True
                    else:
                        self.m3u8Url = url
                self.EM3U8ListData = ''

    def _terminate(self):
        printDBG("M3U8Downloader._terminate")
        if self.EM3U8linkProv:
            self.EM3U8linkProv_appClosed_conn = None
            #self.EM3U8linkProv_stdoutAvail_conn = None
            self.EM3U8linkProv_stderrAvail_conn = None
            self.EM3U8linkProv.sendCtrlC()
            self.EM3U8linkProv = None
        return M3U8Downloader._terminate(self)
