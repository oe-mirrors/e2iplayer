# -*- coding: utf-8 -*-
###################################################
# 2022-08-31 - Web HU Player
###################################################
HOST_VERSION = "4.0"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetLogoDir, GetIPTVPlayerVersion, rm, rmtree, mkdirs, DownloadFile, GetFileSize, GetConfigDir, Which, MergeDicts
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
# Config options for HOST
###################################################
config.plugins.iptvplayer.webhuplayer_dir = ConfigText(default = "/hdd/webhuplayer", fixed_size = False)
config.plugins.iptvplayer.webmedia_dir = ConfigText(default = "/hdd/webmedia", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Web HU Player könyvtára:", config.plugins.iptvplayer.webhuplayer_dir))
    optionList.append(getConfigListEntry("Web média könyvtára:", config.plugins.iptvplayer.webmedia_dir))
    return optionList
###################################################

def gettytul():
    return 'Web HU Player'

class webhuplayer(CBaseHostClass):

    def __init__(self):
        printDBG("webhuplayer.__init__")
        CBaseHostClass.__init__(self, {'history':'webhuplayer', 'cookie':'webhuplayer.cookie'})
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = self.cm.getDefaultHeader()
        self.DEFAULT_ICON_URL = 'http://www.figyelmeztetes.hu/webhuplayer_logo.jpg'
        self.ICON_IDOJARAS = 'https://w.bookcdn.com/weather/picture/4_18069_1_14_151fe8_160_ffffff_333333_08488D_1_ffffff_333333_0_6.png?scode=124&domid=462&anc_id=44759'
        self.ICON_INFO = 'http://www.figyelmeztetes.hu/webhuplayer_logo_i.jpg'
        self.ICON_FRISSIT = 'http://www.figyelmeztetes.hu/webhuplayer_logo_fr.jpg'
        self.list_tart = 'webhuplayer.list'
        self.aktual = 'aktualis.stream'
        self.path_webh = config.plugins.iptvplayer.webmedia_dir.value + "/"
        self.path_full =  normpath(self.path_webh + self.list_tart)
        self.path_aktual = normpath(self.path_webh + self.aktual)
        self.defaultParams = {'header':self.HEADER, 'use_cookie': False, 'load_cookie': False, 'save_cookie': False, 'cookiefile': self.COOKIE_FILE}
        
    def _uriIsValid(self, url):
        return '://' in url
    
    def list_tartalom(self, cItem):
        approve = self.check()
        if approve:
            params = []
            self.list_ujdonsag()
            data = open(self.path_full, 'r')
            list = data.readlines()
            printDBG(str(list))
            for i in list:
                actual = i.split('|')
                title = actual[0]
                url = self.path_webh + actual[1].replace(".list", "").strip()
                desc = actual[2]
                params.append({'category': 'list_items', 'title': title, 'url': url, 'desc': desc, 'icon': None})
            data.close()
            self.listsTab(params, cItem) 
    
    def listItems(self, cItem):
        printDBG('listItems')
        printDBG(cItem)
        dir_list = os.listdir(cItem['url'])
        printDBG(str(dir_list))
        for i in dir_list:
            if i.endswith('.list'):
                data = open(cItem['url'] + "/" + i, 'r')
                list = data.readlines()
                if 'stream' not in list[0]:
                    for e in list:
                        actual = e.split('|')
                        title = actual[0]
                        url = cItem['url'] + "/" + actual[1].replace(".list", "").strip()
                        if 'stream' not in url:
                            printDBG(url)
                            desc = actual[2]
                            params = {'category': 'list_items', 'title': title, 'url': url, 'desc': desc, 'icon': None}
                            self.addDir(params)
                if 'stream' in list[0] or 'stream' in list[-1]:
                    data.close()
                    data = open(cItem['url'] + "/" + i.replace(".list", ".stream"), 'r')
                    printDBG(cItem['url'] + "/" + i.replace(".list", ".stream"))
                    list = data.read()
                    list = list.split('---')
                    list.pop(0)
                    printDBG(str(list))
                    for a in list:
                        item = a.split('\n')
                        item.pop(0)
                        title = item[0]
                        url = item[1]
                        icon = item[2]
                        desc = item[3]
                        params = {'title': title, 'url': url, 'desc': desc, 'icon': icon}
                        if url.endswith(".jpg"):
                            self.addPicture(params)
                        else:
                           self.addVideo(params)
                data.close()
    
    def list_ujdonsag(self):
        data = open(self.path_aktual, 'r')
        list = data.read()
        list = list.split("---")
        printDBG(str(list))
        list.pop(0)
        list.pop(-1)
        for i in list:
            actual = i.split("\n")
            title = actual[1].strip("\n")
            url = actual[2].strip("\n")
            printDBG(url)
            desc = actual[4].strip("\n")
            params = {'title': title, 'url': url, 'desc': desc, 'icon': actual[3].strip("\n")}
            if url.endswith(".jpg"):
                self.addPicture(params)
            else:
               self.addVideo(params)
        data.close()
    
    def check(self):
        if os.path.isdir(self.path_webh):
            sts, data = self.cm.getPage('https://github.com/e2iplayerhosts/webmedia3/blob/master/README.md', self.defaultParams)
            version = self.cm.ph.getDataBeetwenMarkers(data, 'Version: ', '</p>', False)[1]
            printDBG(version)
            local = self.getversion()
            if version != local:
                self._update()
                return False
            else:
               return True
        else:
           self._update()
           return False
    
    def getversion(self):
        data = open(self.path_aktual, 'r')
        version = data.readline()
        version = self.cm.ph.getDataBeetwenMarkers(version, '|', '|', False)[1]
        printDBG(version)
        data.close()
        return version
    
    def _update(self):
        msg = 'Telepítés/frissítés szükséges. A telepítés/frissítés helye:  ' + config.plugins.iptvplayer.webmedia_dir.value.replace('/',' / ').strip() + '\nFolytathatom?'
        msg += '\n\nHa máshova szeretnéd, akkor itt nem - utána KÉK gomb, majd az Oldal beállításai.\nOtt az adatok megadása, s utána a ZÖLD gomb (Mentés) megnyomása!'
        ret = self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_YESNO, default=True)
        if ret[0]:
            pass
        else:
           return
        url = 'https://github.com/e2iplayerhosts/webmedia3/archive/master.zip'
        fname = 'webmedia.zip'
        destination =  '/tmp/' + fname
        destination_dir = '/tmp' + '/webmedia3-main'
        destination_fo = '/tmp' + '/webmedia'
        fname_zip = destination_dir + '/' + fname
        unzip_command = ['unzip', '-q', '-o', destination, '-d', '/tmp']
        unzip_command_zip = ['unzip', '-q', '-o', fname_zip, '-d', '/tmp']
        if self.download(url, destination):
            if self._mycall(unzip_command) == 0:
                if self._mycall(unzip_command_zip) == 0:
                    if mkdirs(self.path_webh):
                        if self._copy(destination_fo + '/*', self.path_webh):
                            msg = 'Sikerült a webmedia könyvtár frissítése/telepítése!'
                            self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10 )
                            self.list_tartalom()
                        else:
                           msg = 'A frissítés/telepítés sikertelen! (Másolási hiba)'
                           self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
                    else:
                       msg = 'A frissítés/telepítés sikertelen! (A webmedia könyvtára nem hozható létre)'
                       self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
                else:
                   msg = 'A frissítés/telepítés sikertelen! (Hiba a belső könyvtár kicsomagolása során)'
                   self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
            else:
               msg = 'A frissítés/telepítés sikertelen! (Hiba a kicsomagolás során)'
               self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
        else:
           msg = 'A frissítés/telepítés sikertelen! (Letöltési hiba, próbáld újra.)'
           self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_ERROR, timeout = 20 )
        if fileExists(destination):
            rm(destination) 
            rmtree(destination_dir, ignore_errors=True)
            rmtree(destination_fo, ignore_errors=True)    
    
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
    
    def getLinksForVideo(self, cItem):
        printDBG("Webhuplayer.getLinksForVideo")
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(cItem['url'])
        protocol = uri.meta.get('iptv_proto', '')
        
        printDBG("PROTOCOL [%s] " % protocol)
        
        urlSupport = self.up.checkHostSupport( uri )
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt( uri )
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == 'm3u8':
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                videoUrls.extend(retTab)
            elif protocol == 'f4m':
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif protocol == 'mpd':
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name':'direct link', 'url':uri})
        return videoUrls
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        try:
            CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
            name     = self.currItem.get("name", '')
            category = self.currItem.get("category", '')
            self.currList = []
            if name == None:
                self.list_tartalom({'name':'category'})
            elif category == "list_items":
                self.listItems(self.currItem)
            elif category in ['search', 'search_next_page']:
                cItem = dict(self.currItem)
                cItem.update({'search_item':False, 'name':'category'}) 
                self.listSearchResult(cItem, searchPattern, searchType)
            elif category == 'search_history':
                self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
            else:
                printExc()
            CBaseHostClass.endHandleService(self, index, refresh)
        except Exception:
            return

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, webhuplayer(), True, [])
    
