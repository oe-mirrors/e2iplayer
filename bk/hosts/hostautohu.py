# -*- coding: utf-8 -*-
###################################################
# 2020-08-09 by Alec - auto.HU
#            by celeburdi - rtlmost.hu
#            by McFly - logok
###################################################
HOST_VERSION = "2.0"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetIPTVPlayerVerstion, GetTmpDir, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta, decorateUrl
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
import traceback
from copy import deepcopy
try:
	import json
except Exception:
	import simplejson as json
from Components.config import config, ConfigText, ConfigYesNo, getConfigListEntry
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
config.plugins.iptvplayer.autohu_rtlmost_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.autohu_rtlmost_password = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.autohu_id = ConfigYesNo(default = False)
config.plugins.iptvplayer.boxtipus = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.boxrendszer = ConfigText(default = "", fixed_size = False)

def GetConfigList():
	optionList = []
	optionList.append(getConfigListEntry("autohu_rtlmost_login:", config.plugins.iptvplayer.autohu_rtlmost_login))
	optionList.append(getConfigListEntry("autohu_rtlmost_password:", config.plugins.iptvplayer.autohu_rtlmost_password))
	optionList.append(getConfigListEntry("autohu_id:", config.plugins.iptvplayer.autohu_id))
	return optionList
###################################################

def gettytul():
	return 'auto.HU'
	
def _getImageExtKey(images, role):
	try:
		for i in images:
			if i.get('role') == role: return i['external_key']
	except: pass
	return None

class AutosHU(CBaseHostClass):
 
	def __init__(self):
		CBaseHostClass.__init__(self, {'history':'auto.hu', 'cookie':'autohu.cookie'})
		self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
		self.HEADER = self.cm.getDefaultHeader()
		self.AJAX_HEADER = dict(self.HEADER)
		self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
		self.DEFAULT_ICON_URL = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8sLcnPKI3PyU/P1yvISwcAfmERMA=='))
		self.MAIN_URL_AUTOGRAM = zlib.decompress(base64.b64decode('eJwzNzczAQACJQDZ'))
		self.DEFAULT_ICON_URL_AUTOGRAM = zlib.decompress(base64.b64decode(
			'eJwtyEsOwiAQANDbsCyUqXxMiEcxAx0KhioC2vT2bnzLl8ao/cp53nGjPqla8Jxi41/5Lz4LsEZY'
			'3vC4HXkdyUktWaK8peHmC7CYh+sBC91De1X2/mDJ43RKsPhqOw73qLSx/BzUCgZyM0vYkwOpyWiI'
			'gqRfpQdj5aIpBA1eg16V8YDWLuoHajI0vg=='))
		self.API_URL = zlib.decompress(base64.b64decode(
			'eJwdxkEKwCAMBdEb+aELF72MWI21oChJVHr7SjfzJqt2OYEeTH1iLLQ8k7G9+Nckxj+YB7aaGldB'
			'tTe30d2iC0I8n0AC1pKH23W1ieIDaJggkw=='))
		self.API_HEADER = dict(self.HEADER)
		self.API_HEADER.update( {'x-customer-name': 'rtlhu'} )
		self.ICON_PATH = zlib.decompress(base64.b64decode(
			'eJzTLzPSz8xNTE8t1q+u1S9KLLcvz0wpybCtrlXLSM1MzygBsdIywVRhaWJOZkklWCS/KDcRLJiZ'
			'V5JalJOYnArkAABkJB19'))
		self.ICON_HASH = zlib.decompress(base64.b64decode(
			'eJwzNUkyNTUxsEg0NTawNAVxjNPSzC1TLS0AVI4Gfg=='))
		self.ICON_URL = zlib.decompress(base64.b64decode(
			'eJzLKCkpKLbS18/MTUxPLdYzK8hJrNRLK6quVctILM6wra4FAM7fDFk='))
		self.ACCOUNT_URL = zlib.decompress(base64.b64decode(
			'eJwlxt0KgjAUAOC38U6NDKFAokhEo1gYZd3IGHPz7xzZjtgPvXtE39WniQa78v0OVQ2eoa5HS54e'
			'fS4EjkDWU5I2/6dQ4Rr5SLokbCVE749jpTCSfqvQ9JyixiI4fKj38hkFJWOje5g3LbLzjRY9uPqy'
			'TUJI2LaZ4iLMMjXlx3u9LFylXicz6+ARJBSoON1ZkefXL7XkOfU='))
		self.LOGIN_URL = zlib.decompress(base64.b64decode(
			'eJwdjN0KgjAYQN9md2pkCAUSiCIaxcIo6ybmsjndj2yf2Q+9e+TN4cCB0wD0duV5QjOuXANCagtu'
			'M3iEUj0osO5U1hOzOPx8UU+sHbW5/R2IYTUk6hFKXXFRo7s2kkDYWq0Q6fmmfoX+FePB2c7bTuPD'
			'GRZSOc0xSgOV4qgdkzLIczYWuwtflg5j772ZCfX0U/BZksWWFsUJUSJERWg3fX939EE8'))
		self.SUBCATS_URL = self.API_URL+zlib.decompress(base64.b64decode(
			'eJwrKMpPL0rMLdavrrUvzyzJsM3JzMsu1ikuTUpOLCnWKcpMzygpBgAacg7K'))
		self.EPISODES_URL = self.API_URL+zlib.decompress(base64.b64decode(
			'eJwlyjEKwzAMBdDbeDJk6ih6FlWVU1EbC3/FIYTcvZBub3g++jq4YTmvZdpbO54CpkfaLT4k1Ry5'
			'DNVmW3OWL1IcrjQtT8le+aiGSNhewkHnlao1u9FLgd5CH0H/8QMyYSqT'))
		self.VIDEO_URL = self.API_URL+zlib.decompress(base64.b64decode(
			'eJwtyDEKgDAMAMDfOBWcHItPKSGNNbShIdGKiH938cYbnKn7/LwrOsRluvjYIzZWD5sRCZ+igNWD'
			'Wi8GkligkAcnG4yUMrs2uP/+AKaUHqw='))
		self.loginParams = {'header':self.HEADER}
		self.apiParams = {'header':self.API_HEADER}        
		self.MAIN_URL_GARAZS = zlib.decompress(base64.b64decode('eJzLKCkpsNLXT08sSqwq1isp0y/LTEnNz9ZPTEksBlIAt9MLew=='))
		self.MAIN_URL_GARAZS_ADASOK = zlib.decompress(base64.b64decode('eJzLKCkpsNLXT08sSqwq1isp0y/LTEnNz9ZPTEkszs8GAKxYC0w='))
		self.DEFAULT_ICON_URL_GARAZS = zlib.decompress(base64.b64decode('eJzLKCkpsNLXT08sSqwq1isp08/MTUxPLdbPyU/P1yvISwcAwzsL8Q=='))
		self.MAIN_URL_SUPERCAR = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v1ysuLUgtSk4sKinTyyjVBwB7dQl1'))
		self.MAIN_URL_SUPERCAR_ADASOK = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v1ysuLUgtSk4sKinTyyjVT0xJLM7P1gcAyKoMFw=='))
		self.DEFAULT_ICON_URL_SUPERCAR = zlib.decompress(base64.b64decode(
			'eJzLKCkpsNLXLy4tSC1KTizSKzYu18so1S8v0E3OzytJzSvRLy3IyU9MKdY3MjC00DcwhyuNz8lP'
			'z9cryEsHADc1GCA='))
		self.MAIN_URL_TOTALCAR = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y/JL0nMSU4s0sso1S8pAwBf1QhK'))
		self.DEFAULT_ICON_URL_TOTALCAR = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S/JL0nMSU4sis/JT8/XyypIBwChxxHw'))
		self.DEFAULT_ICON_URL_VEZESS = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S9LrUotLo7PyU/P18sqSAcAfukRNg=='))
		self.DEFAULT_ICON_URL_AUTONAV = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8sLcnPSyzLTE8syS+Kz8lPz9fLKkgHAAP0FBo='))
		self.DEFAULT_ICON_URL_HANDRAS = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzEspSiyOz8lPz9fLKkgHAI57EXc='))
		self.DEFAULT_ICON_URL_AUTOSAMAN = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8sLckvTsxNzIvPyU/P18sqSAcAtIMSXw=='))
		self.DEFAULT_ICON_URL_AUTOROOM = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8sLckvys/Pjc/JT8/XyypIBwCi7hIM'))
		self.DEFAULT_ICON_URL_VILLANY = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S/LzMlJzKtMLC3JL87Pjs/JT8/XyypIBwAaBBSb'))
		self.DEFAULT_ICON_URL_ALAPJARAT = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U/MSSzISixKLInPyU/P18sqSAcAssMSRg=='))
		self.DEFAULT_ICON_URL_BPIAUTOSOK = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8qyEwsLckvzs+Oz8lPz9fLKkgHAMfUEtc='))
		self.DEFAULT_ICON_URL_112PRESS = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1Tc0NCooSi0ujs/JT8/XyypIBwCXnhFX'))
		self.DEFAULT_ICON_URL_SPEEDZONE = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1S8uSE1NqcrPS43PyU/P18sqSAcAtKwSYw=='))
		self.DEFAULT_ICON_URL_AUTOBABBO = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8sLclPSkxKyo/PyU/P18sqSAcAsyYSRQ=='))
		self.MAIN_URL_FORMA1 = zlib.decompress(base64.b64decode('eJzLKCkpKLbS108zTCstSczNz9ZLLQUATWQHYg=='))
		self.DEFAULT_ICON_URL_FORMA1 = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8zjM/JT8/XK8hLBwA4Gg8x'))
		self.MAIN_URL_FORMA1_VERSENYNAPTAR = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9fLNSkuyC8q0cso1U8z1C1LLSpOzavMSywoSSzSBwAwVw73'))
		self.MAIN_URL_FORMA1_PONTVERSENY = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9fLNSkuyC8q0cso1U8z1C3IzyspSy0qTs2r1AcAErkOMg=='))
		self.MAIN_URL_HOLVEZES = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1U9PzEktykzUyyjJzQEAGlgOkQ=='))
		self.DEFAULT_ICON_URL_HOLVEZES = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c/IzylLrUotjs/JT8/XK8hLBwCiphIK'))
		self.MAIN_URL_AUTOSHOW = zlib.decompress(base64.b64decode('eJxLLC3Jj08EEsUZ+eUAJpYFkw=='))
		self.DEFAULT_ICON_URL_AUTOSHOW = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U8sLckvzsgvj8/JT8/XyypIBwCjCxIQ'))
		self.MAIN_URL_FORDRIVE = zlib.decompress(base64.b64decode('eJxLLC3Jj0/LL0opyixLBQAmTAV6'))
		self.DEFAULT_ICON_URL_FORDRIVE = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1U/LL0opyixLjc/JT8/XyypIBwCh4BH3'))
		self.kfvk = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUTzPUBwAMUA2+'))
		self.kfvcsk =zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUTzNMLk4sSCzRBwBowRA6'))
		self.vivn = GetIPTVPlayerVerstion()
		self.porv = self.gits()
		self.pbtp = '-'
		self.btps = config.plugins.iptvplayer.boxtipus.value
		self.brdr = config.plugins.iptvplayer.boxrendszer.value
		self.ytp = YouTubeParser()
		self.loggedIn = False
		self.login = ''
		self.password = ''
		self.aid = config.plugins.iptvplayer.autohu_id.value
		self.aid_ki = ''
		self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE} 
		self.plurl_vezess_matksz = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVB4X6GBsEm5gYWqamlhkkV3qEFPs6GANqaGcw='))
		self.plurl_vezess_ertekb = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVBFpH5ebo5xWYukWXmjkl+eVWVzu7lAOZaGtM='))
		self.plurl_vezess_aszaloncs = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVBHmWZxc6BpgHlvuHGaf4+xq7GlUa5AOWCGks='))
		self.plurl_vezess_ojkogm = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQUhWbnenoaRjuZVyabZrpFBpZleTtnmAOSnGm4='))
		self.plurl_vezess_bgtgml = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVBJgEhfmFufn66RqkGOb6JVeaROU4GANySGdo='))
		self.plurl_vezess_htank = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQWBlinlqRV+Bi7mke6e6amergZ+EW6WAONZGgc='))
		self.plurl_vezess_haaktink = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQXBHqlVBqaepmbGmW7mxY4myVGlrm5VANzHGf8='))
		self.plurl_vezess_trahvzs = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQWB6T6+QeWhicaOFkk5+fGWfpYeWfEZAOUiGoU='))
		self.plurl_total_trtk = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S/ISazMySwusQcRtgE+Hs6lga4mgf5RPhGmLjlBxS4eOQbxfslZJRmeZWmeho4ArcAZSw=='))
		self.plurl_total_mlypn = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5h3k7pyfFuxj4hFYYWwZWVYX6RPlnFAMwNGc8='))
		self.plurl_total_treo = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT6hOT4BWUFlZh5GhY4e2eVBjhFZoRnlAM9hGgI='))
		self.plurl_total_tlbk = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5hYYZlZlGlOXkpheYV4VW6eZ5prjnuANMlGic='))
		self.plurl_total_szjsn = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT6hLhUuUYEWwYWJAZlBRq6OLuGRpRneAMxtGZo='))
		self.plurl_total_trmks = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5hBUmhhcEhOZ6+3kWmES6ema65RlUWANIUGcs='))
		self.plurl_total_uzk = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5hrvHxubnejgEe4X55AVGRRVVREYFhANDUGhA='))
		self.plurl_total_tlac = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT4RrtnOmeVlxQElUQYhnvEV2clpFT4+ANaPGng='))
		self.plurl_autoshow = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoW5pbump3mFhGVkRJYHBEUFZxqm6nuUA5W4W7A=='))
		self.plurl_fordrive = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoc7mZkbmxcWp+SZl/mHx3lmWHonh3o4A3BEWVw=='))
		self.plurl_asr = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoUEWhVEpXh5G3vnBibrJ6eXmOY6FpY4A4IAWwA=='))
		self.plurl_asm = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoeZBATmGRaFJwc65YXkRnu7mSaaWxekA37YWiw=='))
		self.plurl_autonav = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoa5JiWWGeSHu4QXpUaUWFVm+fvnBJuUA50MXMw=='))
		self.plurl_villany = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoeGlIVEp7m6FXt4eOZnZuhleBpXJYekA5WcW/Q=='))
		self.plurl_alapjarat = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoaWpOan+UUaBbo6JYcEeERmpUTlumekA5dUXDQ=='))
		self.plurl_bpiautosok = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahof5RoRY+oUbm5R4uVcWREWZJSVEp4ekA3i4Wsw=='))
		self.plurl_112press = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPm7m5YmhlfFVluaF5iUeFZ6Gge4e3o5Rll7uBo7x5WXJANORGcA='))
		self.plurl_speedzone = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPibp/pEpQSFOlkFGHmVpWbqRhuGuQWGhUXlVKR7JGeWVAM3SGiE='))
		self.plurl_autobabbo = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPqmBmQF+lZmZFeYeyQbhqQY+6eFBaZnlaeGOVZmWpkkBAN+hGm8='))
		self.plurl_hand = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoamOThbxwQVeAWm6FT4BJmGFHtlmIYEA3lMWaA=='))
							
	def listMainMenu(self, cItem):
		if not self.ebbtit(): return
		if self.btps != '' and self.brdr != '': self.pbtp = self.btps.strip() + ' - ' + self.brdr.strip()
		#self.lfrbfts()
		url_legfris = 'legfrissebb'
		desc_legfris = self.getdvdsz(url_legfris, 'auto.HU - v' + HOST_VERSION + '\n\nLegfrissebb autós adások, műsorok és információk gyűjtőhelye. Amennyiben egyes adások nem játszhatók le - NINCS ELÉRHETŐ LINK, akkor az adott műsor tartalomszolgáltatója megváltoztatta annak elérhetőségét. Ez nem az "auto.HU" lejátszó hibája!!!  Kérlek, hogy ezt vedd figyelembe...')
		url_mindentudo = 'auto_hu_mindentudo'
		desc_mindentudo = self.getdvdsz(url_mindentudo, 'Minden, ami az autókról, illetve az autózásről tudni kell.\nAutós műsorcsatornák (VEZESS TV, TOTALCAR, AUTÓNAVIGÁTOR, HANDRAS TV, AUTÓSÁMÁN, AUTOROOM, VILLANYAUTÓSOK, ALAPJÁRAT, SPEEDZONE, AUTÓ BABBO) lejátszási listái, videói. Érdekes elméleti és gyakorlati ismeretek bemutatói, videói...')
		url_autoskoz = 'auto_hu_musorcsat'
		desc_autoskoz = self.getdvdsz(url_autoskoz, 'Autós műsorcsatornák (AUTOGRAM, GARAZS, SUPERCAR, TOTALCAR, HOLVEZESSEK, AUTOSHOW, 4DRIVE TIME) műsorai...')
		url_inenonan = 'inenonan'
		desc_inenonan = self.getdvdsz(url_inenonan, 'Autós műsorok véletlenszerű megjelenéssel (A betöltődés hosszabb ideig is eltarthat, max. 1-2 percig is. Várd meg míg betöltődnek az adások..)')
		url_atipus = 'atipus'
		desc_atipus = self.getdvdsz(url_atipus, 'Autós műsorok az adott autó típusának megfelelően...')
		url_szabalytalan = 'auto_szabalytalan'
		desc_szabalytalan = self.getdvdsz(url_szabalytalan, 'Autós szabálytalanságok, szabálysértések...')
		url_forma1 = self.MAIN_URL_FORMA1
		desc_forma1 = self.getdvdsz(url_forma1, 'Forma1 közvetítések, versenynaptár, pontverseny...')
		url_keres = 'auto_kereses'
		desc_keres = self.getdvdsz(url_keres, 'Keresés az autós műsorok tartalmának címében...')
		url_info = 'auto_informacio'
		desc_info = self.getdvdsz(url_info, 'Információk megjelenítése...')
		MAIN_CAT_TAB = [{'category':'list_main', 'title': 'Legfrissebb adások', 'url': url_legfris, 'tab_id': 'legfrissebb', 'desc': desc_legfris},
						{'category':'list_main', 'title': 'AUTÓS műsorcsatornák', 'url': url_autoskoz, 'tab_id': 'autoskoz', 'desc': desc_autoskoz},
						{'category':'list_main', 'title': 'AUTÓS videócsatornák', 'url': url_mindentudo, 'tab_id': 'mindentudo', 'desc': desc_mindentudo},
						{'category':'list_main', 'title': 'AUTÓS szabálytalanságok', 'url': url_szabalytalan, 'tab_id': 'szabalytalan', 'desc': desc_szabalytalan},
						{'category':'list_main', 'title': 'Adások innen-onnan', 'url': url_inenonan, 'tab_id': 'veletlenszeru', 'desc': desc_inenonan},
						#{'category':'list_main', 'title': 'Autók típus szerint', 'url': url_atipus, 'tab_id': 'tipusok', 'desc': desc_atipus},
						{'category':'list_main', 'title': 'FORMA1 közvetítések', 'url': url_forma1, 'tab_id': 'forma1', 'icon': self.DEFAULT_ICON_URL_FORMA1, 'desc': desc_forma1}
						#{'category':'search', 'title': 'Keresés', 'url': url_keres, 'search_item': True, 'desc': desc_keres}                        
					   ]
		self.listsTab(MAIN_CAT_TAB, cItem)
		params = dict(cItem)
		params = {'good_for_fav': False, 'title':'Információ', 'url': url_info, 'desc':desc_info, 'icon':self.DEFAULT_ICON_URL, 'art_id':'foinformacio', 'type':'article'}
		self.addArticle(params)
		
	def MusorMainMenu(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		url_autogram = self.MAIN_URL_AUTOGRAM
		desc_autogram = self.getdvdsz(url_autogram, 'Autogram autós műsor adásai...')
		url_garazs = self.MAIN_URL_GARAZS
		desc_garazs = self.getdvdsz(url_garazs, 'GarázsTV autós műsor adásai...')
		url_super = self.MAIN_URL_SUPERCAR
		desc_super = self.getdvdsz(url_super, 'Supercar autós műsor adásai...')
		url_totalcar = self.MAIN_URL_TOTALCAR
		desc_total = self.getdvdsz(url_totalcar, 'TotalcarTV autós műsor adásai...')
		url_holvezes = self.MAIN_URL_HOLVEZES
		desc_holvezes = self.getdvdsz(url_holvezes, 'Holvezessek.hu autós műsor adásai...')
		plurl_autoshow = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoW5pbump3mFhGVkRJYHBEUFZxqm6nuUA5W4W7A=='))
		url_autoshow = self.MAIN_URL_AUTOSHOW
		desc_autoshow = self.getdvdsz(url_autoshow, 'AutoSHOW videói...')
		plurl_fordrive = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoc7mZkbmxcWp+SZl/mHx3lmWHonh3o4A3BEWVw=='))
		url_fordrive = self.MAIN_URL_FORDRIVE
		desc_fordrive = self.getdvdsz(url_fordrive, '4Drive Time videói...')
		MR_CAT_TAB = [{'category':'list_second', 'title': 'Autogram adásai', 'url': url_autogram, 'tab_id': 'autogram', 'icon': self.DEFAULT_ICON_URL_AUTOGRAM, 'desc': desc_autogram},
					  {'category':'list_second', 'title': 'GarázsTV adásai', 'url': url_garazs, 'tab_id': 'garazs', 'icon': self.DEFAULT_ICON_URL_GARAZS, 'desc': desc_garazs},
					  {'category':'list_second', 'title': 'Supercar adásai', 'url': url_super, 'tab_id': 'supercar', 'icon': self.DEFAULT_ICON_URL_SUPERCAR, 'desc': desc_super},
					  {'category':'list_second', 'title': 'TotalcarTV adásai', 'url': url_totalcar, 'tab_id': 'totalcar', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total},
					  {'category':'list_second', 'title': 'Holvezessek adásai', 'url': url_holvezes, 'tab_id': 'holvezes', 'icon': self.DEFAULT_ICON_URL_HOLVEZES, 'desc': desc_holvezes},
					  {'category':'list_second', 'title': 'AutoSHOW adásai', 'url': url_autoshow, 'plurl': plurl_autoshow, 'tab_id': 'autoshow', 'icon': self.DEFAULT_ICON_URL_AUTOSHOW, 'desc': desc_autoshow},
					  {'category':'list_second', 'title': '4Drive Time adásai', 'url': url_fordrive, 'plurl': plurl_fordrive, 'tab_id': 'fordrive', 'icon': self.DEFAULT_ICON_URL_FORDRIVE, 'desc': desc_fordrive}
					 ]
		self.listsTab(MR_CAT_TAB, cItem)
		
	def MindentudoMainMenu(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		url_vezess_m = 'auto_vezess_csatorna_m'
		desc_vezess_m = self.getdvdsz(url_vezess_m, 'Vezess TV csatorna műsorai, videói...')
		url_totalcar_m = 'auto_totalcar_csatorna_m'
		desc_totalcar_m = self.getdvdsz(url_totalcar_m, 'Totalcar csatorna műsorai, videói...')
		plurl_autonav = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoa5JiWWGeSHu4QXpUaUWFVm+fvnBJuUA50MXMw=='))
		url_autonav_m = 'auto_autonav_csatorna_m'
		desc_autonav_m = self.getdvdsz(url_autonav_m, 'Autónavigátor csatorna műsorai, videói...')
		plurl_handras_m = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoamOThbxwQVeAWm6FT4BJmGFHtlmIYEA3lMWaA=='))
		url_handras_m = 'auto_handras_csatorna_m'
		desc_handras_m = self.getdvdsz(url_handras_m, 'Handras TV csatorna videói...')
		plurl_autosaman = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoeZBATmGRaFJwc65YXkRnu7mSaaWxekA37YWiw=='))
		url_autosaman_m = 'auto_autosaman_csatorna_m'
		desc_autosaman_m = self.getdvdsz(url_autosaman_m, 'AutóSámán.hu csatorna videói...')
		plurl_autoroom = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoUEWhVEpXh5G3vnBibrJ6eXmOY6FpY4A4IAWwA=='))
		url_autoroom_m = 'auto_autoroom_csatorna_m'
		desc_autoroom_m = self.getdvdsz(url_autoroom_m, 'AutoRoom csatorna videói...')
		plurl_villany = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoeGlIVEp7m6FXt4eOZnZuhleBpXJYekA5WcW/Q=='))
		url_villany_m = 'auto_villany_csatorna_m'
		desc_villany_m = self.getdvdsz(url_villany_m, 'Villanyautósok csatorna videói...')
		plurl_alapjarat = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahoaWpOan+UUaBbo6JYcEeERmpUTlumekA5dUXDQ=='))
		url_alapjarat_m = 'auto_alapjarat_csatorna_m'
		desc_alapjarat_m = self.getdvdsz(url_alapjarat_m, 'Alapjárat csatorna videói...')
		plurl_speedzone = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPibp/pEpQSFOlkFGHmVpWbqRhuGuQWGhUXlVKR7JGeWVAM3SGiE='))
		url_speedzone_m = 'auto_speedzone_m'
		desc_speedzone_m = self.getdvdsz(url_speedzone_m, 'Speedzone csatorna videói...')
		plurl_autobabbo = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPqmBmQF+lZmZFeYeyQbhqQY+6eFBaZnlaeGOVZmWpkkBAN+hGm8='))
		url_autobabbo_m = 'auto_autobabbo_m'
		desc_autobabbo_m = self.getdvdsz(url_autobabbo_m, 'Autó Babbo csatorna videói...')
		MT_CAT_TAB = [{'category':'list_second', 'title': 'Vezess TV', 'url': url_vezess_m, 'tab_id': 'vezess_m', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_m},
					  {'category':'list_second', 'title': 'Totalcar', 'url': url_totalcar_m, 'tab_id': 'totalcar_m', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_totalcar_m},
					  {'category':'list_second', 'title': 'Autónavigátor', 'url': url_autonav_m, 'plurl': plurl_autonav, 'tab_id': 'autonav_m', 'icon': self.DEFAULT_ICON_URL_AUTONAV, 'desc': desc_autonav_m},
					  {'category':'list_second', 'title': 'Handras TV', 'url': url_handras_m, 'plurl': plurl_handras_m, 'tab_id': 'handras_m', 'icon': self.DEFAULT_ICON_URL_HANDRAS, 'desc': desc_handras_m},
					  {'category':'list_second', 'title': 'AutóSámán', 'url': url_autosaman_m, 'plurl': plurl_autosaman, 'tab_id': 'autosaman_m', 'icon': self.DEFAULT_ICON_URL_AUTOSAMAN, 'desc': desc_autosaman_m},
					  {'category':'list_second', 'title': 'AutoRoom', 'url': url_autoroom_m, 'plurl': plurl_autoroom, 'tab_id': 'autoroom_m', 'icon': self.DEFAULT_ICON_URL_AUTOROOM, 'desc': desc_autoroom_m},
					  {'category':'list_second', 'title': 'Villanyautósok', 'url': url_villany_m, 'plurl': plurl_villany, 'tab_id': 'villany_m', 'icon': self.DEFAULT_ICON_URL_VILLANY, 'desc': desc_villany_m},
					  {'category':'list_second', 'title': 'Alapjárat', 'url': url_alapjarat_m, 'plurl': plurl_alapjarat, 'tab_id': 'alapjarat_m', 'icon': self.DEFAULT_ICON_URL_ALAPJARAT, 'desc': desc_alapjarat_m},
					  {'category':'list_second', 'title': 'Speedzone', 'url': url_speedzone_m, 'plurl': plurl_speedzone, 'tab_id': 'speedzone_m', 'icon': self.DEFAULT_ICON_URL_SPEEDZONE, 'desc': desc_speedzone_m},
					  {'category':'list_second', 'title': 'Autó Babbo', 'url': url_autobabbo_m, 'plurl': plurl_autobabbo, 'tab_id': 'autobabbo_m', 'icon': self.DEFAULT_ICON_URL_AUTOBABBO, 'desc': desc_autobabbo_m}
					 ]
		self.listsTab(MT_CAT_TAB, cItem)
		
	def SzabalytalanMainMenu(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		plurl_bpiautosok = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbahof5RoRY+oUbm5R4uVcWREWZJSVEp4ekA3i4Wsw=='))
		url_bpiautosok = 'auto_bpiautosok_m'
		desc_bpiautosok = self.getdvdsz(url_bpiautosok, 'Bp-i Autósok Közössége csatorna videói...')
		plurl_112press = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPm7m5YmhlfFVluaF5iUeFZ6Gge4e3o5Rll7uBo7x5WXJANORGcA='))
		url_112press = 'auto_112press_m'
		desc_112press = self.getdvdsz(url_112press, '112 Press csatorna videói...')
		MT_CAT_TAB = [{'category':'list_second', 'title': 'Bp-i Autósok Közössége', 'url': url_bpiautosok, 'plurl': plurl_bpiautosok, 'tab_id': 'bpiautosok_m', 'icon': self.DEFAULT_ICON_URL_BPIAUTOSOK, 'desc': desc_bpiautosok},
					  {'category':'list_second', 'title': '112 Press', 'url': url_112press, 'plurl': plurl_112press, 'tab_id': '112press_m', 'icon': self.DEFAULT_ICON_URL_112PRESS, 'desc': desc_112press}
					 ]
		self.listsTab(MT_CAT_TAB, cItem)
							
	def getFullIconUrl(self, url):
		url = url.replace('&amp;', '&')
		return CBaseHostClass.getFullIconUrl(self, url)
		
	def getFullIconUrl_Autogram(self, url):
		if not url: return self.DEFAULT_ICON_URL_AUTOGRAM
		if url[:1] == 't':
			width = 250
			height = 617
		else:
			width = 480
			height = 360
		if url[1:2] == 'p': format = 'png'
		else: format = 'jpeg'
		path = self.ICON_PATH.format(url[2:],width,height,'scale_crop',60,format,1)
		return self.ICON_URL.format(path, sha1(path+self.ICON_HASH).hexdigest())
		
	def getPage(self, baseUrl, addParams = {}, post_data = None):
		if addParams == {}:
			addParams = dict(self.defaultParams)
		
		def _getFullUrl(url):
			if self.cm.isValidUrl(url):
				return url
			else:
				return urlparse.urljoin(baseUrl, url)
			
		addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
		sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
		return sts, data

	def datum_converter(self, date_string, separator='-'):
		dateList = []
		dateList = date_string.split(".")
		if len(dateList) != 2: 
			return date_string
		if not dateList[0].isdigit():
			return date_string
		month_string = dateList[1].strip()
		if month_string in ('január','januar','Január','Januar'):
			return dateList[0] + separator + '01'
		elif month_string in ('február','februar','Február','Februar'):
			return dateList[0] + separator + '02'    
		elif month_string in ('március','marcius','Március','Marcius'):
			return dateList[0] + separator + '03'
		elif month_string in ('április','aprilis','Április','Aprilis'):
			return dateList[0] + separator + '04'
		elif month_string in ('május','majus','Május','Majus'):
			return dateList[0] + separator + '05'
		elif month_string in ('június','junius','Június','Junius'):
			return dateList[0] + separator + '06'
		elif month_string in ('július','julius','Július','Julius'):
			return dateList[0] + separator + '07'
		elif month_string in ('augusztus','Augusztus'):
			return dateList[0] + separator + '08'
		elif month_string in ('szeptember','Szeptember'):
			return dateList[0] + separator + '09'
		elif month_string in ('október','oktober','Október','Oktober'):
			return dateList[0] + separator + '10'
		elif month_string in ('november','November'):
			return dateList[0] + separator + '11'
		elif month_string in ('december','December'):
			return dateList[0] + separator + '12'
		else:
			return date_string
			
	def honapnev_e(self, honap_string=''):
		if honap_string != '':
			if honap_string in ('január','Január','február','Február','március','Március','április','Április','május','Május','június','Június','július','Július','augusztus','Augusztus','szeptember','Szeptember','október','Október','november','November','december','December'):
				return True
			else:
				return False            
		else:        
			return False
			
	def ev_e(self, ev_string='', jelenkor=False, eddig_string='2030'):
		if ev_string != '':
			if jelenkor:
				m = re.search(r'[2]\d{3}',ev_string)
				if m is not None:
					try:
						eddig = int(eddig_string)
						ev = int(m.group(0))
						if ev > 2000 or ev < eddig:
							return True
						else:
							return False
					except:
						return False
					return True
				else:
					return False
			else:
				m = re.search(r'\d{4}',ev_string)
				if m is not None:
					return True
				else:
					return False
		else:
			return False
			
	def ekezetes_atalakitas(self, szoveg=''):
		if szoveg != '':
			szoveg = szoveg.replace('&aacute;', 'á')
			szoveg = szoveg.replace('&eacute;', 'é')
			szoveg = szoveg.replace('&iacute;', 'í')
			szoveg = szoveg.replace('&oacute;', 'ó')
			szoveg = szoveg.replace('&uacute;', 'ú')
		return szoveg        
			
	def datum_honapos(self, date_string, delimiter='.'):
		dateList = []
		dateList = date_string.split(delimiter)
		if len(dateList) < 3: 
			return date_string
		for i in (0,1,2):
			if not dateList[i].isdigit():
				return date_string
		if dateList[1] == '01':
			return dateList[0] + '. január ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '02':
			return dateList[0] + '. február ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '03':
			return dateList[0] + '. március ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '04':
			return dateList[0] + '. április ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '05':
			return dateList[0] + '. május ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '06':
			return dateList[0] + '. június ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '07':
			return dateList[0] + '. július ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '08':
			return dateList[0] + '. augusztus ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '09':
			return dateList[0] + '. szeptember ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '10':
			return dateList[0] + '. október ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '11':
			return dateList[0] + '. november ' + dateList[2].lstrip('0') + '.'
		elif dateList[1] == '12':
			return dateList[0] + '. decmber ' + dateList[2].lstrip('0') + '.'
		else:
			return date_string
			
	def datum_from_honapos(self, date_string, separator='-'):
		dateList = []
		dateList = date_string.split(' ')
		if len(dateList) < 3: 
			return date_string
		if not self.ev_e(dateList[0], True):
			return date_string
		ev_string = dateList[0].strip().replace('.','')
		month_string = dateList[1].strip()
		nap_string = dateList[2].strip().replace('.','')
		if month_string in ('január','januar','Január','Januar'):
			return ev_string + separator + '01' + separator + nap_string
		elif month_string in ('február','februar','Február','Februar'):
			return ev_string + separator + '02' + separator + nap_string   
		elif month_string in ('március','marcius','Március','Marcius'):
			return ev_string + separator + '03' + separator + nap_string
		elif month_string in ('április','aprilis','Április','Aprilis'):
			return ev_string + separator + '04' + separator + nap_string
		elif month_string in ('május','majus','Május','Majus'):
			return ev_string + separator + '05' + separator + nap_string
		elif month_string in ('június','junius','Június','Junius'):
			return ev_string + separator + '06' + separator + nap_string
		elif month_string in ('július','julius','Július','Julius'):
			return ev_string + separator + '07' + separator + nap_string
		elif month_string in ('augusztus','Augusztus'):
			return ev_string + separator + '08' + separator + nap_string
		elif month_string in ('szeptember','Szeptember'):
			return ev_string + separator + '09' + separator + nap_string
		elif month_string in ('október','oktober','Október','Oktober'):
			return ev_string + separator + '10' + separator + nap_string
		elif month_string in ('november','November'):
			return ev_string + separator + '11' + separator + nap_string
		elif month_string in ('december','December'):
			return ev_string + separator + '12' + separator + nap_string
		else:
			return date_string
			
	def Garazs_data(self):
		try:
			data = []
			uhe = self.MAIN_URL_GARAZS_ADASOK
			ptdt = {'_kiemelt':'1', '_akcios':'', '_uj':'', '_nezet':'tablazat', '_random':'', '_tol':'0', '_orderby':'', '_where':" and ty.id not in ('LAPTIME','STORYKAT','TUNINGKAT','TESZTKAT')  and hsz.focusnr<'01' ", '_keres_txt':'', '_dblap':'150', 'lapozas':'1', '_sum':'421', '_mutat':'6' }
			sts, data = self.cm.getPage(uhe, self.defaultParams, ptdt)
			if not sts: return data
			if len(data) == 0: return data
			data = self.cm.ph.getDataBeetwenMarkers(data, '<form id="lapozo"', '<input')[1]
			if len(data) == 0: return data
			data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div class=', '>', 'block'), ('<span class="date', '</span>'))
			return data
		except Exception:
			printExc()
			return data

	def listMainItems(self, cItem, nextCategory):
		try:
			tabID = cItem.get('tab_id', '')
			if tabID == 'legfrissebb':
				self.Legfrissebb_MainItems(cItem, tabID)
			elif tabID == 'veletlenszeru':
				self.Veletlen_MainItems(cItem, tabID)
			elif tabID == 'tipusok':
				self.Tipusok_MainItems(cItem, nextCategory, tabID)
			elif tabID == 'autoskoz':
				self.MusorMainMenu(cItem, nextCategory, tabID)
			elif tabID == 'mindentudo':
				self.MindentudoMainMenu(cItem, nextCategory, tabID)
			elif tabID == 'szabalytalan':
				self.SzabalytalanMainMenu(cItem, nextCategory, tabID)
			elif tabID == 'forma1':
				self.Forma1_MainItems(cItem, nextCategory, tabID)
			else:
				return
		except Exception:
			printExc()
			
	def listSecondItems(self, cItem, nextCategory):
		try:
			tabID = cItem.get('tab_id', '')
			if tabID == 'autogram':
				self.Autogram_MainItems(cItem, nextCategory, tabID)
			elif tabID == 'garazs':
				self.Garazs_MainItems(cItem, nextCategory, tabID)
			elif tabID == 'supercar':
				self.Supercar_MainItems(cItem, nextCategory, tabID)
			elif tabID == 'totalcar':
				self.Totalcar_MainItems(cItem, nextCategory, tabID)
			elif tabID == 'holvezes':
				self.Holvezes_MainItems(cItem, nextCategory, tabID)
			elif tabID == 'totalcar_m':
				self.Totalcar_mindentudolista(cItem, nextCategory, tabID)
			elif tabID == 'vezess_m':
				self.Vezess_mindentudolista(cItem, nextCategory, tabID)
			elif tabID == 'autonav_m':
				self.Ytpl_lista(cItem, tabID, 'autonav')
			elif tabID == 'handras_m':
				self.Ytpl_lista(cItem, tabID, 'hand')
				#self.Handras_lista(cItem, nextCategory, tabID)
			elif tabID == 'autoshow':
				self.Ytpl_lista(cItem, tabID, 'ash')
			elif tabID == 'fordrive':
				self.Ytpl_lista(cItem, tabID, 'fordrive')
			elif tabID == 'autosaman_m':
				self.Ytpl_lista(cItem, tabID, 'asm')
			elif tabID == 'autoroom_m':
				self.Ytpl_lista(cItem, tabID, 'asr')
			elif tabID == 'villany_m':
				self.Ytpl_lista(cItem, tabID, 'villany')
			elif tabID == 'alapjarat_m':
				self.Ytpl_lista(cItem, tabID, 'alapjarat')
			elif tabID == 'bpiautosok_m':
				self.Ytpl_lista(cItem, tabID, 'bpiautosok')
			elif tabID == '112press_m':
				self.Ytpl_lista(cItem, tabID, '112press')
			elif tabID == 'speedzone_m':
				self.Ytpl_lista(cItem, tabID, 'speedzone')
			elif tabID == 'autobabbo_m':
				self.Ytpl_lista(cItem, tabID, 'autobabbo')
			else:
				return
		except Exception:
			printExc()
			
	def Vezess_mindentudolista(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		plurl_vezess_matksz = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVB4X6GBsEm5gYWqamlhkkV3qEFPs6GANqaGcw='))
		url_vezess_matksz = 'auto_vezess_matksz'
		desc_vezess_matksz = self.getdvdsz(url_vezess_matksz, 'Minden amit tudni akarsz az autókról...\nElméleti és gyakorlati bemutatása az autózás műfajának. Ok-okozati összefüggések, elemzések, előnyök, hátrányok. Érdekes videók a témával kapcsolatban Gajdán Miklóssal.')
		plurl_vezess_ertekb = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVBFpH5ebo5xWYukWXmjkl+eVWVzu7lAOZaGtM='))
		url_vezess_ertekb = 'auto_vezess_ertekb'
		desc_vezess_ertekb = self.getdvdsz(url_vezess_ertekb, 'Autók értékbecslése, hibafeltárása, átvizsgálása...\nHasznált autókról Őszintén.')
		plurl_vezess_aszaloncs = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVBHmWZxc6BpgHlvuHGaf4+xq7GlUa5AOWCGks='))
		url_vezess_aszaloncs = 'auto_vezess_aszaloncs'
		desc_vezess_aszaloncs = self.getdvdsz(url_vezess_aszaloncs, 'Autószalonokon készült videók, interjuk...\nGenf, Frankfurt, Párizs, illetve egyéb más autóbemutatók felvételei, videói.')
		plurl_vezess_ojkogm = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQUhWbnenoaRjuZVyabZrpFBpZleTtnmAOSnGm4='))
		url_vezess_ojkogm = 'auto_vezess_ojkogm'
		desc_vezess_ojkogm = self.getdvdsz(url_vezess_ojkogm, 'Olaj, kenőolaj témakör Gajdán Miklóssal...\nMotorolajok legfontosabb tulajdonságai, adalékok. Hogyan válasszunk olajat.')
		plurl_vezess_bgtgml = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQVBJgEhfmFufn66RqkGOb6JVeaROU4GANySGdo='))
		url_vezess_bgtgml = 'auto_vezess_bgtgml'
		desc_vezess_bgtgml = self.getdvdsz(url_vezess_bgtgml, 'Benzin, gázolaj témakör Gajdán Miklóssal...\n Mi a különbség a két üzemanyag fajta között. Benzinkút, tankolás, prémiumüzemanyagok.')
		plurl_vezess_htank = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQWBlinlqRV+Bi7mke6e6amergZ+EW6WAONZGgc='))
		url_vezess_htank = 'auto_vezess_htank'
		desc_vezess_htank = self.getdvdsz(url_vezess_htank, 'Hasznos tanácsok autósoknak...')
		plurl_vezess_haaktink = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQXBHqlVBqaepmbGmW7mxY4myVGlrm5VANzHGf8='))
		url_vezess_haaktink = 'auto_vezess_haaktink'
		desc_vezess_haaktink = self.getdvdsz(url_vezess_haaktink, 'Használt autók amiket imádunk mi magyarok...')
		plurl_vezess_trahvzs = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPsWVRalhmcbhWQWB6T6+QeWhicaOFkk5+fGWfpYeWfEZAOUiGoU='))
		url_vezess_trahvzs = 'auto_vezess_trahvzs'
		desc_vezess_trahvzs = self.getdvdsz(url_vezess_trahvzs, 'Ütközések, karambolok...')
		MV_CAT_TAB = [{'category':'list_third', 'title': '1 - Minden amit tudni akarsz az autókról - Gajdán Miklóssal', 'url': url_vezess_matksz, 'plurl': plurl_vezess_matksz, 'tab_id': 'vezess_matksz', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_matksz},
					  {'category':'list_third', 'title': '2 - Használt autókról őszintén - ÉRTÉKBECSLŐ', 'url': url_vezess_ertekb, 'plurl': plurl_vezess_ertekb, 'tab_id': 'vezess_ertekb', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_ertekb},
					  {'category':'list_third', 'title': '3 - Autószalonok csillogása', 'url': url_vezess_aszaloncs, 'plurl': plurl_vezess_aszaloncs, 'tab_id': 'vezess_aszaloncs', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_aszaloncs},
					  {'category':'list_third', 'title': '4 - Olaj, kenőolaj témakör Gajdán Miklóssal', 'url': url_vezess_ojkogm, 'plurl': plurl_vezess_ojkogm, 'tab_id': 'vezess_ojkogm', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_ojkogm},
					  {'category':'list_third', 'title': '5 - Benzin, gázolaj témakör Gajdán Miklóssal', 'url': url_vezess_bgtgml, 'plurl': plurl_vezess_bgtgml, 'tab_id': 'vezess_bgtgml', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_bgtgml},
					  {'category':'list_third', 'title': '6 - Hasznos tanácsok autósoknak', 'url': url_vezess_htank, 'plurl': plurl_vezess_htank, 'tab_id': 'vezess_htank', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_htank},
					  {'category':'list_third', 'title': '7 - Használt autók amiket imádunk mi magyarok', 'url': url_vezess_haaktink, 'plurl': plurl_vezess_haaktink, 'tab_id': 'vezess_haaktink', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_haaktink},
					  {'category':'list_third', 'title': '8 - Trash', 'url': url_vezess_trahvzs, 'plurl': plurl_vezess_trahvzs, 'tab_id': 'vezess_trahvzs', 'icon': self.DEFAULT_ICON_URL_VEZESS, 'desc': desc_vezess_trahvzs}
					 ]
		self.listsTab(MV_CAT_TAB, cItem)
		
	def Totalcar_mindentudolista(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		plurl_total_trtk = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S/ISazMySwusQcRtgE+Hs6lga4mgf5RPhGmLjlBxS4eOQbxfslZJRmeZWmeho4ArcAZSw=='))
		url_total_trtk = 'auto_total_trtk'
		desc_total_trtk = self.getdvdsz(url_total_trtk, 'Totalcar Tesztek műsorai, videói...\nÚj és használtautó tesztek, összehasonlítások, végsebességtesztek.')
		plurl_total_mlypn = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5h3k7pyfFuxj4hFYYWwZWVYX6RPlnFAMwNGc8='))
		url_total_mlypn = 'auto_total_mlypn'
		desc_total_mlypn = self.getdvdsz(url_total_mlypn, 'MűhelyPRN műsorai, videói...\nHasznált autók felújításainak, karbantartásainak bemutatása.')
		plurl_total_treo = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT6hOT4BWUFlZh5GhY4e2eVBjhFZoRnlAM9hGgI='))
		url_total_treo = 'auto_total_treo'
		desc_total_treo = self.getdvdsz(url_total_treo, 'Totalcar Erőmérő műsorai, videói...\nKülönböző autók teljesítménymérései, állapotfelmérései.')
		plurl_total_tlbk = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5hYYZlZlGlOXkpheYV4VW6eZ5prjnuANMlGic='))
		url_total_tlbk = 'auto_total_tlbk'
		desc_total_tlbk = self.getdvdsz(url_total_tlbk, 'Totalbike műsorai, videói...\nInformációk, élménybeszámolók különböző motorokról és a hozzátartozó kiegészítőkről.')
		plurl_total_szjsn = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT6hLhUuUYEWwYWJAZlBRq6OLuGRpRneAMxtGZo='))
		url_total_szjsn = 'auto_total_szjsn'
		desc_total_szjsn = self.getdvdsz(url_total_szjsn, 'Szerelj Szabadon! műsorai, videói...\nAz autó különböző részegységeinek, alkatrészeinek cseréje, szerelése, javítása. Műhelyinformációk és szerelési videók bemutatása.')
		plurl_total_trmks = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5hBUmhhcEhOZ6+3kWmES6ema65RlUWANIUGcs='))
		url_total_trmks = 'auto_total_trmks'
		desc_total_trmks = self.getdvdsz(url_total_trmks, 'Totalcar Mesterkurzus - Autókról alaposan! műsorai, videói...\nInformációk autótuningról, autókészítésről.')
		plurl_total_uzk = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT5hrvHxubnejgEe4X55AVGRRVVREYFhANDUGhA='))
		url_total_uzk = 'auto_total_uzk'
		desc_total_uzk = self.getdvdsz(url_total_uzk, 'Utazunk műsorai, videói...\nAutós információk utazáshoz. Tesztelések több napon át. Takarékossági tesztek.')
		plurl_total_tlac = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvyEmszMksLrEHEbYBPh7OpYGuJoH+UT4RrtnOmeVlxQElUQYhnvEV2clpFT4+ANaPGng='))
		url_total_tlac = 'auto_total_tlac'
		desc_total_tlac = self.getdvdsz(url_total_tlac, 'TotalArc műsorai, videói...\nAutósműsor emberekről. Történetek és egyéb információk megosztása, elmesélése.')
		MT_CAT_TAB = [{'category':'list_third', 'title': '1 - Totalcar Tesztek', 'url': url_total_trtk, 'plurl': plurl_total_trtk, 'tab_id': 'total_trtk', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_trtk},
					  {'category':'list_third', 'title': '2 - MűhelyPRN', 'url': url_total_mlypn, 'plurl': plurl_total_mlypn, 'tab_id': 'total_mlypn', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_mlypn},
					  {'category':'list_third', 'title': '3 - Totalcar Erőmérő', 'url': url_total_treo, 'plurl': plurl_total_treo, 'tab_id': 'total_treo', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_treo},
					  {'category':'list_third', 'title': '4 - Totalbike', 'url': url_total_tlbk, 'plurl': plurl_total_tlbk, 'tab_id': 'total_tlbk', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_tlbk},
					  {'category':'list_third', 'title': '5 - Szerelj Szabadon!', 'url': url_total_szjsn, 'plurl': plurl_total_szjsn, 'tab_id': 'total_szjsn', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_szjsn},
					  {'category':'list_third', 'title': '6 - Totalcar Mesterkurzus - Autókról alaposan!', 'url': url_total_trmks, 'plurl': plurl_total_trmks, 'tab_id': 'total_trmks', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_trmks},
					  {'category':'list_third', 'title': '7 - Utazunk', 'url': url_total_uzk, 'plurl': plurl_total_uzk, 'tab_id': 'total_uzk', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_uzk},
					  {'category':'list_third', 'title': '8 - TotalArc', 'url': url_total_tlac, 'plurl': plurl_total_tlac, 'tab_id': 'total_tlac', 'icon': self.DEFAULT_ICON_URL_TOTALCAR, 'desc': desc_total_tlac}
					 ]
		self.listsTab(MT_CAT_TAB, cItem)
			
	def Legfrissebb_MainItems(self, cItem, tabID):
		url = cItem['url']
		try:
			self.susn('2', '1', url)
			params = dict()
			params = self.Autogram_Legfrissebb()
			if params: self.addVideo(params)
			params = self.Garazs_Legfrissebb()
			if params: self.addVideo(params)
			params = self.Supercar_Legfrissebb()
			if params: self.addVideo(params)
			params = self.Totalcar_Legfrissebb()
			if params: self.kiirtt(params,'','totalcar')
			params = self.Forma1_Legfrissebb()
			if params: self.addVideo(params)
			params = self.Ytlfl(self.plurl_autonav, 'autonav')
			if params: self.kiirtt(params,'Autónavigátor - ','autonav_m')
			params = self.Holvezes_Legfrissebb()
			if params: self.kiirtt(params,'Holvezessek - ','holvezes')
			params = self.Ytlfl(self.plurl_hand, 'hand')
			if params: self.kiirtt(params,'Handras TV - ','handras_m')
			params = self.Ytlfl(self.plurl_asr, 'asr')
			if params: self.kiirtt(params,'AutoRoom - ','autoroom_m')
			params = self.Ytlfl(self.plurl_asm, 'asm')
			if params: self.kiirtt(params,'AutóSámán - ','autosaman_m')
			params = self.Ytlfl(self.plurl_villany, 'villany')
			if params: self.kiirtt(params,'Villanyautósok - ','villany_m')
			params = self.Ytlfl(self.plurl_alapjarat, 'alapjarat')
			if params: self.kiirtt(params,'Alapjárat - ','alapjarat_m')
			params = self.Ytlfl(self.plurl_bpiautosok, 'bpiautosok')
			if params: self.kiirtt(params,'Bp-i Autósok Közössége - ','bpiautosok_m')
			params = self.Ytlfl(self.plurl_112press, '112press')
			if params: self.kiirtt(params,'112 Press - ','112press_m')
			params = self.Ytlfl(self.plurl_speedzone, 'speedzone')
			if params: self.kiirtt(params,'Speedzone - ','speedzone_m')
			params = self.Ytlfl(self.plurl_autobabbo, 'autobabbo')
			if params: self.kiirtt(params,'Autó Babbo - ','autobabbo_m')
			params = self.Ytlfl(self.plurl_autoshow, 'ash')
			if params: self.kiirtt(params,'AutoSHOW - ','autoshow')
			params = self.Ytlfl(self.plurl_fordrive, 'fordrive')
			if params: self.kiirtt(params,'4Drive Time - ','fordrive')	
			params = self.Ytlfl_vs(self.plurl_vezess_matksz, 'vs')
			if params: self.kiirtt(params,'Vezess1 - ','vezess_matksz')
			params = self.Ytlfl_vs(self.plurl_vezess_ertekb, 'vs')
			if params: self.kiirtt(params,'Vezess2 - ','vezess_ertekb')
			params = self.Ytlfl_vs(self.plurl_vezess_aszaloncs, 'vs')
			if params: self.kiirtt(params,'Vezess3 - ','vezess_aszaloncs')
			params = self.Ytlfl_vs(self.plurl_vezess_ojkogm, 'vs')
			if params: self.kiirtt(params,'Vezess4 - ','vezess_ojkogm')
			params = self.Ytlfl_vs(self.plurl_vezess_bgtgml, 'vs')
			if params: self.kiirtt(params,'Vezess5 - ','vezess_bgtgml')
			params = self.Ytlfl_vs(self.plurl_vezess_htank, 'vs')
			if params: self.kiirtt(params,'Vezess6 - ','vezess_htank')
			params = self.Ytlfl_vs(self.plurl_vezess_haaktink, 'vs')
			if params: self.kiirtt(params,'Vezess7 - ','vezess_haaktink')
			params = self.Ytlfl_vs(self.plurl_vezess_trahvzs, 'vs')
			if params: self.kiirtt(params,'Vezess8 - ','vezess_trahvzs')
			params = self.Ytlfl_tc(self.plurl_total_trtk, 'tc')
			if params: self.kiirtt(params,'Totalcar1 - ','total_trtk')
			params = self.Ytlfl_tc(self.plurl_total_mlypn, 'tc')
			if params: self.kiirtt(params,'Totalcar2 - ','total_mlypn')
			params = self.Ytlfl_tc(self.plurl_total_treo, 'tc')
			if params: self.kiirtt(params,'Totalcar3 - ','total_treo')
			params = self.Ytlfl_tc(self.plurl_total_tlbk, 'tc')
			if params: self.kiirtt(params,'Totalcar4 - ','total_tlbk')
			params = self.Ytlfl_tc(self.plurl_total_szjsn, 'tc')
			if params: self.kiirtt(params,'Totalcar5 - ','total_szjsn')
			params = self.Ytlfl_tc(self.plurl_total_trmks, 'tc')
			if params: self.kiirtt(params,'Totalcar6 - ','total_trmks')
			params = self.Ytlfl_tc(self.plurl_total_uzk, 'tc')
			if params: self.kiirtt(params,'Totalcar7 - ','total_uzk')
			params = self.Ytlfl_tc(self.plurl_total_tlac, 'tc')
			if params: self.kiirtt(params,'Totalcar8 - ','total_tlac')
			#vtb = self.malvadnav(cItem, '1', '1', '3')
			#if len(vtb) > 0:
			#    for item in vtb:
			#        self.addVideo(item)
		except Exception:
			return
			
	def kiirtt(self, params, tsz='', tab_id='-'):
		if params:
			if params['datum'] != '':
				datum = datetime.strptime(params['datum'], "%Y. %m. %d.").date()
				akt_datum = datetime.now().date()
				kulonbseg = (akt_datum - datum).days
				if kulonbseg >= 0 and kulonbseg < 15:
					title = params['title'].strip()
					tempdesc = params['desc'].strip()
					if tempdesc != '':
						tempdesc = tempdesc.replace('\n','KKKK')
						tempdesc = re.sub(r'^(.{600}).*$', '\g<1>...', tempdesc.strip())
						tempdesc = tempdesc.replace('KKKK','\n')
					if tab_id == 'speedzone_m':
						title = title.replace('Speedzone teszt:','').strip()
						title = title.replace('Speedzone-használt teszt:','').strip()
						title = title.replace('Újautó-teszt:','').strip()
						title = title.replace('Speedzone-gyorsteszt:','').strip()
						if tempdesc != '':
							tempdesc = tempdesc.replace('http://www.autohitel.hu','')
							tempdesc = tempdesc.replace('http://www.patreon.com/speedzone','')
							tempdesc = tempdesc.replace('http://patreon.com/speedzone','')
							tempdesc = tempdesc.replace('http://www.speedzoneshop.hu','')
							tempdesc = tempdesc.replace('http://www.sixst.hu','')
					params['desc'] = tempdesc
					params['title'] = tsz + title
					params = MergeDicts(params, {'good_for_fav': False, 'tab_id':tab_id})
					self.addVideo(params) 
			else:
				title = params['title'].strip()
				tempdesc = params['desc'].strip()
				if tempdesc != '':
					tempdesc = tempdesc.replace('\n','KKKK')
					tempdesc = re.sub(r'^(.{600}).*$', '\g<1>...', tempdesc.strip())
					tempdesc = tempdesc.replace('KKKK','\n')
				if tab_id == 'speedzone_m':
					title = title.replace('Speedzone teszt:','').strip()
					title = title.replace('Speedzone-használt teszt:','').strip()
					title = title.replace('Újautó-teszt:','').strip()
					title = title.replace('Speedzone-gyorsteszt:','').strip()
					if tempdesc != '':
						tempdesc = tempdesc.replace('http://www.autohitel.hu','')
						tempdesc = tempdesc.replace('http://www.patreon.com/speedzone','')
						tempdesc = tempdesc.replace('http://patreon.com/speedzone','')
						tempdesc = tempdesc.replace('http://www.speedzoneshop.hu','')
						tempdesc = tempdesc.replace('http://www.sixst.hu','')
				params['desc'] = tempdesc
				params['title'] = tsz + title
				params = MergeDicts(params, {'good_for_fav': False, 'tab_id':tab_id})
				self.addVideo(params) 
			
	def lfrbfts(self):
		try:
			params = dict()
			#params = self.Autogram_Legfrissebb()
			#if params: self.susmafts('2', '1', '3', '1', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_trtk, 'tc')
			if params: self.susmafts('2', '1', '3', '6', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_mlypn, 'tc')
			if params: self.susmafts('2', '1', '3', '7', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_treo, 'tc')
			if params: self.susmafts('2', '1', '3', '8', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_tlbk, 'tc')
			if params: self.susmafts('2', '1', '3', '9', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_szjsn, 'tc')
			if params: self.susmafts('2', '1', '3', '10', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_trmks, 'tc')
			if params: self.susmafts('2', '1', '3', '11', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_uzk, 'tc')
			if params: self.susmafts('2', '1', '3', '12', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_tc(self.plurl_total_tlac, 'tc')
			if params: self.susmafts('2', '1', '3', '13', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_matksz, 'vs')
			if params: self.susmafts('2', '1', '3', '15', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_ertekb, 'vs')
			if params: self.susmafts('2', '1', '3', '16', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_aszaloncs, 'vs')
			if params: self.susmafts('2', '1', '3', '17', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_ojkogm, 'vs')
			if params: self.susmafts('2', '1', '3', '18', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_bgtgml, 'vs')
			if params: self.susmafts('2', '1', '3', '19', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_htank, 'vs')
			if params: self.susmafts('2', '1', '3', '20', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_haaktink, 'vs')
			if params: self.susmafts('2', '1', '3', '21', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl_vs(self.plurl_vezess_trahvzs, 'vs')
			if params: self.susmafts('2', '1', '3', '22', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_fordrive, 'fordrive')
			if params: self.susmafts('2', '1', '3', '25', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_autonav, 'autonav')
			if params: self.susmafts('2', '1', '3', '26', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_hand, 'hand')
			if params: self.susmafts('2', '1', '3', '27', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_asm, 'asm')
			if params: self.susmafts('2', '1', '3', '28', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_asr, 'asr')
			if params: self.susmafts('2', '1', '3', '29', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_villany, 'villany')
			if params: self.susmafts('2', '1', '3', '50', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_alapjarat, 'alapjarat')
			if params: self.susmafts('2', '1', '3', '51', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_bpiautosok, 'bpiautosok')
			if params: self.susmafts('2', '1', '3', '52', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_112press, '112press')
			if params: self.susmafts('2', '1', '3', '53', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_speedzone, 'speedzone')
			if params: self.susmafts('2', '1', '3', '54', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
			params = self.Ytlfl(self.plurl_autobabbo, 'autobabbo')
			if params: self.susmafts('2', '1', '3', '55', params['url'], params['title'], params['icon'], params['desc'], '-', '-', '-')
		except Exception:
			return
			
	def Ytlfl(self, url='', mk='vs'):
		params = dict()
		if url != '':
			playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
			baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
			if baseUrl != '':
				sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
				try:
					data = json_loads(data)['video']
					for item in data:
						url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
						title = CParsingHelper.cleanHtmlStr(item['title'])
						img   = item['thumbnail']
						time  = item['duration']
						added = item['added']
						tempdesc = item['description']
						tempdesc = tempdesc.replace('\n','')
						if mk == 'ash': tempdesc = self.szovegki_ash(tempdesc)
						if mk == 'fordrive': tempdesc = self.szovegki_fordrive(tempdesc)
						if mk == 'asr': tempdesc = self.szovegki_asr(tempdesc)
						if mk == 'asm': tempdesc = self.szovegki_asm(tempdesc)
						if mk == 'hand': tempdesc = self.szovegki_hand(tempdesc)
						if mk == 'villany': tempdesc = self.szovegki_villany(tempdesc)
						if mk == 'autonav': tempdesc = self.szovegki_autonav(tempdesc)
						if mk == 'alapjarat': tempdesc = self.szovegki_alapjarat(tempdesc)
						if mk == 'speedzone': tempdesc = self.szovegki_speedzone(tempdesc)
						if mk == 'autobabbo': tempdesc = self.szovegki_autobabbo(tempdesc)
						desc = added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
						params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'desc': desc, 'datum': added}
						break
					return params
				except Exception:
					return params
			else:
				return params
		else:
			return params
			
	def Ytlfl_tc(self, url='', mk='tc'):
		params = dict()
		if url != '':
			playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
			baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
			if baseUrl != '':
				sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
				try:
					data = json_loads(data)['video']
					for item in data:
						url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
						title = CParsingHelper.cleanHtmlStr(item['title'])
						img   = item['thumbnail']
						time  = item['duration']
						added  = item['added']
						tempdesc  = item['description']
						tempdesc = tempdesc.replace('\n','')
						if mk == 'tc': tempdesc = self.szovegki_tc(tempdesc)
						desc = added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
						params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'desc': desc, 'datum': added}
						break
					return params
				except Exception:
					return params
			else:
				return params
		else:
			return params
			
	def Ytlfl_vs(self, url='', mk='vs'):
		params = dict()
		if url != '':
			playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
			baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
			if baseUrl != '':
				sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
				try:
					data = json_loads(data)['video']
					for item in data:
						if 'vezess' not in item['author'].lower():
							continue
						url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
						title = CParsingHelper.cleanHtmlStr(item['title'])
						title_ere = title
						tlt = title.rfind('- ')
						if -1 < tlt:
							title = title[:tlt-1].strip()
						tlt = title.rfind('/')
						if -1 < tlt:
							title = title[:tlt-1].strip()
						tlt = title.rfind('|')
						if -1 < tlt:
							title = title[:tlt-1].strip()
						img   = item['thumbnail']
						time  = item['duration']
						added  = item['added']
						tempdesc  = item['description']
						tempdesc = tempdesc.replace('\n','')
						tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJxzS83JLEosyc6vOrywWCFRIbk4sSS/KO/wwqJEK4WMkpICK339pMwSvZxK/bDUqtTi4pAw3TS4nsRiAEWAGV4=')),'')
						tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJzLKCkpsNLXT8os0cup1A9LrUotLg4J001LzcksSizJzq9KLAYA5e8NQA==')),'')
						tempdesc = tempdesc.replace('(VEZESS TV ARCHÍV)','')
						tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJxzDQpx9XZydQ728XcIc41yDQ7W8wgFAENUBh8=')),'')
						tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJxLLSpJzU5KTS7OyXcoS61KLS7WyygFAF6UCH8=')),'')
						tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJwrS61KLS7Wyyh1SM9NzMzRS87PBQBLiQdj')),'')
						tempdesc = tempdesc.replace('IRATKOZZ FEL!:','')
						tempdesc = tempdesc.replace('HIBAJAVÍTÁS ITT:','')
						tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJwrS61KLS7WyygFABLlA6w=')),'')
						tlt = tempdesc.find('http')
						if -1 < tlt:
							tempdesc = tempdesc[:tlt-1].strip()
						tempdesc = tempdesc.strip()
						tempdesc = re.sub(r'^(.{400}).*$', '\g<1>...', tempdesc)
						if tempdesc == '':
							tempdesc = title_ere
						tempdesc = CParsingHelper.cleanHtmlStr(tempdesc)
						desc = added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
						params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'desc': desc, 'datum': added}
						break
					return params
				except Exception:
					return params
			else:
				return params
		else:
			return params
			
	def szovegki_asm(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'Nézd meg')
				bv = self.szovegkivetel(bv,'Nézz rá')
				bv = self.szovegkivetel(bv,'Kukk a')
				bv = self.szovegkivetel(bv,'Ilyen tesztvideókat')
				bv = self.szovegkivetel(bv,'Facebook')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_tc(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_ash(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_autonav(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_villany(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'Részletes cikk')
				bv = self.szovegkivetel(bv,'Videó:')
				bv = self.szovegkivetel(bv,'FB oldal:')
				bv = self.szovegkivetel(bv,'Facebook oldal:')
				bv = self.szovegkivetel(bv,'Epizód oldala:')
				bv = self.szovegkivetel(bv,'Csatlakozz hozzánk!')
				bv = self.szovegkivetel(bv,'Weboldal:')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_alapjarat(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'Weboldal:')
				bv = self.szovegkivetel(bv,'Még több infó:')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_bpiautosok(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_112press(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_speedzone(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_autobabbo(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Iratkozz fel')
				bv = self.szovegkivetel(bv,'Köszönjük')
				bv = self.szovegkivetel(bv,'IRATKOZZ FEL')
				bv = self.szovegkivetel(bv,'ÉS IRATKOZZ FEL')
				bv = self.szovegkivetel(bv,'NYOMJ EGY')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_fordrive(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_asr(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'Kövess Facebookon')
				bv = self.szovegkivetel(bv,'Kövess Instagramon')
				bv = self.szovegkivetel(bv,'Kövess minket Facebookon')
				bv = self.szovegkivetel(bv,'Támogass kérlek')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = re.sub(r'^(.{400}).*$', '\g<1>...', bv.strip())
			return bv
		except Exception:
			return ''
			
	def szovegki_hand(self, txt=''):
		bv = ''
		try:
			if txt != '':
				bv = txt
				bv = self.szovegkivetel(bv,'Még több vid')
				bv = self.szovegkivetel(bv,'Itt tudsz')
				bv = self.szovegkivetel(bv,'megte')
				bv = self.szovegkivetel(bv,'Ha a Tesla Univer')
				bv = self.szovegkivetel(bv,'Kövess Facebookon')
				bv = self.szovegkivetel(bv,'Kövess Instagramon')
				bv = self.szovegkivetel(bv,'Kövess minket Facebookon')
				bv = self.szovegkivetel(bv,'http')
				bv = self.szovegkivetel(bv,'https')
				bv = self.szovegkivetel(bv,'Támogass kérlek')
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
					bv = txt[:tlt-1].strip()
			return bv
		except Exception:
			return ''
			
	def Autogram_Legfrissebb(self):
		tabID = 'autogram'
		desc = ''
		params = dict()
		if self.tryTologin():
			url = self.MAIN_URL_AUTOGRAM
			sts, data = self.cm.getPage(self.SUBCATS_URL.format(url), self.apiParams)
			if not sts: return params
			if len(data) == 0: return params
			try:
				data = json_loads(data)
				subcats = data['program_subcats']
				if 0 == len(subcats): return params
				for i in subcats:
					subcat = str(i['id'])
					break
			except Exception:
				return params
			sts, data = self.cm.getPage(self.EPISODES_URL.format(url, subcat, 100, 0), self.apiParams)
			if not sts: return params
			if len(data) == 0: return params
			try:
				data = json_loads(data)
				for i in data:
					clips = i['clips']
					if 0 == len(clips): continue
					if 1 == len(clips):
						c = clips[0]
						url = c['video_id']
					else:
						continue
					title = c['title']
					desc = ''
					m = re.search(r'\d{4}-\d{2}-\d{2}',c['code'])
					if m is not None:
						desctemp = self.malvad('1', '1', url, title)
						desc = self.datum_honapos(m.group(0),'-') + '-i adás tartalma:\n\n' + desctemp
					icon_tmp = _getImageExtKey(c['images'], 'vignette')
					if icon_tmp is None:
						icon = self.DEFAULT_ICON_URL_AUTOGRAM
					else:
						icon = self.getFullIconUrl_Autogram('vj'+icon_tmp)
					params = {'good_for_fav': False, 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'tab_id': tabID}
					break
				return params
			except Exception:
				return params
		else:
			return params
		
	def Holvezes_Legfrissebb(self):
		bv = dict()
		uagnt = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0'
		phdre = {'User-Agent':uagnt, 'DNT':'1', 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate', 'Accept-Language':'hu-HU,hu;q=0.8,en-US;q=0.5,en;q=0.3', 'Host':'www.holvezessek.hu', 'Upgrade-Insecure-Requests':'1', 'Connection':'keep-alive', 'Content-Type':'application/x-www-form-urlencoded', 'Referer':'http://www.holvezessek.hu/galeria.html'}
		phdr = {'header':phdre, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}       
		try:
			uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1U9PzEktykzUyyjJzQEAGlgOkQ=='))
			pstd = {'filterSend':'1', 'modeV':'1'}
			sts, data = self.cm.getPage(uhe, phdr, pstd)
			if not sts: return bv
			if len(data) == 0: return bv
			data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, "<div class='listBlock listBlockvideo", "/script>")
			if len(data2) == 0: return bv
			for item in data2:
				title = self.cm.ph.getDataBeetwenMarkers(item, "<h1 style=", "/h1>")[1]
				if len(title) == 0: continue
				title = self.cleanHtmlStr(title).strip()
				icon_tmp = self.cm.ph.getDataBeetwenMarkers(item, "<img src=", "class='mainPic'/>")[1]
				icon = self.cm.ph.getSearchGroups(icon_tmp, '''src=['"]([^"^']+?)['"]''')[0]
				url_code = self.cm.ph.getSearchGroups(item, '''VideoCode\(['"]([^"^']+?)['"]''')[0]
				desc = self.cm.ph.getDataBeetwenMarkers(item, "</div>", "</td>", False)[1].replace('\n',' ').strip()
				bv = {'type': 'video', 'category': 'video', 'title': title, 'url': url_code, 'icon': icon, 'desc': desc, 'datum':''}
				break
			return bv
		except Exception:
			return bv
		
	def Garazs_Legfrissebb(self):
		tabID = 'garazs'
		params = dict()
		data = self.Garazs_data()
		if len(data) == 0: return params
		for item in data:
			musor_datuma = self.cm.ph.getDataBeetwenMarkers(item, '<span class="date" title="', '">', False)[1]
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
			title_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<a href="', '">')[1]
			title = self.cm.ph.getSearchGroups(title_tmp, '''title="([^"]+?)"''')[0]
			if title == '': continue
			desctemp = self.malvad('1', '2', url, title)
			desc = musor_datuma + '-i adás tartalma:\n\n' + desctemp
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			break
		return params
		
	def Supercar_Legfrissebb(self):
		tabID = 'supercar'
		params = dict()
		url = self.MAIN_URL_SUPERCAR_ADASOK
		sts, data = self.getPage(url)
		if not sts: return params
		if len(data) == 0: return params
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="flex_column av_two_third', '<div class="flex_column av_one_third')[1]
		if len(data) == 0: return params
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href=', '</a>')
		if len(data) == 0: return params
		for item in data:
			if not 'av-masonry-1-item' in item: continue
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'url[\'(]([^"^\']+?)[\')]')[0])
			title_tmp = self.cm.ph.getSearchGroups(item, '''title="([^"]+?)"''')[0]
			if not title_tmp.endswith('.'):
				title_tmp += '.'
			title = 'Supercar - ' + title_tmp
			desctemp = self.malvad('1', '3', url, title)
			desc = self.datum_honapos(title_tmp) + '-i adás tartalma:\n\n' + desctemp
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			break
		return params
		
	def Totalcar_Legfrissebb(self):
		params = dict()
		url = self.MAIN_URL_TOTALCAR
		sts, data = self.getPage(url)
		if not sts: return {}
		if len(data) == 0: return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="ajanlok"', '<div class="archivum">')[1]
		if len(data) == 0: return {}
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
		if len(data) == 0: return {}
		for item in data:
			tmp_i = self.cm.ph.getDataBeetwenMarkers(item, '<div class="img_wrapper"', '</div>')[1]
			if len(tmp_i) == 0: continue
			temp_u = self.cm.ph.getSearchGroups(tmp_i, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if not self.cm.isValidUrl(temp_u):
				continue
			icon = self.cm.ph.getSearchGroups(tmp_i, '''src=['"]([^"^']+?)['"]''')[0]
			if icon == '':
				icon = self.DEFAULT_ICON_URL_TOTALCAR
			temp_desc = self.cm.ph.getDataBeetwenMarkers(item, '<p class="ajanlo">', '</p>', False)[1]
			if len(temp_desc) == 0: continue
			temp_sts, tmp_da = self.getPage(temp_u)
			if not temp_sts: continue
			if len(tmp_da) == 0: continue
			temp_title = self.cm.ph.getDataBeetwenMarkers(tmp_da, '<h1 class="cim"><span>', '</span>', False)[1]
			if temp_title == '': continue
			temp_datum = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp_da, '<div class="datum">', '</span>', False)[1])
			if len(temp_datum) == 0: continue
			title = 'Totalcar - ' + temp_datum
			tmp_ttu = self.cm.ph.getDataBeetwenMarkers(tmp_da, '<div class="yt-video-container"', '</iframe>', False)[1]
			if len(tmp_ttu) == 0: continue
			url = self.cm.ph.getSearchGroups(tmp_ttu, '''src=['"]([^"^']+?)['"]''')[0]
			if not self.cm.isValidUrl(url):
				continue
			n_tc = self.malvadst('1', '1', url)
			if n_tc != '' and self.aid:
				self.aid_ki = 'ID: ' + n_tc + '\n'
			else:
				self.aid_ki = ''
			desc = self.aid_ki + temp_datum + '\n\nMűsor címe:  ' + temp_title + '\nTartalom:  ' + temp_desc
			tdatum = temp_datum[:11].replace('.','. ').strip()
			params = {'title':title, 'url':url, 'icon':icon, 'desc':desc, 'datum':tdatum}
			break
		return params
		
	def Forma1_Legfrissebb(self):
		tabID = 'forma1'
		params = dict()
		url = self.MAIN_URL_FORMA1
		sts, data = self.getPage(url)
		if not sts: return params
		if len(data) == 0: return params
		data = self.cm.ph.getDataBeetwenMarkers(data, '<a  href="/2011"', '</ul>')[1]
		if len(data) == 0: return params
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
		if len(data) == 0: return params
		for item in reversed(data):
			url = self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if url.startswith('/'):
				url = self.MAIN_URL_FORMA1 + url
			if not self.cm.isValidUrl(url):
				return params
			title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, "<a", "</a>")[1] )
			break
		url_citem = url
		title_citem = title
		sts, data = self.getPage(url_citem)
		if not sts: return params
		if len(data) == 0: return params
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="k2Container', '</section>')[1]
		if len(data) == 0: return params
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<span class="catItemImage"', '</span>')
		if len(data) == 0: return params
		for item in data:
			title_kieg = ''
			url_i = self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if url_i.startswith('/'):
				url_i = self.MAIN_URL_FORMA1 + url_i
			if not self.cm.isValidUrl(url_i):
				continue
			else:
				url, title_kieg = self.Forma1_ft(url_i)
				if title_kieg != '':
					title_kieg = ' - ' + title_kieg
			if not title_citem+'-r' in url_i: continue
			icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
			if icon.startswith('/'):
				icon = self.MAIN_URL_FORMA1 + icon
			title = 'Forma1 - ' + self.ekezetes_atalakitas(self.cm.ph.getSearchGroups(item, '''title="([^"]+?)"''')[0]) + title_kieg
			title = title.strip()
			desctemp = self.malvad('1', '4', url, title)
			desc = title + '\n\n' + desctemp
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			break
		return params
		
	def Veletlen_MainItems(self, cItem, tabID):
		url = cItem['url']
		try:
			self.susn('2', '1', url)
			musorList = []
			autogramList = self.Autogram_veletlen()
			if len(autogramList) > 0:
				for item in autogramList:
					musorList.append(item)
			garazsList = self.Garazs_veletlen()
			if len(garazsList) > 0:
				for item in garazsList:
					musorList.append(item)
			supercarList = self.Supercar_veletlen()
			if len(supercarList) > 0:
				for item in supercarList:
					musorList.append(item)        
			if len(musorList) > 0:
				random.shuffle(musorList)
				i = 1
				for item in musorList:
					i += 1
					if i > 20:
						break
					self.addVideo(item)
		except Exception:
			printExc()
				
	def Autogram_veletlen(self):
		tabID = 'autogram'
		desc = ''
		paramsList = []
		params = dict()
		if self.tryTologin():
			url = self.MAIN_URL_AUTOGRAM
			sts, data = self.cm.getPage(self.SUBCATS_URL.format(url), self.apiParams)
			if not sts: return paramsList
			if len(data) == 0: return paramsList
			try:
				data = json_loads(data)
				subcats = data['program_subcats']
				if 0 == len(subcats): return paramsList
				y = 1
				for item in subcats:
					subcat = str(item['id'])
					sts, data = self.cm.getPage(self.EPISODES_URL.format(url, subcat, 100, 0), self.apiParams)
					if not sts: return paramsList
					if len(data) == 0: return paramsList
					try:
						data = json_loads(data)
						for i in data:
							clips = i['clips']
							if 0 == len(clips): continue
							if 1 == len(clips):
								c = clips[0]
								url_ep = c['video_id']
							else:
								continue
							title = c['title']
							desc = ''
							m = re.search(r'\d{4}-\d{2}-\d{2}',c['code'])
							if m is not None:
								desctemp = self.malvad('1', '1', url_ep, title)
								desc = self.datum_honapos(m.group(0),'-') + '-i adás tartalma:\n\n' + desctemp
							icon_tmp = _getImageExtKey(c['images'], 'vignette')
							if icon_tmp is None:
								icon = self.DEFAULT_ICON_URL_AUTOGRAM
							else:
								icon = self.getFullIconUrl_Autogram('vj'+icon_tmp)
							params = {'good_for_fav': False, 'title': title, 'url': url_ep, 'icon': icon, 'desc': desc, 'tab_id': tabID}
							paramsList.append(params)
							y += 1
							if y > 30:
								break
					except Exception:
						printExc()
				return paramsList                        
			except Exception:
				printExc()
				return paramsList                
		else:
			return paramsList
				
	def Garazs_veletlen(self):
		tabID = 'garazs'
		paramsList = []
		params = dict()
		data = self.Garazs_data()
		if len(data) == 0: return paramsList
		i = 1
		for item in data:
			musor_datuma = self.cm.ph.getDataBeetwenMarkers(item, '<span class="date" title="', '">', False)[1]
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
			title_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<a href="', '">')[1]
			title = self.cm.ph.getSearchGroups(title_tmp, '''title="([^"]+?)"''')[0]
			if title == '': continue
			desctemp = self.malvad('1', '2', url, title)
			desc = musor_datuma + '-i adás tartalma:\n\n' + desctemp
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			paramsList.append(params)
			i += 1
			if i > 30:
				break
		return paramsList
		
	def Supercar_veletlen(self):
		tabID = 'supercar'
		paramsList = []
		params = dict()
		url = self.MAIN_URL_SUPERCAR_ADASOK
		sts, data = self.getPage(url)
		if not sts: return paramsList
		if len(data) == 0: return paramsList
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="flex_column av_two_third', '<div class="flex_column av_one_third')[1]
		if len(data) == 0: return paramsList
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href=', '</a>')
		if len(data) == 0: return paramsList
		i = 1
		for item in data:
			if not 'av-masonry-1-item' in item: continue
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'url[\'(]([^"^\']+?)[\')]')[0])
			title_tmp = self.cm.ph.getSearchGroups(item, '''title="([^"]+?)"''')[0]
			if not title_tmp.endswith('.'):
				title_tmp += '.'
			title = 'Supercar - ' + title_tmp
			desctemp = self.malvad('1', '3', url, title)
			desc = self.datum_honapos(title_tmp) + '-i adás tartalma:\n\n' + desctemp
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			paramsList.append(params)
			i += 1
			if i > 30:
				break
		return paramsList
	
	def Tipusok_MainItems(self, cItem, nextCategory, tabID):
		url = cItem['url']
		try:
			self.susn('2', '1', url)
		except Exception:
			printExc()
		return
	
	def Autogram_MainItems(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		if self.tryTologin():
			url = self.MAIN_URL_AUTOGRAM
			sts, data = self.cm.getPage(self.SUBCATS_URL.format(url), self.apiParams)
			if not sts: return
			if len(data) == 0: return
			try:
				data = json_loads(data)
				subcats = data['program_subcats']
				if 0 == len(subcats): return
				ln = 0
				for i in subcats:
					ln += 1
					title = i['title']
					subcat = str(i['id'])
					n_autogram = self.malvadst('1', '1', subcat)
					if n_autogram != '' and self.aid:
						self.aid_ki = 'ID: ' + n_autogram + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + '%s. év adásai' % title
					params = dict(cItem)
					params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url, 'subcat': subcat, 'desc': desc, 'tab_id': tabID, 'icon': self.DEFAULT_ICON_URL_AUTOGRAM})
					self.addDir(params)
					if ln >= 2: break
			except Exception: printExc()
		
	def Garazs_MainItems(self, cItem, nextCategory, tabID):
		url_susn = cItem['url']
		self.susn('2', '1', url_susn)
		datum_lista = []
		url_home = self.MAIN_URL_GARAZS_ADASOK
		data = self.Garazs_data()
		if len(data) == 0: return
		ln = 0
		for item in data:
			musor_datuma = self.cm.ph.getDataBeetwenMarkers(item, '<span class="date" title="', '">', False)[1]
			tmp_tomb = musor_datuma.split(' ')
			if len(tmp_tomb) < 2:
				continue
			else:
				ln += 1
				if not self.ev_e(self.cm.ph.getSearchGroups(tmp_tomb[0], '''([0-9]{4})''')[0],True): continue
				if not self.honapnev_e(tmp_tomb[1].strip()): continue
				if not tmp_tomb[0].endswith('.'):
					tmp_tomb[0] += '.'
				ev_honap = "%s %s" % (tmp_tomb[0], tmp_tomb[1])
				if (ev_honap in datum_lista) or (len(datum_lista) > 30):
					continue
				else:
					datum_lista.append(ev_honap)
				url = url_home
				if not self.cm.isValidUrl(url):
					continue
				icon = self.DEFAULT_ICON_URL_GARAZS
				title = ev_honap
				n_garazs = self.malvadst('1', '1', url+'/'+title)
				if n_garazs != '' and self.aid:
					self.aid_ki = 'ID: ' + n_garazs + '\n'
				else:
					self.aid_ki = ''
				desc = self.aid_ki + '%s havi adások' % title
				params = dict(cItem)
				params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
				params['category'] = nextCategory
				self.addDir(params)
				if ln > 15: break
		
	def Supercar_MainItems(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		sts, data = self.getPage(url)
		if not sts: return
		if len(data) == 0: return
		data = self.cm.ph.getDataBeetwenMarkers(data, "<h3 class='widgettitle'>Archív</h3><ul>", "</ul>")[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
		if len(data) == 0: return
		ln = 0
		for item in data:
			ln += 1
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			icon = self.DEFAULT_ICON_URL_SUPERCAR
			title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, "<a", "</a>")[1] )
			n_supercar = self.malvadst('1', '1', url)
			if n_supercar != '' and self.aid:
				self.aid_ki = 'ID: ' + n_supercar + '\n'
			else:
				self.aid_ki = ''
			desc = self.aid_ki + '%s havi adások' % title
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			params['category'] = nextCategory
			self.addDir(params)
			if ln > 15: break
		
	def getVAPList_vs(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					if 'vezess' not in item['author'].lower():
						continue
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					title_ere = title
					tlt = title.rfind('- ')
					if -1 < tlt:
						title = title[:tlt-1].strip()
					tlt = title.rfind('/')
					if -1 < tlt:
						title = title[:tlt-1].strip()
					tlt = title.rfind('|')
					if -1 < tlt:
						title = title[:tlt-1].strip()
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJxzS83JLEosyc6vOrywWCFRIbk4sSS/KO/wwqJEK4WMkpICK339pMwSvZxK/bDUqtTi4pAw3TS4nsRiAEWAGV4=')),'')
					tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJzLKCkpsNLXT8os0cup1A9LrUotLg4J001LzcksSizJzq9KLAYA5e8NQA==')),'')
					tempdesc = tempdesc.replace('(VEZESS TV ARCHÍV)','')
					tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJxzDQpx9XZydQ728XcIc41yDQ7W8wgFAENUBh8=')),'')
					tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJxLLSpJzU5KTS7OyXcoS61KLS7WyygFAF6UCH8=')),'')
					tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJwrS61KLS7Wyyh1SM9NzMzRS87PBQBLiQdj')),'')
					tempdesc = tempdesc.replace('IRATKOZZ FEL!:','')
					tempdesc = tempdesc.replace('HIBAJAVÍTÁS ITT:','')
					tempdesc = tempdesc.replace(zlib.decompress(base64.b64decode('eJwrS61KLS7WyygFABLlA6w=')),'')
					tlt = tempdesc.find('http')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tempdesc = tempdesc.strip()
					tempdesc = re.sub(r'^(.{400}).*$', '\g<1>...', tempdesc)
					if tempdesc == '':
						tempdesc = title_ere
					tempdesc = CParsingHelper.cleanHtmlStr(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_tc(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tlt = tempdesc.find('Még több vid')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('http')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tempdesc = tempdesc.strip()
					tempdesc = re.sub(r'^(.{400}).*$', '\g<1>...', tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_ash(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_ash(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_asm(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title']).replace('- AutóSámán','').strip()
					img   = item['thumbnail']
					time  = item['duration']
					#added  = item['added']
					date_time = datetime.fromtimestamp(item['time_created'])
					added = date_time.strftime("%Y.%m.%d.")
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_asm(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
		
	def getVAPList_asr(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_asr(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_villany(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_villany(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_autonav(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_autonav(tempdesc)
					if tempdesc == '':
						tempdesc = title
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_alapjarat(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title']).replace('| Alapjárat','').strip()
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_alapjarat(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_bpiautosok(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title']).strip()
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_bpiautosok(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_112press(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title']).strip()
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_112press(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_speedzone(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title']).replace('Speedzone teszt:','').replace('Speedzone-használt teszt:','').strip()
					title = title.replace('Újautó-teszt:','').strip()
					title = title.replace('Speedzone-gyorsteszt:','').strip()
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_speedzone(tempdesc)
					if tempdesc != '':
						tempdesc = tempdesc.replace('http://www.autohitel.hu','')
						tempdesc = tempdesc.replace('http://www.patreon.com/speedzone','')
						tempdesc = tempdesc.replace('http://patreon.com/speedzone','')
						tempdesc = tempdesc.replace('http://www.speedzoneshop.hu','')
						tempdesc = tempdesc.replace('http://www.sixst.hu','')
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_autobabbo(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title']).strip()
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_autobabbo(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_hand(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tlt = tempdesc.find('Még több vid')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('Itt tudsz')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('megte')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('Ha a Tesla Univer')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('Kövess Facebookon')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('Kövess Instagramon')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('Kövess minket Facebookon')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('http')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tlt = tempdesc.find('Támogass kérlek')
					if -1 < tlt:
						tempdesc = tempdesc[:tlt-1].strip()
					tempdesc = tempdesc.strip()
					tempdesc = re.sub(r'^(.{400}).*$', '\g<1>...', tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def getVAPList_fordrive(self, url, category, page, cItem, tabID):
		playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
		baseUrl = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9XPySwuiU/MSqywLy6pzEm1zSrOz1NLTC7JzM+LT08tiQfJ2xqqgSnVYgC/tBqx')) % playlistID
		currList = []
		if baseUrl != '':
			sts, data =  self.cm.getPage(baseUrl, {'host': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'})
			try:
				data = json_loads(data)['video']
				for item in data:
					url   = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v16vMLy0pTUrVS87P1S9PLEnOsC+zBQC7bgue')) + item['encrypted_id']
					title = CParsingHelper.cleanHtmlStr(item['title'])
					img   = item['thumbnail']
					time  = item['duration']
					added  = item['added']
					tempdesc  = item['description']
					tempdesc = tempdesc.replace('\n','')
					tempdesc = self.szovegki_fordrive(tempdesc)
					n_de = self.malvadst('1', '1', url)
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '\n'
					else:
						self.aid_ki = ''
					desc = self.aid_ki + added + '  |  Időtartatm:  ' + time + '\n\nTartalom:\n' + tempdesc
					params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': added, 'desc': desc, 'tab_id':tabID}
					currList.append(params)
			except Exception:
				printExc()
		if len(currList) != '':        
			currList = sorted(currList, key=lambda i: (i['time'], i['title']))       
			return reversed(currList)
		else:
			return []
			
	def Ytpl_lista(self, cItem, tabID, mk='vs'):
		llst = []
		templlst = []
		ln = 0
		category = 'playlist'
		url = cItem['plurl']
		page = '1'
		self.susn('2', '1', cItem['url'])
		params = dict(cItem)
		try:
			if url != '' and tabID != '':
				if mk == 'vs':
					llst = self.getVAPList_vs(url, category, page, params, tabID)
				if mk == 'tc':
					llst = self.getVAPList_tc(url, category, page, params, tabID)
				if mk == 'ash':
					llst = self.getVAPList_ash(url, category, page, params, tabID)
				if mk == 'asm':
					llst = self.getVAPList_asm(url, category, page, params, tabID)
				if mk == 'asr':
					llst = self.getVAPList_asr(url, category, page, params, tabID)
				if mk == 'autonav':
					llst = self.getVAPList_autonav(url, category, page, params, tabID)
				if mk == 'villany':
					llst = self.getVAPList_villany(url, category, page, params, tabID)
				if mk == 'alapjarat':
					llst = self.getVAPList_alapjarat(url, category, page, params, tabID)
				if mk == 'bpiautosok':
					llst = self.getVAPList_bpiautosok(url, category, page, params, tabID)
				if mk == '112press':
					llst = self.getVAPList_112press(url, category, page, params, tabID)
				if mk == 'speedzone':
					llst = self.getVAPList_speedzone(url, category, page, params, tabID)
				if mk == 'autobabbo':
					llst = self.getVAPList_autobabbo(url, category, page, params, tabID)
				if mk == 'hand':
					llst = self.getVAPList_hand(url, category, page, params, tabID)
				if mk == 'fordrive':
					llst = self.getVAPList_fordrive(url, category, page, params, tabID)
				for item in llst:
					templlst.append(item)
					ln += 1
					if ln > 150: break
			self.currList = templlst
		except Exception:
			self.currList = []
		
	def Handras_lista(self, cItem, nextCategory, tabID):
		llst = []
		category = 'channel'
		url = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvLU4t0vdIzEspSiwGAP2vDbc='))
		page = '1'
		self.susn('2', '1', cItem['url'])
		if -1 == url.find('browse_ajax'):
			if url.endswith('/videos'): 
				url = url + '?flow=list&view=0&sort=dd'
			else:
				url = url + '/videos?flow=list&view=0&sort=dd'
		params = dict(cItem)
		llst = self.ytp.getVideosFromChannelList(url, category, page, params)
		for idx in range(len(llst)):
			if llst[idx].get('type', '') == 'video':
				llst[idx]['good_for_fav'] = False
				llst[idx]['tab_id'] = tabID
			if llst[idx].get('page', '') != '':
				llst.remove(llst[idx])
				continue
			tt = llst[idx].get('title', '')
			llst[idx]['title'] = tt
			tdsc = llst[idx].get('desc', '')
			if tdsc != '':
				tlt = tdsc.find('[/br]')
				if -1 < tlt:
					tls1 = tdsc[:tlt]
					tls2 = tdsc[tlt+5:]
				else:
					tls1 = tdsc
					tls2 = ''
				if tls1 != '':
					tlt = tls1.find('megte')
					if -1 < tlt:
						tls1 = tls1[:tlt-1].strip()
						tlt = tls1.rfind(' ')
						if -1 < tlt:
							tls1 = tls1[:tlt].strip()
				if tls2 != '':
					tlt = tls2.find('Itt tudsz')
					if -1 < tlt:
						tls2 = tls2[:tlt-1].strip()
					tlt = tls2.find('https')
					if -1 < tlt:
						tls2 = tls2[:tlt-1].strip()
					tlt = tls2.find('http')
					if -1 < tlt:
						tls2 = tls2[:tlt-1].strip()
				else:
					tls2 = tt
				if tls1 == '' and tls2 == '':
					continue
				if tls1 != '':
					n_de = self.malvadst('1', '1', llst[idx].get('url', ''))
					if n_de != '' and self.aid:
						self.aid_ki = 'ID: ' + n_de + '  |  ' + tls1
					else:
						self.aid_ki = tls1
					desc_de = self.aid_ki + '\n\nTartalom:\n' + tls2
					llst[idx]['desc'] = desc_de
		self.currList = llst
			
	def Totalcar_MainItems(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		sts, data = self.getPage(url)
		if not sts: return
		if len(data) == 0: return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="ajanlok"', '<div class="archivum">')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
		if len(data) == 0: return
		ln = 0
		for item in data:
			tmp_i = self.cm.ph.getDataBeetwenMarkers(item, '<div class="img_wrapper"', '</div>')[1]
			if len(tmp_i) == 0: continue
			temp_u = self.cm.ph.getSearchGroups(tmp_i, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if not self.cm.isValidUrl(temp_u):
				continue
			icon = self.cm.ph.getSearchGroups(tmp_i, '''src=['"]([^"^']+?)['"]''')[0]
			if icon == '':
				icon = self.DEFAULT_ICON_URL_TOTALCAR
			temp_desc = self.cm.ph.getDataBeetwenMarkers(item, '<p class="ajanlo">', '</p>', False)[1]
			if len(temp_desc) == 0: continue
			temp_sts, tmp_da = self.getPage(temp_u)
			if not temp_sts: continue
			if len(tmp_da) == 0: continue
			title = self.cm.ph.getDataBeetwenMarkers(tmp_da, '<h1 class="cim"><span>', '</span>', False)[1]
			if title == '': continue
			temp_datum = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp_da, '<div class="datum">', '</span>', False)[1])
			if len(temp_datum) == 0: continue
			tmp_ttu = self.cm.ph.getDataBeetwenMarkers(tmp_da, '<div class="yt-video-container"', '</iframe>', False)[1]
			if len(tmp_ttu) == 0: continue
			url = self.cm.ph.getSearchGroups(tmp_ttu, '''src=['"]([^"^']+?)['"]''')[0]
			if not self.cm.isValidUrl(url):
				continue
			n_tc = self.malvadst('1', '1', url)
			if n_tc != '' and self.aid:
				self.aid_ki = 'ID: ' + n_tc + '\n'
			else:
				self.aid_ki = ''
			desc = self.aid_ki + temp_datum + '\n\n' + temp_desc
			ln += 1
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			self.addVideo(params)
			if ln > 30: break
			
	def Holvezes_MainItems(self, cItem, nextCategory, tabID):
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1U9PzEktykzUyyjJzQEAGlgOkQ=='))
		try:
			url_temp = cItem['url']
			self.susn('2', '1', url_temp)
			sts, data = self.getPage(uhe)
			if not sts: return
			if len(data) == 0: return
			data = self.cm.ph.getDataBeetwenMarkers(data, "<select name='yearG'", "/select>")[1]
			if len(data) == 0: return
			data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option value=', '/option>')
			if len(data) == 0: return
			ln = 0
			i = 1
			for item in reversed(data):
				title = self.cleanHtmlStr(item)
				if title == '': continue
				url = title
				icon = self.DEFAULT_ICON_URL_HOLVEZES
				n_holvez = self.malvadst('1', '1', zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1QcAhXwJ2Q==')) + url)   
				if n_holvez != '' and self.aid:
					self.aid_ki = 'ID: ' + n_holvez + '\n'
				else:
					self.aid_ki = ''
				desc = self.aid_ki + '%s. évad adásai' % title
				params = dict(cItem)
				params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
				params['category'] = nextCategory
				self.addDir(params)
				i += 1
				if i > 4: break
		except Exception:
			return
			
	def Holvezes_Episodes(self, cItem, tabID):
		uagnt = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0'
		phdre = {'User-Agent':uagnt, 'DNT':'1', 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate', 'Accept-Language':'hu-HU,hu;q=0.8,en-US;q=0.5,en;q=0.3', 'Host':'www.holvezessek.hu', 'Upgrade-Insecure-Requests':'1', 'Connection':'keep-alive', 'Content-Type':'application/x-www-form-urlencoded', 'Referer':'http://www.holvezessek.hu/galeria.html'}
		phdr = {'header':phdre, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}       
		try:
			url = cItem['url']
			if url != '':
				self.susn('2', '1', zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1QcAhXwJ2Q==')) + url)
			uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1U9PzEktykzUyyjJzQEAGlgOkQ=='))
			uhe2 = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1U9PzEktykzUyyjJzbHPz0lJzLE1AgCb0RFL'))
			pstd = {'filterSend':'1', 'modeV':'1', 'yearG':url}
			sts, data = self.cm.getPage(uhe, phdr, pstd)
			if not sts: return
			if len(data) == 0: return
			data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, "<div class='listBlock listBlockvideo", "/script>")
			if len(data2) == 0: return
			for item in data2:
				title = self.cm.ph.getDataBeetwenMarkers(item, "<h1 style=", "/h1>")[1]
				if len(title) == 0: continue
				title = self.cleanHtmlStr(title).strip()
				icon_tmp = self.cm.ph.getDataBeetwenMarkers(item, "<img src=", "class='mainPic'/>")[1]
				icon = self.cm.ph.getSearchGroups(icon_tmp, '''src=['"]([^"^']+?)['"]''')[0]
				url_code = self.cm.ph.getSearchGroups(item, '''VideoCode\(['"]([^"^']+?)['"]''')[0]
				temp_desc = self.cm.ph.getDataBeetwenMarkers(item, "</div>", "</td>", False)[1].replace('\n',' ').strip()
				n_hv = self.malvadst('1', '1', zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1QcAhXwJ2Q==')) + url_code)
				if n_hv != '' and self.aid:
					self.aid_ki = 'ID: ' + n_hv + '\n\n'
				else:
					self.aid_ki = ''
				desc = self.aid_ki + temp_desc
				params = MergeDicts(cItem, {'good_for_fav': False, 'title':title, 'url':url_code, 'icon':icon, 'desc':desc, 'tab_id':tabID})
				self.addVideo(params)
			kvld = self.cm.ph.getDataBeetwenMarkers(data, "<span class='distancePage'>", "</span>")[1]    
			if kvld != '':    
				sts3, data3 = self.cm.getPage(uhe2, phdr)
				if len(data3) > 0:
					data4 = self.cm.ph.getAllItemsBeetwenMarkers(data3, "<div class='listBlock listBlockvideo", "/script>")
					if len(data4) > 0:
						for item4 in data4:
							title4 = self.cm.ph.getDataBeetwenMarkers(item4, "<h1 style=", "/h1>")[1]
							if len(title4) == 0: continue
							title4 = self.cleanHtmlStr(title4).strip()
							icon_tmp4 = self.cm.ph.getDataBeetwenMarkers(item4, "<img src=", "class='mainPic'/>")[1]
							icon4 = self.cm.ph.getSearchGroups(icon_tmp4, '''src=['"]([^"^']+?)['"]''')[0]
							url_code4 = self.cm.ph.getSearchGroups(item4, '''VideoCode\(['"]([^"^']+?)['"]''')[0]
							temp_desc4 = self.cm.ph.getDataBeetwenMarkers(item4, "</div>", "</td>", False)[1].replace('\n',' ').strip()
							n_hv = self.malvadst('1', '1', zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1QcAhXwJ2Q==')) + url_code4)
							if n_hv != '' and self.aid:
								self.aid_ki = 'ID: ' + n_hv + '\n\n'
							else:
								self.aid_ki = ''
							desc4 = self.aid_ki + temp_desc4
							params = MergeDicts(cItem, {'good_for_fav': False, 'title':title4, 'url':url_code4, 'icon':icon4, 'desc':desc4, 'tab_id':tabID})
							self.addVideo(params)
		except Exception:
			return
			
	def Forma1_MainItems(self, cItem, nextCategory, tabID):
		url = cItem['url']
		self.susn('2', '1', url)
		sts, data = self.getPage(url)
		if not sts: return
		if len(data) == 0: return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<a  href="/2011"', '</ul>')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
		if len(data) == 0: return
		i = 1
		for item in reversed(data):
			url = self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if url.startswith('/'):
				url = self.MAIN_URL_FORMA1 + url
			if not self.cm.isValidUrl(url):
				continue
			icon = self.DEFAULT_ICON_URL_FORMA1
			title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, "<a", "</a>")[1] )
			n_forma1 = self.malvadst('1', '1', url)
			if n_forma1 != '' and self.aid:
				self.aid_ki = 'ID: ' + n_forma1 + '\n'
			else:
				self.aid_ki = ''
			desc = self.aid_ki + '%s. évad futamai' % title
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			params['category'] = nextCategory
			self.addDir(params)
			i += 1
			if i > 2: break
		url_forma1_hatra = self.MAIN_URL_FORMA1_VERSENYNAPTAR
		desc_forma1_hatra = self.getdvdsz('forma1_naptar', 'Hátralévő versenyek az aktuális évben...')
		params = dict(cItem)
		params = {'good_for_fav': False, 'category':nextCategory, 'title':'Hátralévő versenyek', 'url':url_forma1_hatra, 'icon': self.DEFAULT_ICON_URL_FORMA1, 'desc':desc_forma1_hatra, 'tab_id':'forma1_naptar'}
		self.addDir(params)
		url_forma1_pont = self.MAIN_URL_FORMA1_PONTVERSENY
		desc_forma1_pont = self.getdvdsz('forma1_pontverseny', 'Az aktuális év pontversenye. Versenyzői és konstruktőri bajnokság állása...')
		params = dict(cItem)
		params = {'good_for_fav': False, 'category':nextCategory, 'title':'Pontverseny', 'url':url_forma1_pont, 'icon': self.DEFAULT_ICON_URL_FORMA1, 'desc':desc_forma1_pont, 'tab_id':'forma1_pontverseny'}
		self.addDir(params)
		url_forma1_ered = self.MAIN_URL_FORMA1_VERSENYNAPTAR
		desc_forma1_ered = self.getdvdsz('forma1_eredmeny', 'Az aktuális év lezajlott futamjainak eredményei...')
		params = dict(cItem)
		params = {'good_for_fav': False, 'category':nextCategory, 'title':'Eredmények', 'url':url_forma1_ered, 'icon': self.DEFAULT_ICON_URL_FORMA1, 'desc':desc_forma1_ered, 'tab_id':'forma1_eredmeny'}
		self.addDir(params)
			
	def listEpisodes(self, cItem, nextCategory):
		try:
			tabID = cItem.get('tab_id', '')
			if tabID == 'autogram':
				self.Autogram_Episodes(cItem, tabID)
			elif tabID == 'garazs':
				self.Garazs_Episodes(cItem, tabID)
			elif tabID == 'supercar':
				self.Supercar_Episodes(cItem, tabID)
			elif tabID == 'holvezes':
				self.Holvezes_Episodes(cItem, tabID)
			elif tabID == 'forma1':
				self.Forma1_Episodes(cItem, tabID)
			elif tabID == 'forma1_naptar':
				self.Forma1_versenynaptar(cItem, tabID)
			elif tabID == 'forma1_pontverseny':
				self.Forma1_pontverseny(cItem, nextCategory, tabID)
			elif tabID == 'forma1_eredmeny':
				self.Forma1_eredmeny(cItem, tabID)
			else:
				return
		except Exception:
			printExc()
			
	def Autogram_Episodes(self, cItem, tabID):
		url = cItem['url']
		subcat = cItem['subcat']
		self.susn('2', '1', subcat)
		sts, data = self.cm.getPage(self.EPISODES_URL.format(url, subcat, 100, 0), self.apiParams)
		if not sts: return
		if len(data) == 0: return
		try:
			data = json_loads(data)
			for i in data:
				clips = i['clips']
				if 0 == len(clips): continue
				if 1 == len(clips):
					c = clips[0]
					isVideo = True
					url = c['video_id']
				else:
					continue
				title = c['title']
				desc = ''
				m = re.search(r'\d{4}-\d{2}-\d{2}',c['code'])
				if m is not None:
					desctemp = self.malvad('1', '1', url, title)
					desc = self.datum_honapos(m.group(0),'-') + '-i adás tartalma:\n\n' + desctemp
				icon_tmp = _getImageExtKey(c['images'], 'vignette')
				params = dict(cItem)
				params.pop('subcat',None)
				if icon_tmp is None:
					icon = self.DEFAULT_ICON_URL_AUTOGRAM
				else:
					icon = self.getFullIconUrl_Autogram('vj'+icon_tmp)
				params.update({'good_for_fav':False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID})
				self.addVideo(params)
		except Exception:
			printExc()
			return
		
	def Garazs_Episodes(self, cItem, tabID):
		url_home = self.MAIN_URL_GARAZS_ADASOK
		datum_szoveg = cItem['title']
		url_sata = cItem['url']
		self.susn('2', '1', url_sata+'/'+datum_szoveg)
		data = self.Garazs_data()
		if len(data) == 0: return
		for item in data:
			musor_datuma = self.cm.ph.getDataBeetwenMarkers(item, '<span class="date" title="', '">', False)[1]
			if not datum_szoveg in musor_datuma: continue
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
			title_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<a href="', '">')[1]
			title = self.cm.ph.getSearchGroups(title_tmp, '''title="([^"]+?)"''')[0]
			if title == '': continue
			desctemp = self.malvad('1', '2', url, title)
			desc = musor_datuma + '-i adás tartalma:\n\n' + desctemp
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			self.addVideo(params)
		
	def Supercar_Episodes(self, cItem, tabID):
		datum_szoveg = cItem['title']
		url_sata = cItem['url']
		self.susn('2', '1', url_sata)
		datum_szoveg = self.datum_converter(datum_szoveg, '-')
		url = self.MAIN_URL_SUPERCAR_ADASOK
		sts, data = self.getPage(url)
		if not sts: return
		if len(data) == 0: return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="flex_column av_two_third', '<div class="flex_column av_one_third')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href=', '</a>')
		for item in data:
			if not 'av-masonry-1-item' in item: continue
			url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
			if not self.cm.isValidUrl(url):
				continue
			if not datum_szoveg in url: continue
			icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'url[\'(]([^"^\']+?)[\')]')[0])
			title_tmp = self.cm.ph.getSearchGroups(item, '''title="([^"]+?)"''')[0]
			if not title_tmp.endswith('.'):
				title_tmp += '.'
			title = 'Supercar - ' + title_tmp
			desctemp = self.malvad('1', '3', url, title)
			desc = self.datum_honapos(title_tmp) + '-i adás tartalma:\n\n' + desctemp
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			self.addVideo(params)
			
	def Forma1_Episodes(self, cItem, tabID):
		title_kieg = ''
		url_citem = cItem['url']
		self.susn('2', '1', url_citem)
		title_citem = cItem['title']
		sts, data = self.getPage(url_citem)
		if not sts: return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="k2Container', '</section>')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<span class="catItemImage"', '</span>')
		if len(data) == 0: return
		for item in data:
			url_i = self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if url_i.startswith('/'):
				url_i = self.MAIN_URL_FORMA1 + url_i
			if not self.cm.isValidUrl(url_i):
				continue
			else:
				url, title_kieg = self.Forma1_ft(url_i)
				if title_kieg != '':
					title_kieg = ' - ' + title_kieg
			#if not url_citem in url: continue
			if not title_citem+'-r' in url_i: continue
			icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
			if icon.startswith('/'):
				icon = self.MAIN_URL_FORMA1 + icon
			title = self.ekezetes_atalakitas(self.cm.ph.getSearchGroups(item, '''title="([^"]+?)"''')[0]) + title_kieg
			title = title.strip()
			desctemp = self.malvad('1', '4', url, title)
			desc = title + '\n\n' + desctemp
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'tab_id':tabID}
			self.addVideo(params)
			
	def Forma1_ft(self, pu):
		bu = ''
		btk = ''
		tvb = False
		try:
			if pu != '':
				sts, data_tmp = self.getPage(pu)
				if not sts: return '',''
				if data_tmp == '': return '',''
				data = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<a id="anchor-futam', '</iframe>')[1]
				if data != '':
					tvb = True
				if not tvb:
					data = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<a id="anchor-idomero-edzes', '</iframe>')[1]
					if data != '':
						tvb = True
						btk = 'időmérőedzés'
				if not tvb:
					data = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<a id="anchor-3-szabadedzes', '</iframe>')[1]
					if data != '':
						tvb = True
						btk = '3. szabadedzés'
				if not tvb:
					data = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<a id="anchor-2-szabadedzes', '</iframe>')[1]
					if data != '':
						tvb = True
						btk = '2. szabadedzés'
				if not tvb:
					data = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<a id="anchor-1-szabadedzes', '</iframe>')[1]
					if data != '':
						tvb = True
						btk = '1. szabadedzés'
				if data == '': return '',''
				url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''')[0]
				if url == '': return '',''
				if url.startswith('//'):
					url = 'https:' + url
				bu = url
				return bu, btk
		except Exception:
			return '',''
		return bu, btk
			
	def Forma1_versenynaptar(self, cItem, tabID):
		url_citem = cItem['url']
		tabid_citem = cItem['tab_id']
		self.susn('2', '1', tabid_citem)
		sts, data = self.getPage(url_citem)
		if not sts: return
		if len(data) == '': return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="F1-RaceSelectorList"', '<div class="F1-raceSelectorMobil">')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href="javascript:void(0);"', '</a>')
		for item in data:
			url = self.cm.ph.getSearchGroups(item, '''data-target_url=[\'"]([^"^\']+?)[\'"]''')[0]
			if url.startswith('//'):
				url = 'https:' + url
			if not url.startswith('https'):
				continue
			if not self.cm.isValidUrl(url):
				continue
			currentYear = str(datetime.now().year)
			datum_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<div class="raceDate"', '</div>')[1]
			datum_string = currentYear + '. ' +self.cm.ph.getDataBeetwenMarkers(datum_tmp, '<span>', '</span>', False)[1]
			datum = datetime.strptime(self.datum_from_honapos(datum_string), "%Y-%m-%d").date()
			akt_datum = datetime.now().date()
			if datum >= akt_datum:
				hely_city = self.cm.ph.getDataBeetwenMarkers(item, 'class="F1-raceCity">', '</span>', False)[1]
				hely_country = self.cm.ph.getDataBeetwenMarkers(item, 'class="F1-raceCountry">', '</span>', False)[1]
				title = self.datum_from_honapos(datum_string) + '  -  ' + hely_city + ' (' + hely_country +')'
				icon = self.DEFAULT_ICON_URL_FORMA1
				desc = 'Futam időpontja:  ' + datum_string + '\nFutam helyszine:  ' + hely_city + ' (' + hely_country +')\n\n\nTovábbi információkért nyomd meg az OK gombot a távirányítón!'
				params = dict(cItem)
				params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'art_id':'forma1_hatralevo', 'type':'article'}
				self.addArticle(params)
				
	def Forma1_pontverseny(self, cItem, nextCategory, tabID):
		self.susn('2', '1', 'forma1_pontverseny')
		desc_ev = self.getdvdsz('auto_f1_egyeni_verseny', 'Versenyzői bajnokság...')
		desc_csv = self.getdvdsz('auto_f1_csapat_verseny', 'Konstruktőri bajnokság...')
		PV_CAT_TAB = [{'category':nextCategory, 'title': 'Versenyzői bajnokság', 'tab_id': 'f1_egyeni_verseny', 'desc': desc_ev},
					  {'category':nextCategory, 'title': 'Konstruktőri bajnokság', 'tab_id': 'f1_csapat_verseny', 'desc': desc_csv}                        
					 ]
		self.listsTab(PV_CAT_TAB, cItem)
		
	def Forma1_eredmeny(self, cItem, tabID):
		url_citem = cItem['url']
		tabid_citem = cItem['tab_id']
		self.susn('2', '1', 'forma1_eredmeny')
		sts, data = self.getPage(url_citem)
		if not sts: return
		if len(data) == '': return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="F1-RaceSelectorList"', '<div class="F1-raceSelectorMobil">')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href="javascript:void(0);"', '</a>')
		if len(data) == 0: return
		for item in reversed(data):
			url = self.cm.ph.getSearchGroups(item, '''data-target_url=[\'"]([^"^\']+?)[\'"]''')[0]
			if url.startswith('//'):
				url = 'https:' + url
			if not url.startswith('https'):
				continue
			if not self.cm.isValidUrl(url):
				continue
			currentYear = str(datetime.now().year)
			datum_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<div class="raceDate"', '</div>')[1]
			datum_string = currentYear + '. ' +self.cm.ph.getDataBeetwenMarkers(datum_tmp, '<span>', '</span>', False)[1]
			datum = datetime.strptime(self.datum_from_honapos(datum_string), "%Y-%m-%d").date()
			akt_datum = datetime.now().date()
			if datum < akt_datum:
				ems, biu = self.emselo(url)
				hely_city = self.cm.ph.getDataBeetwenMarkers(item, 'class="F1-raceCity">', '</span>', False)[1]
				hely_country = self.cm.ph.getDataBeetwenMarkers(item, 'class="F1-raceCountry">', '</span>', False)[1]
				title = self.datum_from_honapos(datum_string) + '  -  ' + hely_city + ' (' + hely_country +')'
				icon = biu
				desc = 'Futam:  ' + datum_string + '  |  ' + hely_city + ' (' + hely_country +')\n\nEredmény:\n' + ems
				params = dict(cItem)
				params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'art_id':'forma1_hatralevo', 'type':'article'}
				self.addArticle(params)
				
	def emselo(self, url):
		bvs = ''
		biu = self.DEFAULT_ICON_URL_FORMA1
		ln = 0
		try:
			if url != '':
				sts, data = self.getPage(url)
				if not sts: return bvs, biu
				if len(data) == '': return bvs, biu
				imdata = self.cm.ph.getDataBeetwenMarkers(data, '<div class="gpName"', '<div class="gpTimetable">')[1]
				image_url = self.cm.ph.getSearchGroups(imdata, '''src=[\'"]([^"^\']+?)[\'"]''')[0]
				if image_url != '':
					if image_url.startswith('//'):
						image_url = 'https:' + image_url
					if not image_url.startswith('https'):
						image_url = self.DEFAULT_ICON_URL_FORMA1
				else:
					image_url = self.DEFAULT_ICON_URL_FORMA1
				biu = image_url
				data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="raceResultsTable finish active" data-tab_id="1"', '<div class="raceResultsTable practice"')[1]
				if len(data) == 0: return bvs, biu
				data =  self.cm.ph.getAllItemsBeetwenNodes(data, ('<div class=', '>', 'line'), ('<div class="wcPoints"', '</div>'))
				if len(data) == 0: return bvs, biu
				for item in data:
					poz = self.cm.ph.getDataBeetwenMarkers(item, '<div class="position">', '</div>', False)[1]
					if len(poz) == 0: continue
					nev = self.cm.ph.getDataBeetwenMarkers(item, '<span class="pilotNameLong">', '</span>', False)[1]
					if len(nev) == 0: continue
					pont = self.cm.ph.getDataBeetwenMarkers(item, '<div class="wcPoints">', '</div>', False)[1]
					if len(pont) == 0: continue
					ln += 1
					if ln == 1:
						tmp = poz + ' - ' + nev + '  (' + pont + ' pont)'
					else:
						tmp = ',   ' + poz + ' - ' + nev + '  (' + pont + ' pont)'
					bvs = bvs + tmp
			return bvs, biu
		except Exception:
			return '', self.DEFAULT_ICON_URL_FORMA1
		
	def listThird(self, cItem):
		try:
			tabID = cItem.get('tab_id', '')
			if tabID == 'f1_egyeni_verseny':
				self.Ltev(cItem, tabID)
			elif tabID == 'f1_csapat_verseny':
				self.Ltcsv(cItem, tabID)
			elif tabID in ['vezess_matksz','vezess_ertekb','vezess_aszaloncs','vezess_ojkogm','vezess_bgtgml','vezess_htank','vezess_haaktink','vezess_trahvzs']:
				self.Ytpl_lista(cItem, tabID, 'vs')
			elif tabID in ['total_trtk', 'total_mlypn', 'total_treo', 'total_tlbk', 'total_szjsn', 'total_trmks', 'total_uzk', 'total_tlac']:
				self.Ytpl_lista(cItem, tabID, 'tc')
			else:
				return
		except Exception:
			printExc()
			
	def Ltev(self, cItem, tabID):
		url = ''
		self.susn('2', '1', 'auto_f1_egyeni_verseny')
		sts, data = self.getPage(self.MAIN_URL_FORMA1_PONTVERSENY)
		if not sts: return
		if len(data) == '': return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pilotStandings"', '<div class="teamStandings">')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
		if len(data) == 0: return
		for item in data:
			poz = self.cm.ph.getDataBeetwenMarkers(item, '<td class="position"><span>', '</span></td>', False)[1]
			if len(poz) == 0: continue
			nev = self.cm.ph.getDataBeetwenMarkers(item, '<span class="pilotNameLong">', '</span>', False)[1]
			if len(nev) == 0: continue
			csapat = self.cm.ph.getDataBeetwenMarkers(item, '<span class="pilotTeamLong">', '</span>', False)[1]
			if len(csapat) == 0: continue
			pont = self.cm.ph.getDataBeetwenMarkers(item, '<td class="points"><span>', '</span>', False)[1]
			if len(pont) == 0: continue
			nev_url_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<td class="pilotName">', '</td>', False)[1]
			nev_url = self.cm.ph.getSearchGroups(nev_url_tmp, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if nev_url != '':
				if nev_url.startswith('//'):
					nev_url = 'https:' + nev_url
			if not self.cm.isValidUrl(nev_url):
				continue
			icon = self.Ltev_i(nev_url,self.kfvk)
			if icon == '':
				icon = self.DEFAULT_ICON_URL_FORMA1
			title = poz + '. hely  -  ' + nev + '  (' + csapat + ')  -  ' + pont + ' pont'
			desc = 'Helyezés:\n' + title
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'type':'article'}
			self.addArticle(params)
			
	def Ltev_i(self, nu='', eu=''):
		icon = self.DEFAULT_ICON_URL_FORMA1
		try:
			if nu != '' and eu != '':
				tlt = nu.find('=')
				if -1 < tlt:
					ti = eu + nu[tlt+1:].replace('ü','u') + '.jpg'
					if self.cm.isValidUrl(ti):
						icon = ti
			return icon
		except Exception:
			return self.DEFAULT_ICON_URL_FORMA1
		
	def Ltcsv(self, cItem, tabID):
		icon = self.DEFAULT_ICON_URL_FORMA1
		url = ''
		self.susn('2', '1', 'auto_f1_csapat_verseny')
		sts, data = self.getPage(self.MAIN_URL_FORMA1_PONTVERSENY)
		if not sts: return
		if len(data) == '': return
		data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="teamStandings"', '<div class="clearFix">')[1]
		if len(data) == 0: return
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
		if len(data) == 0: return
		for item in data:
			poz = self.cm.ph.getDataBeetwenMarkers(item, '<td class="position"><span>', '</span></td>', False)[1]
			if len(poz) == 0: continue
			csapat = self.cm.ph.getDataBeetwenMarkers(item, '<span class="teamNameLong">', '</span>', False)[1]
			if len(csapat) == 0: continue
			pont = self.cm.ph.getDataBeetwenMarkers(item, '<td class="points"><span>', '</span>', False)[1]
			if len(pont) == 0: continue
			nev_url_tmp = self.cm.ph.getDataBeetwenMarkers(item, '<td class="teamName">', '</td>', False)[1]
			nev_url = self.cm.ph.getSearchGroups(nev_url_tmp, 'href=[\'"]([^"^\']+?)[\'"]')[0]
			if nev_url != '':
				if nev_url.startswith('//'):
					nev_url = 'https:' + nev_url
			if not self.cm.isValidUrl(nev_url):
				continue
			icon = self.Ltev_i(nev_url,self.kfvcsk)
			if icon == '':
				icon = self.DEFAULT_ICON_URL_FORMA1
			title = poz + '. hely  -  ' + csapat + '  -  ' + pont + ' pont'
			desc = 'Helyezés:\n' + title
			params = dict(cItem)
			params = {'good_for_fav': False, 'title':title, 'url':url, 'icon':icon, 'desc':desc, 'type':'article'}
			self.addArticle(params)
			
	def getArticleContent(self, cItem):
		try:
			artID = cItem.get('art_id', '')
			if artID == 'forma1_hatralevo':
				return self.Forma1_hatralevo_getArticleContent(cItem)
			elif artID == 'foinformacio':
				return self.fgtac(cItem)
			else:
				return []
		except Exception:
			printExc()
			
	def Forma1_hatralevo_getArticleContent(self, cItem):
		try:
			url_citem = cItem['url']
			title_citem = cItem['title']
			sts, data = self.getPage(url_citem)
			if not sts: return []
			if len(data) == '': return []
			data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="gpName"', '<div class="gpTimetable">')[1]
			palya_neve = self.cm.ph.getDataBeetwenMarkers(data, '<h2>', '</h2>', False)[1]
			image_url = self.cm.ph.getSearchGroups(data, '''src=[\'"]([^"^\']+?)[\'"]''')[0]
			image_alt = self.cm.ph.getSearchGroups(data, '''alt=[\'"]([^"^\']+?)[\'"]''')[0]
			if image_url != '':
				if image_url.startswith('//'):
					image_url = 'https:' + image_url
				if not image_url.startswith('https'):
					return []
			else:
				image_url = self.DEFAULT_ICON_URL_FORMA1
			data_tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div class=', '>', 'gpInfo'), ('<span class="lrTime"', '</span>'))[1]
			if data_tmp != '':
				csucs_vezeto = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<span class="lrName">', '</span>', False)[1]
				csucs_ev = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<span class="lrTeam">', '</span>', False)[1]
				csucs_ev = self.cm.ph.getSearchGroups(csucs_ev, '''([0-9]{4})''')[0]
				csucs_ido = self.cm.ph.getDataBeetwenMarkers(data_tmp, '<span class="lrTime">', '</span>', False)[1]
			else:
				csucs_vezeto = ''
				csucs_ev = ''
				csucs_ido = ''
			items = self.cm.ph.getAllItemsBeetwenMarkers(data_tmp, '<div class="', '</div>')
			if len(items) > 0:
				palyahossz = clean_html(items[0])
				palyahossz_value = clean_html(items[1])
				versenytav = clean_html(items[2])
				versenytav_value = clean_html(items[3])
				korok = clean_html(items[4])
				korok_value = clean_html(items[5])
				desc = palya_neve + '\n\n' + palyahossz + ':  ' + palyahossz_value + '\n' + versenytav + ':  ' + versenytav_value + '\n' + korok + ':  ' + korok_value + '\n\nPályacsúcs:\n' + csucs_vezeto + '\név: ' + csucs_ev + '\nidő: ' + csucs_ido
			else:
				desc = ''            
			retList = {'title':title_citem, 'text': desc, 'images':[{'title':image_alt, 'url':image_url}]}
			return [retList]
		except Exception:
			printExc()
			
	def fgtac(self, cItem):
		try:
			self.susn('2', '1', cItem['url'])
			title_citem = cItem['title']
			icon_citem = cItem['icon']
			desc = 'Észrevételeidet, javaslataidat a következő címre küldheted el:\n' + zlib.decompress(base64.b64decode('eJxLLC3J18so1ctJLUvNcUjPTczM0UvOzwUAaY8Iwg==')) + '\n\nFelhívjuk figyelmedet, hogy egyes csatornák adásai átmenetileg szünetelhetnek. Mielőtt hibát jelzel, ellenőrizd az adott csatorna internetes oldalán az adás működését.\n\nAmennyiben egyes adások nem játszhatók le (NINCS ELÉRHETŐ LINK), akkor az adott műsor tartalomszolgáltatója megváltoztatta annak elérhetőségét. Ez nem az "auto.HU" lejátszó hibája!!!\n\nKellemes szórakozást kívánunk!'            
			retList = {'title':title_citem, 'text': desc, 'images':[{'title':'', 'url':icon_citem}]}
			return [retList]
		except Exception:
			printExc()

	def getLinksForVideo(self, cItem):
		try:
			tabID = cItem.get('tab_id', '')
			if tabID == 'autogram':
				nez = self.Autogram_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.suuim('2', cItem['url'])
				return nez
			elif tabID == 'garazs':
				nez = self.Garazs_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.suuim('2', cItem['url'])
				return nez
			elif tabID == 'supercar':
				nez = self.Supercar_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.suuim('2', cItem['url'])
				return nez
			elif tabID == 'holvezes':
				nez = self.Holvezes_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v18vIzylLrUotLk7N1sso1QcAhXwJ2Q==')) + cItem['url'])
				return nez
			elif tabID in ['vezess_matksz','vezess_ertekb','vezess_aszaloncs','vezess_ojkogm','vezess_bgtgml','vezess_htank','vezess_haaktink','vezess_trahvzs']:
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID in ['totalcar', 'total_trtk', 'total_mlypn', 'total_treo', 'total_tlbk', 'total_szjsn', 'total_trmks', 'total_uzk', 'total_tlac']:
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'autonav_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'handras_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'autoshow':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'fordrive':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'autosaman_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'autoroom_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'villany_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'alapjarat_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'bpiautosok_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == '112press_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'speedzone_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'autobabbo_m':
				nez = self.Yt_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.susn('2', '1', cItem['url'])
				return nez
			elif tabID == 'forma1':
				nez = self.Forma1_getLinksForVideo(cItem)
				if len(nez) > 0:
					self.suuim('2', cItem['url'])
				return nez
			else:
				return []
		except Exception:
			return []    
			
	def Autogram_getLinksForVideo(self, cItem):
		url = cItem['url']
		videoUrls = []
		if not self.tryTologin(): return videoUrls
		sts, data = self.cm.getPage(self.VIDEO_URL.format(url), self.apiParams)
		if not sts: return videoUrls
		if len(data) == 0: return videoUrls
		try:
			data = json_loads(data)
			assets = data['clips'][0].get('assets')
			url = assets[0].get('full_physical_path');
		except Exception:
			printExc()
			return videoUrls
		uri = urlparser.decorateParamsFromUrl(url)
		protocol = uri.meta.get('iptv_proto', '')
		printDBG("PROTOCOL [%s] " % protocol)
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
			
	def Garazs_getLinksForVideo(self, cItem):
		urlTab = []
		url = cItem['url']
		sts, data = self.getPage(url)
		if not sts: return []
		if len(data) == 0: return []
		data = self.cm.ph.getDataBeetwenMarkers(data, '<span class="video-holder', '</span>')[1]
		if len(data) == 0: return []
		url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''')[0]
		if zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOzwUAae8I2Q==')) in url:
			if 1 == self.up.checkHostSupport(url):
				return self.up.getVideoLinkExt(url)
			else:
				return []
		else:
			return []
			
	def Holvezes_getLinksForVideo(self, cItem):
		urlTab = []
		if cItem['url'] != '':
			url = zlib.decompress(base64.b64decode('eJzLKCkpKLbS1y8vL9erzC8tKU1K1UvOz9UvTyxJzrAvswUAycMMEQ==')) + cItem['url']
			if 1 == self.up.checkHostSupport(url):
				return self.up.getVideoLinkExt(url)
			else:
				return []
		else:
			return []

	def Supercar_getLinksForVideo(self, cItem):
		urlTab = []
		url = cItem['url']
		sts, data = self.getPage(url)
		if not sts: return []
		if len(data) == 0: return []
		data = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>')[1]
		if len(data) == 0: return []
		data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source ', '>', False, False)
		if data == '': return []
		for item in data:
			url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
			tmp_url_list = url.split('?')
			url = tmp_url_list[0]
			if url.startswith('//'):
				url = 'http:' + url
			if not url.startswith('http'):
				continue
			if not self.cm.isValidUrl(url):
				continue
			if 'video/mp4' in item:
				label = self.cm.ph.getSearchGroups(item, '''type=['"]([^"^']+?)['"]''')[0]
				urlTab.append({'name':label, 'url':url, 'need_resolve':0})
		return urlTab
		
	def Yt_getLinksForVideo(self, cItem):
		url = cItem['url']
		if cItem['url'] != '':
			if 1 == self.up.checkHostSupport(url):
				return self.up.getVideoLinkExt(url)
			else:
				return []
		else:
			return []
		
	def Forma1_getLinksForVideo(self, cItem):
		urlTab = []
		url = cItem['url']
		baseUrl = strwithmeta(url)
		HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
		referer = baseUrl.meta.get('Referer')
		if referer: HTTP_HEADER['Referer'] = referer
		urlParams = {'header':HTTP_HEADER}
		sts, data = self.cm.getPage(baseUrl, urlParams)
		if not sts: return []
		if data == '': return []
		cUrl = self.cm.meta['url']
		f = ph.find(data, 'player?', '&', flags=0)[1]
		if not f: f = cUrl.split('player?', 1)[-1].rsplit('&', 1)[0]
		if not f: f = ph.find(data, 'player?', '&', flags=0)[1]
		if not f: return []
		url = '/videaplayer_get_xml.php?{0}&start=0&enablesnapshot=0&platform=desktop&referrer={1}'.format(f, urllib.quote(baseUrl))
		sts, data = self.cm.getPage(self.cm.getFullUrl(url, cUrl))
		if not sts: return []
		if data == '': return []
		meta = {'Referer':cUrl, 'Origin':urlparser.getDomain(baseUrl, False)[:-1], 'User-Agent':HTTP_HEADER['User-Agent']}
		hlsMeta = MergeDicts(meta, {'iptv_proto':'m3u8'})
		data = ph.find(data, ('<video_sources', '>'), '</video_sources>', flags=0)[1]
		if data == '': return []
		data = ph.findall(data, ('<video_source', '>'), '</video_source>')
		if data == '': return []
		for item in data:
			url = self.cm.getFullUrl(ph.clean_html(item), cUrl)
			if not url: continue
			if 'video/mp4' in item:
				width  = ph.getattr(item, 'width')
				height = ph.getattr(item, 'height')
				name   = ph.getattr(item, 'name')
				url    = urlparser.decorateUrl(url, meta)
				urlTab.append({'name':'{0} - {1}x{2}'.format(name, width, height), 'url':url})
			elif 'mpegurl' in item:
				url = urlparser.decorateUrl(url, hlsMeta)
				tmpTab = getDirectM3U8Playlist(url, checkExt=False, checkContent=True)
				urlTab.extend(tmpTab)
		urlTab.reverse()
		return urlTab
		
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
		
	def tryTologin(self):
		needLogin = False
		if self.login != config.plugins.iptvplayer.autohu_rtlmost_login.value or self.password != config.plugins.iptvplayer.autohu_rtlmost_password.value:
			needLogin = True
			self.login = config.plugins.iptvplayer.autohu_rtlmost_login.value
			self.password = config.plugins.iptvplayer.autohu_rtlmost_password.value
		if self.loggedIn and not needLogin: return True
		self.loggedIn = False
		if '' == self.login.strip() or '' == self.password.strip():
			self.sessionEx.open(MessageBox, 'Az Autogram megnézéséhez regisztrálnod kell a %s oldalon! \nA kék gomb, majd az Oldal beállításai segítségével megadhatod az ottani belépési adataidat.' % 'https://www.rtlmost.hu', type = MessageBox.TYPE_ERROR, timeout = 15 )
			return False
		try:
			if os.path.exists(self.COOKIE_FILE): cj = self.cm.getCookie(self.COOKIE_FILE)
			else: cj = cookielib.MozillaCookieJar()
			cookieNames = ['sessionToken', 'sessionSecret', 'loginHash', 'loginValid']
			cookies = [None, None, None, None]
			for cookie in cj:
				if cookie.domain == 'vpv.jf7ekt7r6rbm2.hu':
					try:
						i = cookieNames.index(cookie.name)
						if cookies[i]: cookie.discard = True
						else: cookies[i] = cookie
					except ValueError: cookie.discard = True
			for i, cookie in enumerate(cookies):
				if not cookie:
					cookie = cookielib.Cookie(version=0, name=cookieNames[i], value=None, port=None, port_specified=False,
						domain='vpv.jf7ekt7r6rbm2.hu', domain_specified=False, domain_initial_dot=False, path='/', path_specified=True, secure=True,
						expires=2147483647, discard=False, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
					cookies[i] = cookie
					cj.set_cookie(cookie)
			token = cookies[0]
			secret = cookies[1]
			hash = cookies[2]
			valid = cookies[3]
			needLogin = needLogin or not(token.value and secret.value and hash.value
						and sha1(self.login+self.password+token.value+secret.value).hexdigest() == hash.value)
			if not needLogin:
				if valid.value == '1':
					self.loggedIn = True
					return True
				sts, data = self.cm.getPage(self.ACCOUNT_URL.format(token.value, secret.value), self.loginParams)
				if not sts: raise Exception('Can not Get Account page!')
				data = json_loads(data)
				needLogin = data['errorCode'] != 0
			if needLogin:
				sts, data = self.cm.getPage(self.LOGIN_URL.format( self.login, self.password), self.loginParams)
				if not sts: raise Exception('Can not Get Login page!')
				data = json_loads(data)
				if data['errorCode'] != 0: raise Exception(data.get('errorMessage'))
				token.value = data['sessionInfo']['sessionToken']
				secret.value = data['sessionInfo']['sessionSecret']
				hash.value = sha1(self.login+self.password+token.value+secret.value).hexdigest()
			valid.value = '1'
			valid.expires = int(time.time()) + 86400
			cj.save(self.COOKIE_FILE)
			self.loggedIn = True
			return True
		except:
		   printExc()
		   self.sessionEx.open(MessageBox, _('Login failed.'), type = MessageBox.TYPE_ERROR, timeout = 10)
		return False
			
	def suuim(self, i_md='', i_u=''):
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL0vMS6xKLC3J1yvIKAAAsfsSRw=='))
		pstd = {'md':i_md, 'rl':i_u }
		try:
			if i_md != '' and i_u != '':
				sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
			return
		except Exception:
			return
			
	def susn(self, i_md='', i_hgk='', i_mpu=''):
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL04sSdQvS8wD0ilJegUZBQD8FROZ'))
		pstd = {'md':i_md, 'hgk':i_hgk, 'mpu':i_mpu, 'hv':self.vivn, 'orv':self.porv, 'bts':self.pbtp}
		try:
			if i_md != '' and i_hgk != '' and i_mpu != '':
				sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
			return
		except Exception:
			return
			
	def susmafts(self, i_md='', i_hgk='', i_mptip='', i_mptipe='', i_mpu='', i_mpt='', i_mpi='', i_mpdl='', i_mput='-', i_mpaz='-', i_mpmd='-'):
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUm5iXoFGQUAO2EU5w=='))
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
			if i_mput == '-':
				i_mput = base64.b64encode('-')
			else:
				i_mput = base64.b64encode(i_mput).replace('\n', '').strip()
			if i_mpaz == '-':
				i_mpaz = base64.b64encode('-')
			else:
				i_mpaz = base64.b64encode(i_mpaz).replace('\n', '').strip()
			if i_mpmd == '-':
				i_mpmd = base64.b64encode('-')
			else:
				i_mpmd = base64.b64encode(i_mpmd).replace('\n', '').strip()
			pstd = {'md':i_md, 'hgk':i_hgk, 'mptip':i_mptip, 'mptipe':i_mptipe, 'mpu':i_mpu, 'mpt':i_mpt, 'mpi':i_mpi, 'mpdl':i_mpdl, 'mput':i_mput, 'mpaz':i_mpaz, 'mpmd':i_mpmd}
			if i_md != '' and i_hgk != '' and i_mptip != '' and i_mptipe != ''and i_mpu != '' and i_mpt != '':
				sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
			return
		except Exception:
			return
			
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
			
	def malvad(self, i_md='', i_tp='', i_u='', i_tl=''):
		t_s = ''
		t_le_a = ''
		temp_le = ''
		temp_h = ''
		temp_n = ''
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL0vMS6xKLC3J1yvIKAAAsfsSRw=='))
		pstd = {'md':i_md, 'tp':i_tp, 'rl':i_u, 'tl':i_tl }
		try:
			sts, data = self.getPage(zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1ssoBQCbCwro')))
			if not sts: return t_s
			if len(data) == 0: return t_s
			data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div-fo-div', '</div>')[1]
			if len(data) == 0: return t_s
			data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '/>')
			if len(data) == 0: return t_s
			if 'ahufh1' not in data[0]: return t_s
			if 'ahufl1' not in data[1]: return t_s
			t_le_a = zlib.decompress(base64.b64decode(self.cm.ph.getSearchGroups(data[1], 'value=[\'"]([^"^\']+?)[\'"]')[0]))
			if i_u == '':
				return t_le_a
		except Exception:
			return t_s
		try:
			if i_md != '' and i_tp != '' and i_u != '' and i_tl != '':
				sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
				if not sts: return t_s
				if len(data) == 0: return t_s
				data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a_div', '</div>')[1]
				if len(data) == 0: return t_s
				data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '/>')
				if len(data) == 0: return t_s
				for item in data:
					t_i = self.cm.ph.getSearchGroups(item, 'id=[\'"]([^"^\']+?)[\'"]')[0]
					if t_i == 'il':
						temp_le = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0]
						temp_le = temp_le.replace('A_', '')
						temp_le = temp_le.replace('_A', '')
					elif t_i == 'ih':
						temp_h = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0] 
					elif t_i == 'in':
						temp_n = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^"^\']+?)[\'"]')[0]
				if temp_le == '-' or temp_le == '':
					t_s = t_le_a
				else:
					t_s = '- ' + temp_le + '\n\nA műsor hossza:  ' + temp_h + '  |  ' + temp_n
			return t_s
		except Exception:
			return t_le_a
		return t_s
		
	def getdvdsz(self, pu='', psz=''):
		bv = ''
		if pu != '' and psz != '':
			n_atnav = self.malvadst('1', '1', pu)
			if n_atnav != '' and self.aid:
				self.aid_ki = 'ID: ' + n_atnav + '\n'
			else:
				self.aid_ki = ''
			bv = self.aid_ki + psz
		return bv

	def malvadst(self, i_md='', i_hgk='', i_mpu=''):
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL04sSdQvS8wD0ilJegUZBQD8FROZ'))
		pstd = {'md':i_md, 'hgk':i_hgk, 'mpu':i_mpu }
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
			return t_le_a
		return t_s

	def malvadnav(self, cItem, i_md='', i_hgk='', i_mptip=''):
		uhe = zlib.decompress(base64.b64decode('eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUm5iXoFGQUAO2EU5w=='))
		t_s = []
		try:
			if i_md != '' and i_hgk != '' and i_mptip != '':
				if i_hgk != '': i_hgk = base64.b64encode(i_hgk).replace('\n', '').strip()
				if i_mptip != '': i_mptip = base64.b64encode(i_mptip).replace('\n', '').strip()
				pstd = {'md':i_md, 'hgk':i_hgk, 'mptip':i_mptip}
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
						if t_vp == 'c_sor_ut':
							temp_tut = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_ut">', '</span>', False)[1]
							if temp_tut != '': temp_tut = base64.b64decode(temp_tut)
						if t_vp == 'c_sor_az':
							temp_az = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_az">', '</span>', False)[1]
							if temp_az != '': temp_az = base64.b64decode(temp_az)
						if t_vp == 'c_sor_md':
							temp_md = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_md">', '</span>', False)[1]
							if temp_md != '': temp_md = base64.b64decode(temp_md)
					if temp_u == '' and temp_t =='': continue
					if temp_n == '': temp_n = '1'
					params = MergeDicts(cItem, {'good_for_fav': False, 'url':temp_u, 'title':temp_t, 'icon':temp_i, 'desc':temp_l, 'nztsg':temp_n, 'tps':temp_tp, 'azn':temp_az, 'mkt': temp_tut, 'md':temp_md})
					t_s.append(params)       
			return t_s
		except Exception:
			return []
		
	def listSearchResult(self, cItem, searchPattern, searchType):
		printDBG("listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
		url_susn = cItem['url']
		self.susn('2', '1', url_susn)
	
	def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
		CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
		name     = self.currItem.get("name", '')
		category = self.currItem.get("category", '')
		mode     = self.currItem.get("mode", '')
		self.currList = []
		if name == None:
			self.listMainMenu( {'name':'category'} )
		elif category == 'list_main':
			self.listMainItems(self.currItem, 'list_episodes')
		elif category == 'list_second':
			self.listSecondItems(self.currItem, 'list_episodes')
		elif category == 'list_episodes':
			self.listEpisodes(self.currItem, 'list_third')
		elif category == 'list_third':
			self.listThird(self.currItem)
		elif category in ["search", "search_next_page"]:
			cItem = dict(self.currItem)
			cItem.update({'search_item':False, 'name':'category'}) 
			self.listSearchResult(cItem, searchPattern, searchType)
		else:
			printExc()
		CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

	def __init__(self):
		CHostBase.__init__(self, AutosHU(), True, [])
		
	def withArticleContent(self, cItem):
		if cItem['type'] != 'article':
			return False
		return True
