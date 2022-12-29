# -*- coding: utf-8 -*-
###################################################
# 2022-10-19 - UPDATEHOSTS - WhiteWolf
###################################################
HOST_VERSION = "5.0"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetLogoDir, rm, rmtree, mkdirs, DownloadFile, GetFileSize, GetConfigDir, Which, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigText, ConfigYesNo, ConfigDirectory, getConfigListEntry
from os.path import normpath
import os
import re
import random
import codecs
try:
    import subprocess
    FOUND_SUB = True
except Exception:
    FOUND_SUB = False
from Tools.Directories import resolveFilename, fileExists, SCOPE_PLUGINS
from Screens.MessageBox import MessageBox
###################################################
###################################################

def gettytul():
    return 'updatehosts HU'

class UPDATEHOSTS(CBaseHostClass):

    def __init__(self):
        printDBG("Updatehosts.__init__")
        CBaseHostClass.__init__(self, {'history':'updatehosts', 'cookie':'updatehosts.cookie'})
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = self.cm.getDefaultHeader()
        self.versionpath = normpath("/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/version.py")
        self.playerpath = normpath("/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/")
        self.changespath = self.playerpath+"/changes.txt"
        self.defaultParams = {'header':self.HEADER, 'use_cookie': False, 'load_cookie': False, 'save_cookie': False, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'http://www.figyelmeztetes.hu/updatehosts_logo.jpg'
    
    def main_menu(self, cItem):
        changes = {'title': 'Változások listája', 'url': 'changes', 'icon': self.DEFAULT_ICON_URL, 'desc': "Jelenlegi verzió: %s\nElérhető verzió: %s" % (self.getversion(), self.getremoteversion())}
        self.addDir(changes)
        frissit = {'title': 'Frissítés', 'url': 'update', 'icon': self.DEFAULT_ICON_URL, 'desc': "Jelenlegi verzió: %s\nElérhető verzió: %s" % (self.getversion(), self.getremoteversion())}
        self.addDir(frissit)
        telepit = {'title': 'Teljes Telepítés', 'url': 'install', 'icon': self.DEFAULT_ICON_URL, 'desc': "Jelenlegi verzió: %s\nElérhető verzió: %s" % (self.getversion(), self.getremoteversion())}
        self.addDir(telepit)
    
    def getchanges(self):
        sts, data = self.cm.getPage('https://raw.githubusercontent.com/Blindspot76/e2iPlayer-Python3/master/IPTVPlayer/changes.txt', self.defaultParams)
        f = open(self.changespath, "w")
        f.write(data)
        f.close()
        f = open(self.changespath, "r")
        a = f.read()
        a = a.split("#")
        a.pop(0)
        var = 0
        while var != len(a):
           params = {'title': a[var][:a[var].index("\n")], 'desc': a[var][a[var].index("\n"):]}
           self.addMarker(params)
           var += 1
        f.close()
    
    def getremoteversion(self):
        sts, data = self.cm.getPage('https://github.com/Blindspot76/e2iPlayer-Python3/blob/master/IPTVPlayer/version.py', self.defaultParams)
        version = self.cm.ph.getDataBeetwenMarkers(data, 'IPTV_VERSION', '</td>', False)[1]
        version = self.cm.ph.getDataBeetwenMarkers(version, '&quot;', '&quot;', False)[1]
        printDBG(version)
        return version
    
    def check(self):
        version = self.getremoteversion()
        local = self.getversion()
        if version != local:
            self._update("update")
            msg = 'Jelenlegi verzió: %s %s' % (self.getversion(), "\n")
            ret = self.sessionEx.waitForFinishOpen(MessageBox, msg+ _("A frissítés sikeres.\nA rendszer most újraindul."), type = MessageBox.TYPE_INFO, timeout = 10)
            try:
               from enigma import quitMainloop
               quitMainloop(3) 
            except Exception:
               msg = 'Nem sikerült az újraindítás.\nKérlek indítsd újra manuálisan!'
               ret = self.sessionEx.waitForFinishOpen(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 6)
        else:
          msg = 'Nem szükséges frissítés.'
          ret = self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.INFO, timeout = 10 )
    
    def getversion(self):
        data = open(self.versionpath, 'r')
        version = data.read()
        version = self.cm.ph.getDataBeetwenMarkers(version, 'IPTV_VERSION="', '"', False)[1]
        printDBG(version)
        data.close()
        return version
    
    def _update(self, command):
        url = 'https://github.com/Blindspot76/e2iPlayer-Python3/archive/master.zip'
        dir = "/tmp/cache/"
        mkdirs(dir)
        fname = 'master.zip'
        destination = dir + fname
        destination_unpack = "/tmp/cache/e2iPlayer-Python3-master/IPTVPlayer/*"
        unzip_command = ['unzip', '-q', '-o', destination, '-d', dir]
        if self.download(url, destination):
            if self._mycall(unzip_command) == 0:
                if command == "update":
                    if self._copy(destination_unpack, self.playerpath):
                        pass
                    else:
                       msg = 'A frissítés sikertelen! (Másolási hiba)'
                       self.sessionEx.waitForFinishOpen(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
                       return
                if command == "install":
                    rmtree(self.playerpath)
                    mkdirs(self.playerpath)
                    if self._copy(destination_unpack, self.playerpath):
                        pass
                    else:
                       msg = 'A frissítés sikertelen! (Másolási hiba)'
                       self.sessionEx.waitForFinishOpen(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
                       return
            else:
               msg = 'A frissítés sikertelen! (Hiba a kicsomagolás során)'
               self.sessionEx.waitForFinishOpen(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
               return
        else:
           msg = 'A frissítés sikertelen! (Letöltési hiba, próbáld újra.)'
           self.sessionEx.waitForFinishOpen(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
           return
        rmtree(dir)
        return
    
    def download(self, url, destination, tries=2, delay=3):
        vissza = False
        try:
            for i in range(tries):
                tmp = DownloadFile(url,destination)
                if tmp:
                    vissza = True
                    break
                else:
                    sleep(delay)
        except Exception:
            return False
        return vissza
    
    def _mycall(self, cmd):
        command = cmd
        back_state = -1
        try:
            back_state = subprocess.call(command)
        except Exception:
            return -1
        return back_state
    
    def _copy(self, filename, dest_dir):
        sikerult = False
        try:
           copy_command = 'cp -rf ' + filename + ' ' + dest_dir
           if subprocess.call(copy_command, shell=True) == 0:
               sikerult = True
        except Exception:
            return False
        return sikerult
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        try:
            CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
            name     = self.currItem.get("name", '')
            category = self.currItem.get("category", '')
            url      = self.currItem.get("url", '')
            self.currList = []
            if name == None:
                self.main_menu({'name':'category'})
            elif url == "changes":
                self.getchanges()
            elif url == "update":
                self.check()
            elif url == "install":
                self._update("install")
                msg = 'Jelenlegi verzió: %s %s' % (self.getversion(), "\n")
                ret = self.sessionEx.waitForFinishOpen(MessageBox, msg+ _("A telepítés sikeres.\nA rendszer most újraindul."), type = MessageBox.TYPE_INFO, timeout = 10)
                try:
                   from enigma import quitMainloop
                   quitMainloop(3) 
                except Exception:
                   msg = 'Nem sikerült az újraindítás.\nKérlek indítsd újra manuálisan!'
                   ret = self.sessionEx.waitForFinishOpen(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 6)
            else:
                printExc()
            CBaseHostClass.endHandleService(self, index, refresh)
        except Exception:
            return

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, UPDATEHOSTS(), True, [])
    
