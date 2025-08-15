# -*- coding: utf-8 -*-
###################################################
# 2020-01-17 by Alec - modified Technika.HU
###################################################
HOST_VERSION = "1.4"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetTmpDir, GetIPTVPlayerVerstion, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
import random
import os
import datetime
import time
import zlib
import cookielib
import base64
import codecs
import traceback
from copy import deepcopy
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, ConfigYesNo, ConfigSelection, getConfigListEntry
from Tools.Directories import resolveFilename, fileExists, SCOPE_PLUGINS
from datetime import datetime
from hashlib import sha1
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.technika_id = ConfigYesNo(default = False)
config.plugins.iptvplayer.boxtipus = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.boxrendszer = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.technika_legfrissebb_napok = ConfigSelection(default = "7", choices = [
("3", "3 nap"),
("5", "5 nap"),
("7", "7 nap"),
("10", "10 nap")
])

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("id:", config.plugins.iptvplayer.technika_id))
    optionList.append(getConfigListEntry("Legfrissebb napok száma:", config.plugins.iptvplayer.technika_legfrissebb_napok))
    return optionList
###################################################

def gettytul():
    return 'Technika.HU'
    
def int_or_none(data):
    ret = 0
    try: ret = int(data)
    except Exception: pass
    return ret

class Technika(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'technika', 'cookie':'technika.cookie'})
        self.DEFAULT_ICON_URL = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9JTc7Iy8xOjM/JT8/XyypIBwCgsBHd'))
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0'
        self.HEADER = self.cm.getDefaultHeader()
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.IH = resolveFilename(SCOPE_PLUGINS, zlib.decompress(base64.b64decode('eJxzrShJzSvOzM8r1vcMCAkLyEmsTC0CAFlVCBA=')))
        self.HS = zlib.decompress(base64.b64decode('eJzTz8gvLikGAAeYAmE='))
        self.MAIN_URL = ''
        self.DEFAULT_ICON_URL_TECH2 = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9JTc4wis/JT8/XK8hLBwBpnBBw'))
        self.plurl_tech2 = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoY6OJq5hJimpecG+Ln6+ZaEVLmEWRo4A2qUWHw=='))
        self.DEFAULT_ICON_URL_POWERTECH = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S/IL08tKklNzojPyU/P18sqSAcAtSgSZw=='))
        self.plurl_powertech = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahofl5lamOmRH5hm5ZXtlh/p5ZBTkuKYEA6u0XSw=='))
        self.DEFAULT_ICON_URL_MOBEEL = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c/NT0pNzYnPyU/P18sqSAcAfNYRCg=='))
        self.plurl_mobeel = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahocYu5X5eee6Fpe7paekmlv7lAclV/oEA43IW+A=='))
        self.DEFAULT_ICON_URL_ITFROCS = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c8sSSvKTy6Oz8lPz9fLKkgHAI/gEZA='))
        self.plurl_itfrocs = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoe4p6WHephbZHv4GzgXpHomBUQbmFukA3LoWIg=='))
        self.DEFAULT_ICON_URL_TECHVIDEO = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9JTc4oy0xJzY/PyU/P18sqSAcAs6wSUQ=='))
        self.plurl_techvideo = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahod5ZqW65fhZ5LmVlloll8eFmHgUVReUA5r0XYg=='))
        self.DEFAULT_ICON_URL_HDROID = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IKcrPTInPyU/P18sqSAcAfRUREA=='))
        self.plurl_hdroid = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahocZ5jmV+loURqSbB5pZFpVWZHhWmbo4A4RoWpg=='))
        self.DEFAULT_ICON_URL_VRTECH = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S8rKklNzojPyU/P18sqSAcAfjMRIg=='))
        self.plurl_vrtech = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoS6pQcUuhclOFlUp2VWuRRVFKR7O/uUA6SsXdQ=='))
        self.DEFAULT_ICON_URL_NBOOK = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9Lys/Pjs/JT8/XyypIBwBsKhCv'))
        self.plurl_nbook = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoemWZWlFJgGOPsYVaakVEUFu5dlZXoEA5dcXIA=='))
        self.DEFAULT_ICON_URL_APIE = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8syEyNz8lPz9fLKkgHAFqQEDU='))
        self.plurl_apie = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoQG6YZmFQe6JxhW6OdmpJtnx4SUZTo4A4csWyw=='))
        self.DEFAULT_ICON_URL_SHADOWWARRIOR = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S/OSEzJLy9PLCrKzC+Kz8lPz9fLKkgHAAQ1FCI='))
        self.plurl_shadowwarrior = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoaW6VeXuiRHeZgVR/rpGwbph5rm6Fo4A4JsWCA=='))
        self.DEFAULT_ICON_URL_HUNBOXING = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c8ozUvKr8jMS4/PyU/P18sqSAcAtOoSaA=='))
        self.plurl_hunboxing = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoYFm7lXeieFOUaaOySaBeUmpRZme+Y4A3rIWqg=='))
        self.DEFAULT_ICON_URL_BYTECH = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U+qLElNzojPyU/P18sqSAcAfWkRFQ=='))
        self.plurl_bytech = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoSFGWXnF5cHFJsVugV557gWOrmnOIeUA5xkXEQ=='))
        self.DEFAULT_ICON_URL_TECHKALAUZ = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9JTc7ITsxJLK2Kz8lPz9fLKkgHAManEsI='))
        self.plurl_techkalauz = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoUFVblVhpa6p6QEZ2R6OSRapZVlZ3oEA6oUXVQ=='))
        self.DEFAULT_ICON_URL_TECHDOBOZ = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9JTc5IyU/Kr4rPyU/P18sqSAcAs8ISWA=='))
        self.plurl_techdoboz = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoRWOTiUuHgVFxX4VBp4lYfFmxcUpeYEA6AYXUw=='))
        self.DEFAULT_ICON_URL_ANONIM = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U/My8/LzI3PyU/P18sqSAcAfV8RGA=='))
        self.plurl_anonim = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoaEGpeWBhaauiRllniGJlUZlBRWJHoEA50UXSQ=='))
        self.DEFAULT_ICON_URL_PCX = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9IrojPyU/P18sqSAcASwgP4Q=='))
        self.plurl_pcx = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoaXFYdkhhc75LlGO5QHhuaZGFQGlEeUA6pcXWQ=='))
        self.DEFAULT_ICON_URL_BITECH = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U/KLElNzojPyU/P18sqSAcAfIkRBQ=='))
        self.plurl_bitech = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoSmpiaWmYRZF+Y55aQbxfv6ZHi6BBekA5jMW/Q=='))
        self.DEFAULT_ICON_URL_THEHUB = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S/JSM0oTYrPyU/P18sqSAcAfXQRFg=='))
        self.plurl_thehub = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoT66oc7xERFBAemJQabmmRGBFu6mkekA22oWKg=='))
        self.DEFAULT_ICON_URL_RPLAIR = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S8qyEnMLIrPyU/P18sqSAcAfekRIA=='))
        self.plurl_rplair = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoVURJq5uZb4hUZEG5saFhiVuqdlJkekA3zIWnw=='))
        self.DEFAULT_ICON_URL_TECHFUNDO = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9JTc5IK81LyY/PyU/P18sqSAcAs9USVg=='))
        self.plurl_techfundo = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoVFZuUk5Yb7OQeEurq5pKTmhwemuiYEA5lgW9A=='))
        self.fnmts = zlib.decompress(base64.b64decode('eJzTTy1J1k/Ny0zPTTTSTzXKLMhJrEwtKklNzsjLzE4EAKcpC0E='))
        self.vivn = GetIPTVPlayerVerstion()
        self.porv = self.gits()
        self.pbtp = '-'
        self.adfrid = '2'
        self.btps = config.plugins.iptvplayer.boxtipus.value
        self.brdr = config.plugins.iptvplayer.boxrendszer.value
        self.aid = config.plugins.iptvplayer.technika_id.value
        self.lfbnsz = config.plugins.iptvplayer.technika_legfrissebb_napok.value
        self.ytp = YouTubeParser()
        self.aid_ki = ''
        self.ilk = False
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}        

    def getFullIconUrl(self, url):
        return CBaseHostClass.getFullIconUrl(self, url.replace('&amp;', '&'))
        
    def getStringToLowerWithout(self, szoveg):
        bv = ''
        if szoveg != '':
            szoveg = szoveg.replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ö','o').replace('ő','o').replace('ú','u').replace('ü','u').replace('ű','u')
            szoveg = szoveg.replace('Á','a').replace('É','e').replace('Í','i').replace('Ó','o').replace('Ö','o').replace('Ő','o').replace('Ú','u').replace('Ü','u').replace('Ű','u')
            bv = szoveg.lower()
        return bv

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data
        
    def listMainMenu(self, cItem):
        try:
            if not self.ebbtit(): return
            if self.btps != '' and self.brdr != '': self.pbtp = self.btps.strip() + ' - ' + self.brdr.strip()
            self.fldtm()
            if self.muvesegyzs(self.muves('1','15')) == 'vfv':
                msg = zlib.decompress(base64.b64decode('eJw7PCtLoSy1qCrz8GaFwyuLMlJLjk5USM1R5OJyK8osLj68tuTwymKFRAUlj1CFkNSc1AKgyNGJSgrZqUWpJUWpeSnFValFSUcn5ijkpAI1Fx9emZ5arAgAYmIlJg=='))
                self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10)
            url_legfris = 'technika_legfrissebb'
            desc_legfris = self.getdvdsz(url_legfris, 'Legfrissebb technikai adások, műsorok és információk gyűjtőhelye...')
            url_techcsat = 'technika_csatornak'
            desc_techcsat = self.getdvdsz(url_techcsat, 'Tech műsorcsatornák - TECH2, POWERTECH, MOBEEL, ITFROCCS, TECHVIDEOHU, HASZNÁLT DROID, THEVR TECH, NOTEBOOK.HU, APPLE PIE, SHADOWWARRIOR, HUNBOXING, BYTECH, TECHKALAUZ, TECHDOBOZ, ANONIMINC, PCX, BITECH, THE HUB, RPS LAIR, TECHFUNDO - műsorai...')
            url_erdekesseg = 'technika_erdekesseg'
            desc_erdekesseg = self.getdvdsz(url_erdekesseg, 'Tech videó érdekességek megjelenítése...')
            tab_ajanlott = 'technika_ajanlott'
            desc_ajanlott = self.getdvdsz(tab_ajanlott, 'Ajánlott, nézett tartalmak megjelenítése...')
            tab_search = 'technika_kereses'
            desc_search = self.getdvdsz(tab_search, 'Keresés...')
            tab_kereses_lehetoseg = 'technika_kereses_lehetoseg'
            desc_kereses_lehetoseg = self.getdvdsz(tab_kereses_lehetoseg, 'Keresett videók megjelenítése, Keresés az előzmények között...')
            url_info = 'technika_informacio'
            desc_info = self.getdvdsz(url_info, 'Információk megjelenítése...')
            MAIN_CAT_TAB = [
                            {'category':'list_main', 'title': 'Legfrissebb videók', 'url': url_legfris, 'tab_id': 'legfrissebb', 'desc': desc_legfris},
                            {'category':'list_main', 'title': 'Tech csatornák videói', 'url': url_techcsat, 'tab_id': 'techcsat', 'desc': desc_techcsat},
                            {'category':'list_main', 'title': 'Tech videó érdekességek', 'url': url_erdekesseg, 'tab_id':'erdekesseg', 'desc':desc_erdekesseg},
                            {'category':'list_main', 'title': 'Ajánlott, nézett videók', 'tab_id':tab_ajanlott, 'desc':desc_ajanlott},
                            {'category':'search', 'title': _('Search'), 'search_item': True, 'tps':'0', 'tab_id':tab_search, 'desc':desc_search},
                            {'category':'list_main', 'title': 'Keresési lehetőségek', 'tab_id':tab_kereses_lehetoseg, 'desc':desc_kereses_lehetoseg}
                           ]
            self.listsTab(MAIN_CAT_TAB, {'name':'category'})
            params = dict(cItem)
            params = {'good_for_fav': False, 'title':'Információ', 'url': url_info, 'desc':desc_info, 'icon':self.DEFAULT_ICON_URL, 'art_id':'foinformacio', 'type':'article'}
            self.addArticle(params)
            vtb = self.malvadnav(cItem, '7', '15', '4', '13')
            if len(vtb) > 0:
                for item in vtb:
                    if len(item['desc']) > 0:
                        tempdesc = item['desc']
                        if tempdesc.startswith('ID'):
                            tlt = tempdesc.find('\n')
                            if -1 < tlt:
                                tempdesc = tempdesc[tlt+1:].strip()
                        if not tempdesc.startswith('Csatorna'):
                            ttmb = tempdesc.split('Tartalom:')
                            if len(ttmb) == 2:
                                tempdesc = 'Csatorna:  ' + self.cslkrs(item['tpe']) + '\n' + ttmb[0]
                                tempdesc = tempdesc + 'Tartalom:\n' + re.sub(r'^(.{450}).*$', '\g<1>...', ttmb[1].replace('\n','').strip())
                        item['desc'] = tempdesc
                    item['category'] = 'list_third'
                    self.addVideo(item)
            self.ilk = True
        except Exception:
            return
            
    def getLinksForVideo(self, cItem):
        try:
            tabID = cItem.get('tab_id', '')
            if tabID in ['tech2','powertech','mobeel','itfrocs','techvideo','hdroid','vrtech','nbook','apie','shadowwarrior','hunboxing','bytech','techkalauz','techdoboz','anonim','pcx','bitech','thehub','rplair','techfundo']:
                nez = self.Yt_getLinksForVideo(cItem)
                if len(nez) > 0:
                    self.susn('2', '15', cItem['url'])
                return nez
            else:
                return []    
        except Exception:
            return []
            
    def Yt_getLinksForVideo(self, cItem):
        url = cItem['url']
        tpe = cItem['tpe']
        title = cItem['title']
        temp_title = self.rpttl(title, tpe)
        try:
            if cItem['url'] != '' and cItem['title'] != '':
                if 1 == self.up.checkHostSupport(url):
                    if cItem['category'] != 'list_third':
                        temp_desc = cItem['desc']
                        if temp_desc.startswith('ID'):
                            tlt = temp_desc.find('\n')
                            if -1 < tlt:
                                temp_desc = temp_desc[tlt+1:].strip()
                        self.fvunz(url, tpe)
                        self.susmrgts('2', '15', '4', cItem['tpe'], cItem['url'], temp_title, cItem['icon'], temp_desc, 'mnez', cItem['time'])
                    return self.up.getVideoLinkExt(url)
                else:
                    return []
            else:
                return []
        except Exception:
            return []
            
    def rpttl(self, title='', tpe=''):
        bv = ''
        try:
            if title != '' and tpe != '':
                if tpe == '30': bv = title.replace('Tech2 - ','').strip()
                if tpe == '31': bv = title.replace('PowerTech - ','').strip()
                if tpe == '32': bv = title.replace('Mobeel - ','').strip()
                if tpe == '33': bv = title.replace('ITFroccs - ','').strip()
                if tpe == '34': bv = title.replace('TechVideoHU - ','').strip()
                if tpe == '35': bv = title.replace('Hasznalt Droid - ','').strip()
                if tpe == '36': bv = title.replace('TheVR Tech - ','').strip()
                if tpe == '37': bv = title.replace('Notebook.hu - ','').strip()
                if tpe == '38': bv = title.replace('Apple Pie - ','').strip()
                if tpe == '39': bv = title.replace('ShadowWarrior - ','').strip()
                if tpe == '40': bv = title.replace('Hunboxing - ','').strip()
                if tpe == '41': bv = title.replace('ByTech - ','').strip()
                if tpe == '42': bv = title.replace('TechKalauz - ','').strip()
                if tpe == '43': bv = title.replace('TechDoboz - ','').strip()
                if tpe == '44': bv = title.replace('AnonimInc - ','').strip()
                if tpe == '45': bv = title.replace('PCX - ','').strip()
                if tpe == '46': bv = title.replace('BiTech - ','').strip()
                if tpe == '47': bv = title.replace('The HUB - ','').strip()
                if tpe == '48': bv = title.replace('RPs Lair - ','').strip()
                if tpe == '49': bv = title.replace('TechFunDo - ','').strip()
                
            return bv
        except Exception:
            return ''            
            
    def fvunz(self, fun='', tpe=''):
        encoding = 'utf-8'
        flist = []
        pi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if fun != '' and tpe != '':
                if fileExists(self.fnmts):
                    with codecs.open(self.fnmts, 'r', encoding, 'replace') as fpr:
                        data = fpr.readlines()
                    if len(data) > 0:
                        for item in data:
                            tit = item.replace('\n','').strip()
                            tstm = tit.split(' | ')
                            if len(tstm) == 3:
                                pd = {'time': tstm[0].strip(), 'tpe':tstm[1].strip(), 'url': tstm[2].strip()}
                                flist.append(pd)
                        pd = {'time': pi, 'tpe':tpe, 'url': fun}
                        flist.append(pd)
                        if len(flist) > 0:
                            flist = sorted(flist, key=lambda i: (i['time']), reverse=True)
                        if len(flist) > 0:
                            self.fkrs(flist)
                else:
                    with codecs.open(self.fnmts, 'w', encoding, 'replace') as fpw:
                        fpw.write("%s | %s | %s\n" % (pi,tpe,fun))                
        except Exception:
            return
            
    def fldtm(self):
        encoding = 'utf-8'
        hiba = False
        flist = []
        try:
            try:
                with codecs.open(self.fnmts, 'r', encoding, 'replace') as fr:
                    for line in fr:
                        line = line.replace('\n', '').strip()
                        if len(line) > 0:
                            tstm = line.split(' | ')
                            if len(tstm) == 3:
                                datum = datetime.strptime(tstm[0].strip(), "%Y-%m-%d %H:%M:%S").date()
                                akt_datum = datetime.now().date()
                                kulonbseg = (akt_datum - datum).days
                                if kulonbseg >= 0 and kulonbseg < int(self.lfbnsz):
                                    pd = {'time': tstm[0].strip(), 'tpe':tstm[1].strip(), 'url': tstm[2].strip()}
                                    flist.append(pd)
                if len(flist) > 0:
                    flist = sorted(flist, key=lambda i: (i['time']), reverse=True)
            except Exception:
                hiba = True
        finally:
            if not hiba and len(flist) > 0:
                self.fkrs(flist)
            
    def fnbvn(self, fun=''):
        encoding = 'utf-8'
        bv = False
        try:
            if fun != '':
                if fileExists(self.fnmts):
                    with codecs.open(self.fnmts, 'r', encoding, 'replace') as fpr:
                        data = fpr.readlines()
                    for item in data:
                        tit = item.replace('\n','').strip()
                        if fun in tit:
                            bv = True
                            break
            return bv
        except Exception:
            return False
        
    def fkrs(self, flist=[]):
        encoding = 'utf-8'
        ltfn = self.fnmts + '.writing'
        if fileExists(ltfn):
            rm(ltfn)
        try:
            if len(flist) > 0:
                fpw = codecs.open(ltfn, 'w', encoding, 'replace')
                for item in flist:
                    fpw.write("%s | %s | %s\n" % (item['time'],item['tpe'],item['url']))
                fpw.flush()
                os.fsync(fpw.fileno())
                fpw.close()
                os.rename(ltfn, self.fnmts)
                if fileExists(ltfn):
                    rm(ltfn)
        except Exception:
            if fileExists(ltfn):
                rm(ltfn)
        
    def listSecondItems(self, cItem):
        try:
            tabID = cItem.get('tab_id', '')
            if tabID == 'tech2':
                self.Ytpl_lista(cItem, tabID, 'tech2')                
            elif tabID == 'powertech':
                self.Ytpl_lista(cItem, tabID, 'powertech')
            elif tabID == 'mobeel':
                self.Ytpl_lista(cItem, tabID, 'mobeel')
            elif tabID == 'itfrocs':
                self.Ytpl_lista(cItem, tabID, 'itfrocs')
            elif tabID == 'techvideo':
                self.Ytpl_lista(cItem, tabID, 'techvideo')
            elif tabID == 'hdroid':
                self.Ytpl_lista(cItem, tabID, 'hdroid')
            elif tabID == 'vrtech':
                self.Ytpl_lista(cItem, tabID, 'vrtech')
            elif tabID == 'nbook':
                self.Ytpl_lista(cItem, tabID, 'nbook')
            elif tabID == 'apie':
                self.Ytpl_lista(cItem, tabID, 'apie')
            elif tabID == 'shadowwarrior':
                self.Ytpl_lista(cItem, tabID, 'shadowwarrior')
            elif tabID == 'hunboxing':
                self.Ytpl_lista(cItem, tabID, 'hunboxing')
            elif tabID == 'bytech':
                self.Ytpl_lista(cItem, tabID, 'bytech')
            elif tabID == 'techkalauz':
                self.Ytpl_lista(cItem, tabID, 'techkalauz')
            elif tabID == 'techdoboz':
                self.Ytpl_lista(cItem, tabID, 'techdoboz')
            elif tabID == 'anonim':
                self.Ytpl_lista(cItem, tabID, 'anonim')
            elif tabID == 'pcx':
                self.Ytpl_lista(cItem, tabID, 'pcx')
            elif tabID == 'bitech':
                self.Ytpl_lista(cItem, tabID, 'bitech')
            elif tabID == 'thehub':
                self.Ytpl_lista(cItem, tabID, 'thehub')
            elif tabID == 'rplair':
                self.Ytpl_lista(cItem, tabID, 'rplair')
            elif tabID == 'techfundo':
                self.Ytpl_lista(cItem, tabID, 'techfundo')
            else:
                return
        except Exception:
            return

    def Ytpl_lista(self, cItem, tabID, mk='tech2'):
        llst = []
        templlst = []
        ln = 0
        friss_kell = False
        category = 'playlist'
        url = cItem['plurl']
        tpe = cItem['tpe']
        page = '1'
        self.susn('2', '15', cItem['url'])
        params = dict(cItem)
        try:
            if url != '' and tabID != '':
                llst = self.Ytlfl(tabID, url, tpe, mk, False)
                if self.fdmgnz('4', '15', tpe):
                    friss_kell = True
                for item in llst:
                    if item['title'] == '': continue
                    templlst.append(item)
                    temp_desc = item['desc']
                    if temp_desc.startswith('ID'):
                        tlt = temp_desc.find('\n')
                        if -1 < tlt:
                            temp_desc = temp_desc[tlt+1:].strip()
                    #ttitle = re.sub(r'[^\x00-\x7f]',r'', item['title'])
                    ttitle = item['title']
                    temp_title = self.rpttl(ttitle, tpe)
                    if friss_kell:
                        self.susmrgts('2', '15', '4', item['tpe'], item['url'], temp_title, item['icon'], temp_desc, '', item['time'])
                    ln += 1
                    if ln > 150: break
                if friss_kell:
                    self.fdnvls('5','15',tpe,self.adfrid)
            self.currList = templlst
        except Exception:
            self.currList = []
            
    def Ytlfl(self, tabID, url='', tpe='', mk='tech2', elso=False):
        params = dict()
        if url != '' and tpe != '':
            playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
            baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
            currList = []
            if baseUrl != '':
                sts, data = self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
                try:
                    data = json_loads(data)['video']
                    for item in data:
                        url = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
                        if mk in ['tech2','mobeel','techvideo','hdroid','vrtech','nbook','apie','shadowwarrior','hunboxing','bytech','techkalauz','techdoboz','anonim','pcx','bitech','thehub','techfundo']:
                            title = CParsingHelper.cleanHtmlStr(item['title']).strip()
                        if mk == 'powertech':
                            title = CParsingHelper.cleanHtmlStr(item['title']).replace('| PowerTech.hu','').strip()
                        if mk == 'itfrocs':    
                            title = CParsingHelper.cleanHtmlStr(item['title']).replace('| ITFroccs.hu','').strip()
                        if mk == 'rplair':
                            title = CParsingHelper.cleanHtmlStr(item['title']).replace("- RP's Lair",'').strip()
                        #title = re.sub(r'[^\x00-\x7f]',r'', title)
                        title = self.rpttl(title, tpe)    
                        img = item['thumbnail']
                        time = item['duration']
                        #added  = item['added']
                        date_time = datetime.fromtimestamp(item['time_created'])
                        added = date_time.strftime("%Y.%m.%d.")
                        tempdesc = item['description']
                        tempdesc = tempdesc.replace('\n','')
                        if mk == 'tech2': tempdesc = self.szovegki_tech2(tempdesc)
                        if mk == 'powertech': tempdesc = self.szovegki_powertech(tempdesc)
                        if mk == 'mobeel': tempdesc = self.szovegki_mobeel(tempdesc)
                        if mk == 'itfrocs': tempdesc = self.szovegki_itfrocs(tempdesc)
                        if mk == 'techvideo': tempdesc = self.szovegki_techvideo(tempdesc)
                        if mk == 'hdroid': tempdesc = self.szovegki_hdroid(tempdesc)
                        if mk == 'vrtech': tempdesc = self.szovegki_vrtech(tempdesc)
                        if mk == 'nbook': tempdesc = self.szovegki_nbook(tempdesc)
                        if mk == 'apie': tempdesc = self.szovegki_apie(tempdesc)
                        if mk == 'shadowwarrior': tempdesc = self.szovegki_shadowwarrior(tempdesc)
                        if mk == 'hunboxing': tempdesc = self.szovegki_hunboxing(tempdesc)
                        if mk == 'bytech': tempdesc = self.szovegki_bytech(tempdesc)
                        if mk == 'techkalauz': tempdesc = self.szovegki_techkalauz(tempdesc)
                        if mk == 'techdoboz': tempdesc = self.szovegki_techdoboz(tempdesc)
                        if mk == 'anonim': tempdesc = self.szovegki_anonim(tempdesc)
                        if mk == 'pcx': tempdesc = self.szovegki_pcx(tempdesc)
                        if mk == 'bitech': tempdesc = self.szovegki_bitech(tempdesc)
                        if mk == 'thehub': tempdesc = self.szovegki_thehub(tempdesc)
                        if mk == 'rplair': tempdesc = self.szovegki_rplair(tempdesc)
                        if mk == 'techfundo': tempdesc = self.szovegki_techfundo(tempdesc)
                        tempdesc = tempdesc.strip()
                        if tempdesc == '': tempdesc = title
                        if elso:
                            desc = added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
                            params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tpe': tpe}
                            break
                        else:
                            n_de = self.malvadst('1', '15', url)
                            if n_de != '' and self.aid:
                                self.aid_ki = 'ID: ' + n_de + '\n'
                            else:
                                self.aid_ki = ''
                            desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
                            params_temp = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID, 'tpe': tpe}
                            currList.append(params_temp)
                except Exception:
                    if elso:
                        return params
                    else:
                        return []
            if len(currList) > 0:        
                currList = sorted(currList, key=lambda i: (i['time'], i['title'])) 
                return reversed(currList)
            else:
                if elso:
                    return params
                else:
                    return []
        else:
            if elso:
                return params
            else:
                return []
                
    def szovegki_techfundo(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Támogass')
                bv = self.szovegkivetel(bv,'Támogatás')
                bv = self.szovegkivetel(bv,'Segítesz')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Csatlakozz')
                bv = self.szovegkivetel(bv,'Iratkozz')
                bv = self.szovegkivetel(bv,'Link a')
                bv = self.szovegkivetel(bv,'Adsz bele')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = self.szovegkivetel(bv,'www.')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_rplair(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Dobj egy')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Arukereso')
                bv = self.szovegkivetel(bv,'Tedd fel')
                bv = self.szovegkivetel(bv,'Duma link')
                bv = self.szovegkivetel(bv,'---')
                bv = self.szovegkivetel(bv,'Csatlakozz')
                bv = self.szovegkivetel(bv,'Patriot')
                bv = self.szovegkivetel(bv,'Megéri?')
                bv = self.szovegkivetel(bv,'Szemelyre szabott')
                bv = self.szovegkivetel(bv,'Egyedi hosszu')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_thehub(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Holoszoba')
                bv = self.szovegkivetel(bv,'Ha tetszett a')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_bitech(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'facebook')
                bv = self.szovegkivetel(bv,'Instagram')
                bv = self.szovegkivetel(bv,'Regisztráció')
                bv = self.szovegkivetel(bv,'Ha tetszett a videó')
                bv = self.szovegkivetel(bv,'Remélem tetszett')
                bv = self.szovegkivetel(bv,'Patreon')
                bv = self.szovegkivetel(bv,'---')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_pcx(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'A videóban látható')
                bv = self.szovegkivetel(bv,'A videóban szereplő')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_anonim(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Itt tudod megvenni')
                bv = self.szovegkivetel(bv,'Vásárlási')
                bv = self.szovegkivetel(bv,'További információ')
                bv = self.szovegkivetel(bv,'VEDD MEG')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Hivatalos Weboldal')
                bv = self.szovegkivetel(bv,'Támogatnál?')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_techdoboz(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'WEB')
                bv = self.szovegkivetel(bv,'Termékleírást')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_techkalauz(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Vásárlás')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Weboldal')
                bv = self.szovegkivetel(bv,'techkalauz.hu')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_bytech(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Itten lehet')
                bv = self.szovegkivetel(bv,'A terméket itt')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_hunboxing(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Részletek')
                bv = self.szovegkivetel(bv,'Vásárlás')
                bv = self.szovegkivetel(bv,'Bővebben')
                bv = self.szovegkivetel(bv,'Bővebb')
                bv = self.szovegkivetel(bv,'Regisztrálj')
                bv = self.szovegkivetel(bv,'Több infó')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Instagram')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_shadowwarrior(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'***')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_tech2(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'További információ')
                bv = self.szovegkivetel(bv,'További részletek')
                bv = self.szovegkivetel(bv,'Közösségi csoportunk')
                bv = self.szovegkivetel(bv,'Bővebb információ')
                bv = self.szovegkivetel(bv,'Kövessetek minket')
                bv = self.szovegkivetel(bv,'katt a linkre')
                bv = self.szovegkivetel(bv,'További infó')
                bv = self.szovegkivetel(bv,'Vásárlás')
                bv = self.szovegkivetel(bv,'Ha megvennéd')
                bv = self.szovegkivetel(bv,'Link')
                bv = self.szovegkivetel(bv,'Linkek')
                bv = self.szovegkivetel(bv,'Ha érdekel')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Instagram')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_powertech(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Cikk')
                bv = self.szovegkivetel(bv,'cikk')
                bv = self.szovegkivetel(bv,'weboldal')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_mobeel(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Elérhetőség')
                bv = self.szovegkivetel(bv,'A tesztben látható')
                bv = self.szovegkivetel(bv,'A videóban látható')
                bv = self.szovegkivetel(bv,'az alábbi linken')
                bv = self.szovegkivetel(bv,'Üzleteink listája')
                bv = self.szovegkivetel(bv,'Az üzlet elérhetősége')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_itfrocs(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'| ITFroccs.hu')
                bv = self.szovegkivetel(bv,'Cikk')
                bv = self.szovegkivetel(bv,'Web:')
                bv = self.szovegkivetel(bv,'írjon nekünk')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_techvideo(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Ezt légyszi')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Instagram')
                bv = self.szovegkivetel(bv,'Forrás')
                bv = self.szovegkivetel(bv,'Nézzétek live')
                bv = self.szovegkivetel(bv,'Ti mit szóltok')
                bv = self.szovegkivetel(bv,'Felvétel és vágás')
                bv = self.szovegkivetel(bv,'Vedd meg')
                bv = self.szovegkivetel(bv,'A Nyereményjáték')
                bv = self.szovegkivetel(bv,'#Techvideo')
                bv = self.szovegkivetel(bv,'#Galaxy')
                bv = self.szovegkivetel(bv,'#Porszivo')
                bv = self.szovegkivetel(bv,'#Ariv')
                bv = self.szovegkivetel(bv,'#Asus')
                bv = self.szovegkivetel(bv,'#Honor')
                bv = self.szovegkivetel(bv,'#Huawei')
                bv = self.szovegkivetel(bv,'#Sharp')
                bv = self.szovegkivetel(bv,'#qualcomm')
                bv = self.szovegkivetel(bv,'#MWC')
                bv = self.szovegkivetel(bv,'#Samsung')
                bv = self.szovegkivetel(bv,'#bakik')
                bv = self.szovegkivetel(bv,'Blog')
                bv = self.szovegkivetel(bv,'Amazon.com')
                bv = self.szovegkivetel(bv,'Első benyomás')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = self.szovegkivetel(bv,'-----')
                bv = self.szovegkivetel(bv,'www.youtube')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_hdroid(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'stylebolt.hu')
                bv = self.szovegkivetel(bv,'HasznaltAndroid')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Nézd meg élőben')
                bv = self.szovegkivetel(bv,'Lurdy')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_vrtech(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'Nézd meg élőben')
                bv = self.szovegkivetel(bv,'Még több infó')
                bv = self.szovegkivetel(bv,'A termék és további')
                bv = self.szovegkivetel(bv,'További infó')
                bv = self.szovegkivetel(bv,'Bővebb infó')
                bv = self.szovegkivetel(bv,'MIVEL NYOMJUK')
                bv = self.szovegkivetel(bv,'Itt csekkolhatjátok')
                bv = self.szovegkivetel(bv,'Részletek')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_nbook(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'----')
                bv = self.szovegkivetel(bv,'Csak kattints')
                bv = self.szovegkivetel(bv,'notebook.hu')
                bv = self.szovegkivetel(bv,'Notebook.hu')
                bv = self.szovegkivetel(bv,'További részletek')
                bv = self.szovegkivetel(bv,'Csapj le rá')
                bv = self.szovegkivetel(bv,'Termék link')
                bv = self.szovegkivetel(bv,'Link')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegki_apie(self, txt=''):
        bv = ''
        try:
            if txt != '':
                bv = txt
                bv = self.szovegkivetel(bv,'Csatlakozz')
                bv = self.szovegkivetel(bv,'LINK')
                bv = self.szovegkivetel(bv,'Cikk link')
                bv = self.szovegkivetel(bv,'Apple Pie')
                bv = self.szovegkivetel(bv,'APPLE PIE')
                bv = self.szovegkivetel(bv,'A videót támogatta')
                bv = self.szovegkivetel(bv,'Amennyiben te')
                bv = self.szovegkivetel(bv,'KATT')
                bv = self.szovegkivetel(bv,'Katt')
                bv = self.szovegkivetel(bv,'Ajándék')
                bv = self.szovegkivetel(bv,'Regisztrálj itt')
                bv = self.szovegkivetel(bv,'Támogasd')
                bv = self.szovegkivetel(bv,'Facebook')
                bv = self.szovegkivetel(bv,'http')
                bv = self.szovegkivetel(bv,'https')
                bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
            return bv
        except Exception:
            return ''
            
    def szovegkivetel(self, txt='', msg=''):
        bv = ''
        try:
            if txt != '' and msg != '':
                bv = txt
                tlt = txt.find(msg)
                if -1 < tlt:
                    if 0 < tlt:
                        bv = txt[:tlt].strip()
                    else:
                        bv = ''
            return bv
        except Exception:
            return ''
        
    def listMainItems(self, cItem):
        try:
            tabID = cItem.get('tab_id', '')
            if tabID == 'legfrissebb':
                self.Legfrissebb_MainItems(cItem, tabID)
            elif tabID == 'techcsat':
                self.MusorMainMenu(cItem, tabID)
            elif tabID == 'erdekesseg':
                self.ErdekesMainMenu(cItem, tabID)
            elif tabID == 'technika_ajanlott':
                self.Fzkttm(cItem, tabID)
            elif tabID == 'technika_kereses_lehetoseg':
                self.KeresesMainMenu(cItem, tabID)
            elif tabID == 'technika_keresett_tartalom':
                self.Vdakstmk({'name':'history', 'category': 'search', 'tab_id':''}, 'desc', _("Type: "), tabID)
            else:
                return
        except Exception:
            return
            
    def MusorMainMenu(self, cItem, tabID):
        url = cItem['url']
        self.susn('2', '15', url)
        url_tech2 = 'technika_tech2_csatorna'
        desc_tech2 = self.getdvdsz(url_tech2, 'Tech2.hu csatorna videói...\n\nHírek, tesztek, videók.')
        url_powertech = 'technika_powertech_csatorna'
        desc_powertech = self.getdvdsz(url_powertech, 'PowerTech csatorna videói...\n\nÉrdekességek, bemutatók, kütyük a notebook, mobil, a tech világából. Minden amivel találkozhatunk napjainkban és megkönnyíti, esetleg megnehezíti az életünket.')
        url_mobeel = 'technika_mobeel_csatorna'
        desc_mobeel = self.getdvdsz(url_mobeel, 'Mobeel - Mobil Világ csatorna videói...\n\nTelefon tesztek, telefon kiegészítő bemutató. Hírek a tech világából.')
        url_itfrocs = 'technika_itfrocs_csatorna'
        desc_itfrocs = self.getdvdsz(url_itfrocs, 'ITFroccs csatorna videói...\n\nSzoftver - Hardver újdonságok, tesztek, megoldások egy helyen.')
        url_techvideo = 'technika_techvideo_csatorna'
        desc_techvideo = self.getdvdsz(url_techvideo, 'TechVideoHU csatorna videói...\n\nA legfrissebb híreket és termék teszteket találod meg itt érthetően, képekkel, magyar videókkal karöltve.')
        url_hdroid = 'technika_hdroid_csatorna'
        desc_hdroid = self.getdvdsz(url_hdroid, 'Hasznalt Droid csatorna videói...\n\nInformációk, videók a legfrissebb hírekkel és tesztekkel.')
        url_vrtech = 'technika_vrtech_csatorna'
        desc_vrtech = self.getdvdsz(url_vrtech, 'TheVR Tech csatorna videói...\n\nA TheVR Tech célja, hogy megmutassa az embereknek, hogy milyen technológiák fogják megváltoztatni a jövőnket, illetve hogy milyen jelenlegi termékek/technológiák vannak, amelyekkel érdemes foglalkozni.')
        url_nbook = 'technika_nbook_csatorna'
        desc_nbook = self.getdvdsz(url_nbook, 'Notebook.hu csatorna videói...\n\nNotebookról, ultrabookról, tabletről és okostelefonról szóló információkat lehet itt megtekinteni.')
        url_apie = 'technika_apie_csatorna'
        desc_apie = self.getdvdsz(url_apie, 'Apple Pie csatorna videói...\n\nEz a csatonra leginkább az Apple-ről szól, azonban néha más menő cuccok is bemutatásra kerülnek.')
        url_shadowwarrior = 'technika_shadowwarrior_csatorna'
        desc_shadowwarrior = self.getdvdsz(url_shadowwarrior, 'ShadowWarrior csatorna videói...\n\nA ShadowWarrior csatorna, egy független forrás, amely különféle hardver és gamer témával kapcsolatban jelentkezik újabb és újabb videokkal.')
        url_hunboxing = 'technika_hunboxing_csatorna'
        desc_hunboxing = self.getdvdsz(url_hunboxing, 'Hunboxing csatorna videói...\n\nKülönféle eszközök tesztelése, bemutatása. TV, telefon, okos otthon és egyéb kiegészítő tesztek.')
        url_bytech = 'technika_bytech_csatorna'
        desc_bytech = self.getdvdsz(url_bytech, 'ByTech csatorna videói...\n\nTechnikai kütyük tesztelése.')
        url_techkalauz = 'technika_techkalauz_csatorna'
        desc_techkalauz = self.getdvdsz(url_techkalauz, 'TechKalauz csatorna videói...\n\nKülönféle eszközök tesztelése, bemutatása.')
        url_techdoboz = 'technika_techdoboz_csatorna'
        desc_techdoboz = self.getdvdsz(url_techdoboz, 'TechDoboz csatorna videói...\n\nKülönféle eszközök tesztelése, bemutatása.')
        url_anonim = 'technika_anonim_csatorna'
        desc_anonim = self.getdvdsz(url_anonim, 'AnonimInc csatorna videói...\n\nA Tech minden oldala: Népszerű, külföldi, limitált, prémium, komplikált, olcsó, hangos, méretes, nálam mindent megtalálsz. Hangszórók, telefonok, laptopok, egerek, tabletek, billentyűzetek, fejhallgatók, drónok, és sok minden más. Éljen a mindenható Tech.')
        url_pcx = 'technika_pcx_csatorna'
        desc_pcx = self.getdvdsz(url_pcx, 'PCX csatorna videói...\n\nSzámítógépek minden mennyiségben.')
        url_bitech = 'technika_bitech_csatorna'
        desc_bitech = self.getdvdsz(url_bitech, 'BiTech csatorna videói...\n\nKülönféle eszközök tesztelése, bemutatása.')
        url_thehub = 'technika_thehub_csatorna'
        desc_thehub = self.getdvdsz(url_thehub, 'The HUB csatorna videói...\n\nKülönféle eszközök tesztelése, bemutatása.')
        url_rplair = 'technika_rplair_csatorna'
        desc_rplair = self.getdvdsz(url_rplair, 'RPs Lair csatorna videói...\n\nBonyolult Tech, Egyszerűen! Magyarország legtechnikaibb tech csatornája. Részletek egészen az utolsó legkisebb alkatrészig.')
        url_techfundo = 'technika_techfundo_csatorna'
        desc_techfundo = self.getdvdsz(url_techfundo, 'TechFunDo csatorna videói...\n\nNem vagyok egészen normális és bírom a tech kütyüket. Há mondom kotyvasztok ebből egy csatornát, meméne!?')
        MR_CAT_TAB = [
                      {'category':'list_second', 'title': 'Tech2', 'url': url_tech2, 'plurl': self.plurl_tech2, 'tab_id': 'tech2', 'icon': self.DEFAULT_ICON_URL_TECH2, 'desc': desc_tech2, 'tpe':'30'},
                      {'category':'list_second', 'title': 'PowerTech', 'url': url_powertech, 'plurl': self.plurl_powertech, 'tab_id': 'powertech', 'icon': self.DEFAULT_ICON_URL_POWERTECH, 'desc': desc_powertech, 'tpe':'31'},
                      {'category':'list_second', 'title': 'Mobeel - Mobil Világ', 'url': url_mobeel, 'plurl': self.plurl_mobeel, 'tab_id': 'mobeel', 'icon': self.DEFAULT_ICON_URL_MOBEEL, 'desc': desc_mobeel, 'tpe':'32'},
                      {'category':'list_second', 'title': 'ITFroccs', 'url': url_itfrocs, 'plurl': self.plurl_itfrocs, 'tab_id': 'itfrocs', 'icon': self.DEFAULT_ICON_URL_ITFROCS, 'desc': desc_itfrocs, 'tpe':'33'},
                      {'category':'list_second', 'title': 'TechVideoHU', 'url': url_techvideo, 'plurl': self.plurl_techvideo, 'tab_id': 'techvideo', 'icon': self.DEFAULT_ICON_URL_TECHVIDEO, 'desc': desc_techvideo, 'tpe':'34'},
                      {'category':'list_second', 'title': 'Hasznalt Droid', 'url': url_hdroid, 'plurl': self.plurl_hdroid, 'tab_id': 'hdroid', 'icon': self.DEFAULT_ICON_URL_HDROID, 'desc': desc_hdroid, 'tpe':'35'},
                      {'category':'list_second', 'title': 'TheVR Tech', 'url': url_vrtech, 'plurl': self.plurl_vrtech, 'tab_id': 'vrtech', 'icon': self.DEFAULT_ICON_URL_VRTECH, 'desc': desc_vrtech, 'tpe':'36'},
                      {'category':'list_second', 'title': 'Notebook.hu', 'url': url_nbook, 'plurl': self.plurl_nbook, 'tab_id': 'nbook', 'icon': self.DEFAULT_ICON_URL_NBOOK, 'desc': desc_nbook, 'tpe':'37'},
                      {'category':'list_second', 'title': 'Apple Pie', 'url': url_apie, 'plurl': self.plurl_apie, 'tab_id': 'apie', 'icon': self.DEFAULT_ICON_URL_APIE, 'desc': desc_apie, 'tpe':'38'},
                      {'category':'list_second', 'title': 'ShadowWarrior', 'url': url_shadowwarrior, 'plurl': self.plurl_shadowwarrior, 'tab_id': 'shadowwarrior', 'icon': self.DEFAULT_ICON_URL_SHADOWWARRIOR, 'desc': desc_shadowwarrior, 'tpe':'39'},
                      {'category':'list_second', 'title': 'Hunboxing', 'url': url_hunboxing, 'plurl': self.plurl_hunboxing, 'tab_id': 'hunboxing', 'icon': self.DEFAULT_ICON_URL_HUNBOXING, 'desc': desc_hunboxing, 'tpe':'40'},
                      {'category':'list_second', 'title': 'ByTech', 'url': url_bytech, 'plurl': self.plurl_bytech, 'tab_id': 'bytech', 'icon': self.DEFAULT_ICON_URL_BYTECH, 'desc': desc_bytech, 'tpe':'41'},
                      {'category':'list_second', 'title': 'TechKalauz', 'url': url_techkalauz, 'plurl': self.plurl_techkalauz, 'tab_id': 'techkalauz', 'icon': self.DEFAULT_ICON_URL_TECHKALAUZ, 'desc': desc_techkalauz, 'tpe':'42'},
                      {'category':'list_second', 'title': 'TechDoboz', 'url': url_techdoboz, 'plurl': self.plurl_techdoboz, 'tab_id': 'techdoboz', 'icon': self.DEFAULT_ICON_URL_TECHDOBOZ, 'desc': desc_techdoboz, 'tpe':'43'},
                      {'category':'list_second', 'title': 'AnonimInc', 'url': url_anonim, 'plurl': self.plurl_anonim, 'tab_id': 'anonim', 'icon': self.DEFAULT_ICON_URL_ANONIM, 'desc': desc_anonim, 'tpe':'44'},
                      {'category':'list_second', 'title': 'PCX', 'url': url_pcx, 'plurl': self.plurl_pcx, 'tab_id': 'pcx', 'icon': self.DEFAULT_ICON_URL_PCX, 'desc': desc_pcx, 'tpe':'45'},
                      {'category':'list_second', 'title': 'BiTech', 'url': url_bitech, 'plurl': self.plurl_bitech, 'tab_id': 'bitech', 'icon': self.DEFAULT_ICON_URL_BITECH, 'desc': desc_bitech, 'tpe':'46'},
                      {'category':'list_second', 'title': 'The HUB', 'url': url_thehub, 'plurl': self.plurl_thehub, 'tab_id': 'thehub', 'icon': self.DEFAULT_ICON_URL_THEHUB, 'desc': desc_thehub, 'tpe':'47'},
                      {'category':'list_second', 'title': 'RPs Lair', 'url': url_rplair, 'plurl': self.plurl_rplair, 'tab_id': 'rplair', 'icon': self.DEFAULT_ICON_URL_RPLAIR, 'desc': desc_rplair, 'tpe':'48'},
                      {'category':'list_second', 'title': 'TechFunDo', 'url': url_techfundo, 'plurl': self.plurl_techfundo, 'tab_id': 'techfundo', 'icon': self.DEFAULT_ICON_URL_TECHFUNDO, 'desc': desc_techfundo, 'tpe':'49'}
                     ]
        random.shuffle(MR_CAT_TAB)
        self.listsTab(MR_CAT_TAB, cItem)
        
    def ErdekesMainMenu(self, cItem, tabID):
        url = cItem['url']
        try:
            self.susn('2', '15', url)
            self.Vajnltmsr(cItem)
        except Exception:
            return
            
    def Legfrissebb_MainItems(self, cItem, tabID):
        url = cItem['url']
        param_lista = [] 
        try:
            self.susn('2', '15', url)
            params = dict()
            params = self.Ytlfl('tech2', self.plurl_tech2, '30', 'tech2', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('powertech', self.plurl_powertech, '31', 'powertech', True)
            if params: param_lista.append(params)  
            params = self.Ytlfl('mobeel', self.plurl_mobeel, '32', 'mobeel', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('itfrocs', self.plurl_itfrocs, '33', 'itfrocs', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('techvideo', self.plurl_techvideo, '34', 'techvideo', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('hdroid', self.plurl_hdroid, '35', 'hdroid', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('vrtech', self.plurl_vrtech, '36', 'vrtech', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('nbook', self.plurl_nbook, '37', 'nbook', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('apie', self.plurl_apie, '38', 'apie', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('shadowwarrior', self.plurl_shadowwarrior, '39', 'shadowwarrior', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('hunboxing', self.plurl_hunboxing, '40', 'hunboxing', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('bytech', self.plurl_bytech, '41', 'bytech', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('techkalauz', self.plurl_techkalauz, '42', 'techkalauz', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('techdoboz', self.plurl_techdoboz, '43', 'techdoboz', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('anonim', self.plurl_anonim, '44', 'anonim', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('pcx', self.plurl_pcx, '45', 'pcx', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('bitech', self.plurl_bitech, '46', 'bitech', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('thehub', self.plurl_thehub, '47', 'thehub', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('rplair', self.plurl_rplair, '48', 'rplair', True)
            if params: param_lista.append(params)
            params = self.Ytlfl('techfundo', self.plurl_techfundo, '49', 'techfundo', True)
            if params: param_lista.append(params)
            if len(param_lista) > 0:
                param_lista = sorted(param_lista, key=lambda i: (i['time']), reverse=True)
                for item in param_lista:
                    tsz = '-'
                    tab_id = '-'
                    if not self.fnbvn(item['url']):
                        if item['tpe'] == '30':
                            tsz = 'Tech2 - '
                            tab_id = 'tech2'
                        if item['tpe'] == '31':
                            tsz = 'PowerTech - '
                            tab_id = 'powertech'
                        if item['tpe'] == '32':
                            tsz = 'Mobeel - '
                            tab_id = 'mobeel'
                        if item['tpe'] == '33':
                            tsz = 'ITFroccs - '
                            tab_id = 'itfrocs'
                        if item['tpe'] == '34':
                            tsz = 'TechVideoHU - '
                            tab_id = 'techvideo'
                        if item['tpe'] == '35':
                            tsz = 'Hasznalt Droid - '
                            tab_id = 'hdroid'
                        if item['tpe'] == '36':
                            tsz = 'TheVR Tech - '
                            tab_id = 'vrtech'
                        if item['tpe'] == '37':
                            tsz = 'Notebook.hu - '
                            tab_id = 'nbook'
                        if item['tpe'] == '38':
                            tsz = 'Apple Pie - '
                            tab_id = 'apie'
                        if item['tpe'] == '39':
                            tsz = 'ShadowWarrior - '
                            tab_id = 'shadowwarrior'
                        if item['tpe'] == '40':
                            tsz = 'Hunboxing - '
                            tab_id = 'hunboxing'
                        if item['tpe'] == '41':
                            tsz = 'ByTech - '
                            tab_id = 'bytech'
                        if item['tpe'] == '42':
                            tsz = 'TechKalauz - '
                            tab_id = 'techkalauz'
                        if item['tpe'] == '43':
                            tsz = 'TechDoboz - '
                            tab_id = 'techdoboz'
                        if item['tpe'] == '44':
                            tsz = 'AnonimInc - '
                            tab_id = 'anonim'
                        if item['tpe'] == '45':
                            tsz = 'PCX - '
                            tab_id = 'pcx'
                        if item['tpe'] == '46':
                            tsz = 'BiTech - '
                            tab_id = 'bitech'
                        if item['tpe'] == '47':
                            tsz = 'The HUB - '
                            tab_id = 'thehub'
                        if item['tpe'] == '48':
                            tsz = 'RPs Lair - '
                            tab_id = 'rplair'
                        if item['tpe'] == '49':
                            tsz = 'TechFunDo - '
                            tab_id = 'techfundo'   
                        if tsz != '-' and tab_id != '-':
                            item['title'] = tsz + item['title']
                            item = MergeDicts(item, {'good_for_fav': False, 'tab_id':tab_id})
                            self.addVideo(item)
        except Exception:
            return
            
    def kiirtt(self, params, tsz='', tab_id='-'):
        if params:
            if not self.fnbvn(params['url']):
                params['title'] = tsz + params['title']
                params = MergeDicts(params, {'good_for_fav': False, 'tab_id':tab_id})
                self.addVideo(params)
            
    def Fzkttm(self, cItem, tabID):
        try:
            self.susn('2', '15', tabID)
            tab_adt = 'technika_ajnlt_datum'
            desc_adt = self.getdvdsz(tab_adt, 'Ajánlott, nézett tartalmak megjelenítése dátum szerint...')
            tab_anzt = 'technika_ajnlt_nezettseg'
            desc_anzt = self.getdvdsz(tab_anzt, 'Ajánlott, nézett tartalmak megjelenítése nézettség szerint...')
            A_CAT_TAB = [
                         {'category':'list_third', 'title': 'Dátum szerint', 'tab_id':tab_adt, 'desc':desc_adt},
                         {'category':'list_third', 'title': 'Nézettség szerint', 'tab_id':tab_anzt, 'desc':desc_anzt} 
                        ]
            self.listsTab(A_CAT_TAB, cItem)
            try:
                vtb = self.malvadnav(cItem, '9', '15', '4')
                if len(vtb) > 0:
                    for item in vtb:
                        if not self.fnbvn(item['url']):
                            if len(item['desc']) > 0:
                                tempdesc = item['desc']
                                if tempdesc.startswith('ID'):
                                    tlt = tempdesc.find('\n')
                                    if -1 < tlt:
                                        tempdesc = tempdesc[tlt+1:].strip()
                                if not tempdesc.startswith('Csatorna'):
                                    ttmb = tempdesc.split('Tartalom:')
                                    if len(ttmb) == 2:
                                        tempdesc = 'Csatorna:  ' + self.cslkrs(item['tpe']) + '\n' + ttmb[0]
                                        tempdesc = tempdesc + 'Tartalom:\n' + re.sub(r'^(.{450}).*$', '\g<1>...', ttmb[1].replace('\n','').strip())
                                item['desc'] = tempdesc
                            item['category'] = 'list_main'
                            if item['url'] != '' and item['title'] != '':
                                self.addVideo(item)
            except Exception:
                pass
        except Exception:
            return
            
    def KeresesMainMenu(self, cItem, tabID):
        try:
            self.susn('2', '15', tabID)
            tab_keresett = 'technika_keresett_tartalom'
            desc_keresett = self.getdvdsz(tab_keresett, 'Keresett tartalmak megjelenítése...')
            tab_search_hist = 'technika_kereses_elozmeny'
            desc_search_hist = self.getdvdsz(tab_search_hist, 'Keresés az előzmények között...')
            K_CAT_TAB = [
                         {'category':'list_main', 'title': 'Keresett videók', 'tab_id':tab_keresett, 'desc':desc_keresett},
                         {'category':'search_history', 'title': _('Search history'), 'tps':'0', 'tab_id':tab_search_hist, 'desc':desc_search_hist} 
                        ]
            self.listsTab(K_CAT_TAB, cItem)
        except Exception:
            return
            
    def cslkrs(self, tpse=''):
        bv = ''
        try:
            if tpse != '':
                if tpse == '30': bv = 'Tech2'
                if tpse == '31': bv = 'PowerTech'
                if tpse == '32': bv = 'Mobeel - Mobil világ'
                if tpse == '33': bv = 'ITFroccs'
                if tpse == '34': bv = 'TechVideoHU'
                if tpse == '35': bv = 'Hasznalt Droid'
                if tpse == '36': bv = 'TheVR Tech'
                if tpse == '37': bv = 'Notebook.hu'
                if tpse == '38': bv = 'Apple Pie'
                if tpse == '39': bv = 'ShadowWarrior'
                if tpse == '40': bv = 'Hunboxing'
                if tpse == '41': bv = 'ByTech'
                if tpse == '42': bv = 'TechKalauz'
                if tpse == '43': bv = 'TechDoboz'
                if tpse == '44': bv = 'AnonimInc'
                if tpse == '45': bv = 'PCX'
                if tpse == '46': bv = 'BiTech'
                if tpse == '47': bv = 'The HUB'
                if tpse == '48': bv = 'RPs Lair'
                if tpse == '49': bv = 'TechFunDo'
            return bv
        except Exception:
            return ''
            
    def cslkrstid(self, tpse=''):
        bv = ' '
        try:
            if tpse != '':
                if tpse == '30': bv = 'tech2'
                if tpse == '31': bv = 'powertech'
                if tpse == '32': bv = 'mobeel'
                if tpse == '33': bv = 'itfrocs'
                if tpse == '34': bv = 'techvideo'
                if tpse == '35': bv = 'hdroid'
                if tpse == '36': bv = 'vrtech'
                if tpse == '37': bv = 'nbook'
                if tpse == '38': bv = 'apie'
                if tpse == '39': bv = 'shadowwarrior'
                if tpse == '40': bv = 'hunboxing'
                if tpse == '41': bv = 'bytech'
                if tpse == '42': bv = 'techkalauz'
                if tpse == '43': bv = 'techdoboz'
                if tpse == '44': bv = 'anonim'
                if tpse == '45': bv = 'pcx'
                if tpse == '46': bv = 'bitech'
                if tpse == '47': bv = 'thehub'
                if tpse == '48': bv = 'rplair'
                if tpse == '49': bv = 'techfundo'
            return bv
        except Exception:
            return ''
        
    def listThirdItems(self, cItem):
        try:
            tabID = cItem.get('tab_id', '')
            if tabID == 'technika_ajnlt_datum':
                self.Vajnltdtm(cItem)
            elif tabID == 'technika_ajnlt_nezettseg':
                self.Vajnltnztsg(cItem)
            else:
                return
        except Exception:
            return
            
    def Vajnltmsr(self,cItem):
        try:
            vtb = self.malvadnav(cItem, '3', '15', '4')
            if len(vtb) > 0:
                for item in vtb:
                    if len(item['desc']) > 0:
                        tempdesc = item['desc']
                        if tempdesc.startswith('ID'):
                            tlt = tempdesc.find('\n')
                            if -1 < tlt:
                                tempdesc = tempdesc[tlt+1:].strip()
                        if not tempdesc.startswith('Csatorna'):
                            ttmb = tempdesc.split('Tartalom:')
                            if len(ttmb) == 2:
                                tempdesc = 'Csatorna:  ' + self.cslkrs(item['tpe']) + '\n' + ttmb[0]
                                tempdesc = tempdesc + 'Tartalom:\n' + re.sub(r'^(.{450}).*$', '\g<1>...', ttmb[1].replace('\n','').strip())
                        item['desc'] = tempdesc
                    item['category'] = 'list_main'
                    if item['url'] != '' and item['title'] != '':
                        self.addVideo(item)
        except Exception:
            return
            
    def Vajnltdtm(self,cItem):
        vtb = []
        try:
            self.susn('2', '15', 'technika_ajnlt_datum')
            vtb = self.malvadnav(cItem, '4', '15', '4')
            if len(vtb) > 0:
                for item in vtb:
                    if len(item['desc']) > 0:
                        tempdesc = item['desc']
                        if tempdesc.startswith('ID'):
                            tlt = tempdesc.find('\n')
                            if -1 < tlt:
                                tempdesc = tempdesc[tlt+1:].strip()
                        if not tempdesc.startswith('Csatorna'):
                            ttmb = tempdesc.split('Tartalom:')
                            if len(ttmb) == 2:
                                tempdesc = 'Csatorna:  ' + self.cslkrs(item['tpe']) + '\n' + ttmb[0]
                                tempdesc = tempdesc + 'Tartalom:\n' + re.sub(r'^(.{450}).*$', '\g<1>...', ttmb[1].replace('\n','').strip())
                        item['desc'] = tempdesc
                    item['category'] = 'list_third'
                    if item['url'] != '' and item['title'] != '':
                        self.addVideo(item)
        except Exception:
            return
            
    def Vajnltnztsg(self,cItem):
        try:
            self.susn('2', '15', 'technika_ajnlt_nezettseg')
            vtb = self.malvadnav(cItem, '5', '15', '4')
            if len(vtb) > 0:
                for item in vtb:
                    if len(item['desc']) > 0:
                        tempdesc = item['desc']
                        if tempdesc.startswith('ID'):
                            tlt = tempdesc.find('\n')
                            if -1 < tlt:
                                tempdesc = tempdesc[tlt+1:].strip()
                        if not tempdesc.startswith('Csatorna'):
                            ttmb = tempdesc.split('Tartalom:')
                            if len(ttmb) == 2:
                                tempdesc = 'Csatorna:  ' + self.cslkrs(item['tpe']) + '\n' + ttmb[0]
                                tempdesc = tempdesc + 'Tartalom:\n' + re.sub(r'^(.{450}).*$', '\g<1>...', ttmb[1].replace('\n','').strip())
                        item['desc'] = tempdesc
                    item['category'] = 'list_third'
                    if item['url'] != '' and item['title'] != '':
                        self.addVideo(item)
        except Exception:
            return

    def listSearchResult(self, cItem, searchPattern, searchType):
        try:
            cItem = dict(cItem)
            if searchPattern != '':
                if len(searchPattern) > 1:
                    self.suskrbt('2', '15', searchPattern)
                    vtb = self.malvadnavk(cItem, '8', '15', '4', '150', searchPattern)
                    if len(vtb) > 0:
                        for item in vtb:
                            if len(item['desc']) > 0:
                                tempdesc = item['desc']
                                if tempdesc.startswith('ID'):
                                    tlt = tempdesc.find('\n')
                                    if -1 < tlt:
                                        tempdesc = tempdesc[tlt+1:].strip()
                                if not tempdesc.startswith('Csatorna'):
                                    ttmb = tempdesc.split('Tartalom:')
                                    if len(ttmb) == 2:
                                        tempdesc = 'Csatorna:  ' + self.cslkrs(item['tpe']) + '\n' + ttmb[0]
                                        tempdesc = tempdesc + 'Tartalom:\n' + re.sub(r'^(.{450}).*$', '\g<1>...', ttmb[1].replace('\n','').strip())
                                item['desc'] = tempdesc
                            self.addVideo(item)
                else:
                    msg = '\nLegalább 2 karakteresnek kell lennie a Keresési szövegnek!\n'
                    self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10 )
        except Exception:
            return

    def getFavouriteData(self, cItem):
        params = {'type':cItem['type'], 'category':cItem.get('category', ''), 'title':cItem['title'], 'url':cItem['url'], 'desc':cItem['desc'], 'icon':cItem['icon']}
        return json_dumps(params) 
  
    def suskrbt(self, i_md='', i_hgk='', i_mpsz=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzwbywERxYklKkl5BRgEAD/4T/Q=='))
        try:
            if i_mpsz != '' and len(i_mpsz) > 1:
                if len(i_mpsz) > 80:
                    i_mpsz = i_mpsz[:78]
                i_mpsz = base64.b64encode(i_mpsz).replace('\n', '').strip()
                if i_hgk != '':
                    i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                    pstd = {'md':i_md, 'hgk':i_hgk, 'mpsz':i_mpsz}
                    if i_md != '' and i_hgk != '' and i_mpsz != '':
                        sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
            return
        except Exception:
            return
            
    def susmrgts(self, i_md='', i_hgk='', i_mptip='', i_mptipe='', i_mpu='', i_mpt='', i_mpi='', i_mpdl='', i_mpnzs='', i_mpyd=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUl6BRkFABGoFBk='))
        try:
            if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
            if i_mptip != '': i_mptip = base64.b64encode(i_mptip).replace('\n', '').strip()
            if i_mptipe != '': i_mptipe = base64.b64encode(i_mptipe).replace('\n', '').strip()
            if i_mpu != '': i_mpu = base64.b64encode(i_mpu).replace('\n', '').strip()
            if i_mpt != '': i_mpt = base64.b64encode(i_mpt).replace('\n', '').strip()
            if i_mpi == '':
                i_mpi = base64.b64encode('-')
            else:
                i_mpi = base64.b64encode(i_mpi).replace('\n', '').strip()
            if i_mpdl == '':
                i_mpdl = base64.b64encode('-')
            else:
                i_mpdl = base64.b64encode(i_mpdl).replace('\n', '').strip()
            if i_mpnzs != '': i_mpnzs = base64.b64encode(i_mpnzs).replace('\n', '').strip()
            if i_mpyd != '': i_mpyd = base64.b64encode(i_mpyd).replace('\n', '').strip()
            pstd = {'md':i_md, 'hgk':i_hgk, 'mptip':i_mptip, 'mptipe':i_mptipe, 'mpu':i_mpu, 'mpt':i_mpt, 'mpi':i_mpi, 'mpdl':i_mpdl, 'mpnzs':i_mpnzs, 'mpyd':i_mpyd}
            if i_md != '' and i_hgk != '' and i_mptip != '' and i_mptipe != '' and i_mpu != '':
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
            return
        except Exception:
            return
    
    def getdvdsz(self, pu='', psz=''):
        bv = ''
        if pu != '' and psz != '':
            n_atnav = self.malvadst('1', '15', pu)
            if n_atnav != '' and self.aid:
                if pu == 'technika_legfrissebb':
                    self.aid_ki = 'ID: ' + n_atnav + '  |  Technika.HU - v' + HOST_VERSION + '\n'
                else:
                    self.aid_ki = 'ID: ' + n_atnav + '\n'
            else:
                if pu == 'technika_legfrissebb':
                    self.aid_ki = 'Technika.HU - v' + HOST_VERSION + '\n'
                else:
                    self.aid_ki = ''
            bv = self.aid_ki + psz
        return bv
        
    def malvadst(self, i_md='', i_hgk='', i_mpu=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL04sSdQvS8wD0ilJegUZBQD8FROZ'))
        pstd = {'md':i_md, 'hgk':i_hgk, 'mpu':i_mpu}
        t_s = ''
        temp_vn = ''
        temp_vni = ''
        try:
            if i_md != '' and i_hgk != '' and i_mpu != '':
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts: return t_s
                if len(data) == 0: return t_s
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a_div', '</div>')[1]
                if len(data) == 0: return t_s
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '/>')
                if len(data) == 0: return t_s
                for item in data:
                    t_i = self.cm.ph.getSearchGroups(item, 'id=[\'"]([^"^\']+?)[\'"]')[0]
                    if t_i == 'vn':
                        temp_vn = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0]
                    elif t_i == 'vni':
                        temp_vni = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0]
                if temp_vn != '':
                    t_s = temp_vn
            return t_s
        except Exception:
            return t_s
            
    def malvadnav(self, cItem, i_md='', i_hgk='', i_mptip='', i_mpdb=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUl6BRkFABGoFBk='))
        t_s = []
        temp_yd = ''
        try:
            if i_md != '' and i_hgk != '' and i_mptip != '':
                if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                if i_mptip != '': i_mptip = base64.b64encode(i_mptip).replace('\n', '').strip()
                if i_mpdb != '': i_mpdb = base64.b64encode(i_mpdb).replace('\n', '').strip()
                pstd = {'md':i_md, 'hgk':i_hgk, 'mptip':i_mptip, 'mpdb':i_mpdb}
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts: return t_s
                if len(data) == 0: return t_s
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a1_div"', '<div id="div_a2_div"')[1]
                if len(data) == 0: return t_s
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="d_sor_d"', '</div>')
                if len(data) == 0: return t_s
                for temp_item in data:
                    temp_data = self.cm.ph.getAllItemsBeetwenMarkers(temp_item, '<span', '</span>')
                    if len(temp_data) == 0: return t_s
                    for item in temp_data:
                        t_vp = self.cm.ph.getSearchGroups(item, 'class=[\'"]([^"^\']+?)[\'"]')[0]
                        if t_vp == 'c_sor_u':
                            temp_u = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_u">', '</span>', False)[1]
                            if temp_u != '': temp_u = base64.b64decode(temp_u)
                        if t_vp == 'c_sor_t':
                            temp_t = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_t">', '</span>', False)[1]
                            if temp_t != '': temp_t = base64.b64decode(temp_t)
                        if t_vp == 'c_sor_i':
                            temp_i = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_i">', '</span>', False)[1]
                            if temp_i != '': temp_i = base64.b64decode(temp_i)
                        if t_vp == 'c_sor_l':
                            temp_l = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_l">', '</span>', False)[1]
                            if temp_l != '': temp_l = base64.b64decode(temp_l)
                        if t_vp == 'c_sor_n':
                            temp_n = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_n">', '</span>', False)[1]
                            if temp_n != '': temp_n = base64.b64decode(temp_n)
                        if t_vp == 'c_sor_tip':
                            temp_tp = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_tip">', '</span>', False)[1]
                            if temp_tp != '': temp_tp = base64.b64decode(temp_tp)
                        if t_vp == 'c_sor_tipe':
                            temp_tpe = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_tipe">', '</span>', False)[1]
                            if temp_tpe != '': temp_tpe = base64.b64decode(temp_tpe)
                        if t_vp == 'c_sor_yd':
                            temp_yd = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_yd">', '</span>', False)[1]
                            if temp_yd != '':
                                temp_yd = base64.b64decode(temp_yd)
                                pev = temp_yd[:4]
                                pho = temp_yd[5:7]
                                pnap = temp_yd[8:10]
                                if pev.isdigit() and pho.isdigit() and pnap.isdigit():
                                    temp_yd = pev + '.' + pho + '.' + pnap + '.'
                                else:
                                    temp_yd = ''
                    if temp_u == '' and temp_t =='': continue
                    if temp_n == '': temp_n = '1'
                    if temp_tpe == '': temp_tpe = '0'
                    temp_tabid = self.cslkrstid(temp_tpe)
                    params = MergeDicts(cItem, {'good_for_fav': True, 'url':temp_u, 'title':temp_t, 'icon':temp_i, 'desc':temp_l, 'nztsg':temp_n, 'tps':temp_tp, 'tpe':temp_tpe, 'tab_id':temp_tabid, 'time':temp_yd})
                    t_s.append(params)       
            return t_s
        except Exception:
            return []
            
    def malvadnavk(self, cItem, i_md='', i_hgk='', i_mptip='', i_mpdb='', i_mpks=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUl6BRkFABGoFBk='))
        t_s = []
        try:
            if i_md != '' and i_hgk != '' and i_mptip != '' and i_mpks != '':
                if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                if i_mptip != '': i_mptip = base64.b64encode(i_mptip).replace('\n', '').strip()
                if i_mpdb != '': i_mpdb = base64.b64encode(i_mpdb).replace('\n', '').strip()
                if i_mpks != '': i_mpks = base64.b64encode(i_mpks).replace('\n', '').strip()
                pstd = {'md':i_md, 'hgk':i_hgk, 'mptip':i_mptip, 'mpdb':i_mpdb, 'mpks':i_mpks}
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts: return t_s
                if len(data) == 0: return t_s
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a1_div"', '<div id="div_a2_div"')[1]
                if len(data) == 0: return t_s
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="d_sor_d"', '</div>')
                if len(data) == 0: return t_s
                for temp_item in data:
                    temp_data = self.cm.ph.getAllItemsBeetwenMarkers(temp_item, '<span', '</span>')
                    if len(temp_data) == 0: return t_s
                    for item in temp_data:
                        t_vp = self.cm.ph.getSearchGroups(item, 'class=[\'"]([^"^\']+?)[\'"]')[0]
                        if t_vp == 'c_sor_u':
                            temp_u = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_u">', '</span>', False)[1]
                            if temp_u != '': temp_u = base64.b64decode(temp_u)
                        if t_vp == 'c_sor_t':
                            temp_t = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_t">', '</span>', False)[1]
                            if temp_t != '': temp_t = base64.b64decode(temp_t)
                        if t_vp == 'c_sor_i':
                            temp_i = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_i">', '</span>', False)[1]
                            if temp_i != '': temp_i = base64.b64decode(temp_i)
                        if t_vp == 'c_sor_l':
                            temp_l = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_l">', '</span>', False)[1]
                            if temp_l != '': temp_l = base64.b64decode(temp_l)
                        if t_vp == 'c_sor_n':
                            temp_n = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_n">', '</span>', False)[1]
                            if temp_n != '': temp_n = base64.b64decode(temp_n)
                        if t_vp == 'c_sor_tip':
                            temp_tp = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_tip">', '</span>', False)[1]
                            if temp_tp != '': temp_tp = base64.b64decode(temp_tp)
                        if t_vp == 'c_sor_tipe':
                            temp_tpe = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_tipe">', '</span>', False)[1]
                            if temp_tpe != '': temp_tpe = base64.b64decode(temp_tpe)
                        if t_vp == 'c_sor_yd':
                            temp_yd = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_yd">', '</span>', False)[1]
                            if temp_yd != '':
                                temp_yd = base64.b64decode(temp_yd)
                                pev = temp_yd[:4]
                                pho = temp_yd[5:7]
                                pnap = temp_yd[8:10]
                                if pev.isdigit() and pho.isdigit() and pnap.isdigit():
                                    temp_yd = pev + '.' + pho + '.' + pnap + '.'
                                else:
                                    temp_yd = ''
                    if temp_u == '' and temp_t =='': continue
                    if temp_n == '': temp_n = '1'
                    if temp_tpe == '': temp_tpe = '0'
                    temp_tabid = self.cslkrstid(temp_tpe)
                    params = MergeDicts(cItem, {'good_for_fav': True, 'url':temp_u, 'title':temp_t, 'icon':temp_i, 'desc':temp_l, 'nztsg':temp_n, 'tps':temp_tp, 'tpe':temp_tpe, 'tab_id':temp_tabid, 'time':temp_yd})
                    t_s.append(params)       
            return t_s
        except Exception:
            return []
            
    def susn(self, i_md='', i_hgk='', i_mpu=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL04sSdQvS8wD0ilJegUZBQD8FROZ'))
        pstd = {'md':i_md, 'hgk':i_hgk, 'mpu':i_mpu, 'hv':self.vivn, 'orv':self.porv, 'bts':self.pbtp}
        try:
            if i_md != '' and i_hgk != '' and i_mpu != '':
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
            return
        except Exception:
            return
            
    def fdnvls(self, i_md='', i_hgk='', i_mptipe='', i_mpno=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL0stTtQvS8wD0SlJegUZBQAQzBQG'))
        try:
            if i_md != '' and i_hgk != '' and i_mptipe != '':
                if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                if i_mptipe != '': i_mptipe = base64.b64encode(i_mptipe).replace('\n', '').strip()
                if i_mpno != '': i_mpno = base64.b64encode(i_mpno).replace('\n', '').strip()
                pstd = {'md':i_md, 'hgk':i_hgk, 'mptipe':i_mptipe, 'mpno':i_mpno}
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
            return
        except Exception:
            return
            
    def fdmgnz(self, i_md='', i_hgk='', i_mptipe=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL0stTtQvS8wD0SlJegUZBQAQzBQG'))
        bv = False
        try:
            if i_md != '' and i_hgk != '' and i_mptipe != '':
                if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                if i_mptipe != '': i_mptipe = base64.b64encode(i_mptipe).replace('\n', '').strip()
                pstd = {'md':i_md, 'hgk':i_hgk, 'mptipe':i_mptipe}
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts: return bv
                if len(data) == 0: return bv
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_af_div"', '</div>')[1]
                if len(data) == 0: return bv
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="d_soraf_d"', '</div>')
                if len(data) == 0: return bv
                for temp_item in data:
                    temp_data = self.cm.ph.getAllItemsBeetwenMarkers(temp_item, '<span', '</span>')
                    if len(temp_data) == 0: return bv
                    for item in temp_data:
                        t_vp = self.cm.ph.getSearchGroups(item, 'class=[\'"]([^"^\']+?)[\'"]')[0]
                        if t_vp == 'c_soraf_no':
                            temp_ano = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_soraf_no">', '</span>', False)[1]
                            if temp_ano != '': self.adfrid = base64.b64decode(temp_ano)
                        if t_vp == 'c_soraf_d':
                            temp_af = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_soraf_d">', '</span>', False)[1]
                            if temp_af != '': temp_af = base64.b64decode(temp_af)
                            akt_ido = datetime.now()
                            datum = datetime.strptime(temp_af, "%Y-%m-%d %H:%M:%S")
                            if akt_ido > datum:
                                bv = True
                            break
            return bv
        except Exception:
            return False
            
    def muves(self, i_md='', i_hgk=''):
        uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL0stTtQvS8wD0SlJegUZBQAQzBQG'))
        temp_ah = ''
        temp_av = ''
        temp_avf = ''
        bv = []
        try:
            if i_md != '' and i_hgk != '':
                if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                pstd = {'md':i_md, 'hgk':i_hgk}
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts: return bv
                if len(data) == 0: return bv
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_av_div"', '</div>')[1]
                if len(data) == 0: return bv
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="d_sorv_d"', '</div>')
                if len(data) == 0: return bv
                for temp_item in data:
                    temp_data = self.cm.ph.getAllItemsBeetwenMarkers(temp_item, '<span', '</span>')
                    if len(temp_data) == 0: return bv
                    for item in temp_data:
                        t_vp = self.cm.ph.getSearchGroups(item, 'class=[\'"]([^"^\']+?)[\'"]')[0]
                        if t_vp == 'c_sorv_h':
                            temp_ah = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sorv_h">', '</span>', False)[1]
                            if temp_ah != '': temp_ah = base64.b64decode(temp_ah)
                        if t_vp == 'c_sorv_v':
                            temp_av = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sorv_v">', '</span>', False)[1]
                            if temp_av != '': temp_av = base64.b64decode(temp_av)
                        if t_vp == 'c_sorv_vf':
                            temp_avf = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sorv_vf">', '</span>', False)[1]
                            if temp_avf != '': temp_avf = base64.b64decode(temp_avf) 
                    if temp_ah != '' and temp_av != '' and temp_avf != '':
                        bv.append({'hh':temp_ah, 'vv':temp_av, 'ff':temp_avf})
            return bv
        except Exception:
            return []
            
    def muvesegyzs(self, tmb=[]):
        bv = 'nfv'
        try:
            if len(tmb) == 1:
                for item in tmb:
                    if float(item['vv']) > float(HOST_VERSION):
                        bv = 'vfv'
                    break
            return bv
        except Exception:
            return 'nfv'
    
    def ebbtit(self):
        try:
            if '' == self.btps.strip() or '' == self.brdr.strip():
                msg = 'A Set-top-Box típusát és a használt rendszer (image) nevét egyszer meg kell adni!\n\nA kompatibilitás és a megfelelő használat miatt kellenek ezek az adatok a programnak.\nKérlek, a helyes működéshez a valóságnak megfelelően írd be azokat.\n\nA "HU Telepítő" keretrendszerben tudod ezt megtenni.\n\nKilépek és megyek azt beállítani?'
                ret = self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_YESNO, default=True)
                return False
            else:
                return True
        except Exception:
            return False
    
    def gits(self):
        bv = '-'
        tt = []
        try:
            if fileExists(zlib.decompress(base64.b64decode('eJzTTy1J1s8sLi5NBQATXQPE'))):
                fr = open(zlib.decompress(base64.b64decode('eJzTTy1J1s8sLi5NBQATXQPE')),'r')
                for ln in fr:
                    ln = ln.rstrip('\n')
                    if ln != '':
                        tt.append(ln)
                fr.close()
                if len(tt) == 1:
                    bv = tt[0].strip()[:-6].capitalize()
                if len(tt) == 2:
                    bv = tt[1].strip()[:-6].capitalize()
            return bv
        except:
            return '-'
            
    def malvadkrttmk(self, i_md='', i_hgk=''):
        bv = []
        ukszrz = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzwbywERxYklKkl5BRgEAD/4T/Q=='))
        try:
            if i_md != '' and i_hgk != '':
                i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
                pstd = {'md':i_md, 'hgk':i_hgk}
                sts, data = self.cm.getPage(ukszrz, self.defaultParams, pstd)
                if not sts: return []
                if len(data) == 0: return []
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div>', '</div>', False)
                if len(data) == 0: return []
                for item in data:
                    if item != '':
                        bv.append(base64.b64decode(item))
            return bv
        except Exception:
            return []
        
    def Vdakstmk(self, baseItem={'name': 'history', 'category': 'search'}, desc_key='plot', desc_base=(_("Type: ")), tabID='' ):
        if tabID != '':
            self.susn('2', '15', tabID)
            
        def _vdakstmk(data,lnp=50):
            ln = 0
            for histItem in data:
                plot = ''
                try:
                    ln += 1
                    if type(histItem) == type({}):
                        pattern = histItem.get('pattern', '')
                        search_type = histItem.get('type', '')
                        if '' != search_type: plot = desc_base + _(search_type)
                    else:
                        pattern = histItem
                        search_type = None
                    params = dict(baseItem)
                    params.update({'title': pattern, 'search_type': search_type,  desc_key: plot, 'tps':'4'})
                    self.addDir(params)
                    if ln >= lnp:
                        break
                except Exception:
                    return
            
        try:
            list = self.malvadkrttmk('1','15')
            if len(list) > 0:
                _vdakstmk(list,2)
            if len(list) > 0:
                list = list[2:]
                random.shuffle(list)
                _vdakstmk(list,48)
        except Exception:
            return
            
    def getArticleContent(self, cItem):
        try:
            artID = cItem.get('art_id', '')
            if artID == 'foinformacio':
                return self.fgtac(cItem)
            else:
                return []
        except Exception:
            return
            
    def fgtac(self, cItem):
        try:
            self.susn('2', '15', cItem['url'])
            title_citem = cItem['title']
            icon_citem = cItem['icon']
            desc = 'Észrevételeidet, javaslataidat a következő címre küldheted el:\n' + zlib.decompress(base64.b64decode('eJwrT03KKC3ISaxMLXJIz03MzNFLzs8FAF5sCGA=')) + '\n\nFelhívjuk figyelmedet, hogy egyes csatornák adásai átmenetileg szünetelhetnek. Mielőtt hibát jelzel, ellenőrizd az adott csatorna internetes oldalán az adás működését.\n\nAmennyiben egyes adások nem játszhatók le (NINCS ELÉRHETŐ LINK), akkor az adott műsor tartalomszolgáltatója megváltoztatta annak elérhetőségét. Ez nem a "Technika.HU" lejátszó hibája!!!\n\nKellemes szórakozást kívánunk!\n(Alec)'            
            retList = {'title':title_citem, 'text': desc, 'images':[{'title':'', 'url':icon_citem}]}
            return [retList]
        except Exception:
            return
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        self.currList = []
        if name == None:
            self.listMainMenu( {'name':'category'} )
        elif category == 'list_main':
            self.listMainItems(self.currItem)
        elif category == 'list_second':
            self.listSecondItems(self.currItem)
        elif category == 'list_third':
            self.listThirdItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            if self.currItem['tab_id'] == 'technika_kereses':
                self.susn('2', '15', 'technika_kereses')
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            if self.currItem['tab_id'] == 'technika_kereses_elozmeny':
                self.susn('2', '15', 'technika_kereses_elozmeny')
            self.listsHistory({'name':'history', 'category': 'search', 'tab_id':'', 'tps':'4'}, 'desc', _("Type: "))
        else:
            return
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Technika(), True, [])
    
    def withArticleContent(self, cItem):
        if cItem['type'] != 'article':
            return False
        return True
