# -*- coding: utf-8 -*-
# hostxtream.py
# Xtream IPTV (LIVE only)
# Last modified: 17/10/2025 - popking (odem2014)
# Compatible with modern E2iPlayer structure

from __future__ import absolute_import, division
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Components.config import config, ConfigText, getConfigListEntry
import json
import os

###################################################
# Xtream Config
###################################################
try:
    from Components.config import ConfigSubsection
    if not hasattr(config.plugins, 'iptvplayer'):
        config.plugins.iptvplayer = ConfigSubsection()
    if not hasattr(config.plugins.iptvplayer, 'xtream_host'):
        config.plugins.iptvplayer.xtream_host = ConfigText(default="", fixed_size=False)
    if not hasattr(config.plugins.iptvplayer, 'xtream_username'):
        config.plugins.iptvplayer.xtream_username = ConfigText(default="", fixed_size=False)
    if not hasattr(config.plugins.iptvplayer, 'xtream_password'):
        config.plugins.iptvplayer.xtream_password = ConfigText(default="", fixed_size=False)
    if not hasattr(config.plugins.iptvplayer, 'xtream_useragent'):
        config.plugins.iptvplayer.xtream_useragent = ConfigText(default="", fixed_size=False)
except Exception as e:
    print("Xtream config init error:", e)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Xtream host (e.g. http://server:port)"), config.plugins.iptvplayer.xtream_host))
    optionList.append(getConfigListEntry(_("Username"), config.plugins.iptvplayer.xtream_username))
    optionList.append(getConfigListEntry(_("Password"), config.plugins.iptvplayer.xtream_password))
    optionList.append(getConfigListEntry(_("Optional User-Agent (leave blank for default)"), config.plugins.iptvplayer.xtream_useragent))
    return optionList


def gettytul():
    return 'Xtream IPTV (LIVE)'


class XtreamApiHost(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'xtream.live', 'cookie': 'xtream.live.cookie'})
        self.cm = common()
        self.MAIN_URL = ''
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/xtream.png"
        self.HTTP_HEADER = {'User-Agent': 'Enigma2-IPTV XtreamAPI/1.0', 'Accept': 'application/json', 'Connection': 'close'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.host, self.username, self.password, self.useragent = '', '', '', ''
        self.account_info = None

    ###################################################
    # Helpers
    ###################################################
    def _readConfig(self):
        self.host = config.plugins.iptvplayer.xtream_host.value.strip()
        self.username = config.plugins.iptvplayer.xtream_username.value.strip()
        self.password = config.plugins.iptvplayer.xtream_password.value.strip()
        self.useragent = config.plugins.iptvplayer.xtream_useragent.value.strip()
        if self.useragent:
            self.defaultParams['header'] = MergeDicts(self.defaultParams['header'], {'User-Agent': self.useragent})

    def _makeApiUrl(self, action, extra=''):
        return '%s/player_api.php?username=%s&password=%s&action=%s%s' % (self.host.rstrip('/'), self.username, self.password, action, extra)

    def _isConfigured(self):
        self._readConfig()
        return all([self.host, self.username, self.password])

    def _requestJson(self, url):
        try:
            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts or not data:
                return False, None
            return True, json_loads(data)
        except Exception:
            printExc()
            return False, None

    ###################################################
    # Account Info
    ###################################################
    def getAccountInfo(self):
        if self.account_info is not None:
            return self.account_info
        self.account_info = {}
        try:
            url = self._makeApiUrl('get_account_info')
            sts, data = self._requestJson(url)
            if sts and isinstance(data, dict) and 'user_info' in data:
                ui = data.get('user_info', {})
                self.account_info = {
                    'expiry': ui.get('exp_date'),
                    'status': ui.get('status'),
                    'max_connections': ui.get('max_connections'),
                    'active_cons': ui.get('active_cons')
                }
            return self.account_info
        except Exception:
            printExc()
            return {}

    ###################################################
    # List
    ###################################################
    def listMain(self, cItem):
        if not self._isConfigured():
            self.addMarker({'title': _('Please configure Xtream (blue button)'), 'desc': _('Set host, username, password in host config')})
            return
        ai = self.getAccountInfo()
        desc = ''
        if ai:
            parts = []
            if ai.get('expiry'):
                parts.append(_('Expiry: %s') % ai['expiry'])
            if ai.get('status'):
                parts.append(_('Status: %s') % ai['status'])
            if ai.get('max_connections'):
                parts.append(_('Max connections: %s') % ai['max_connections'])
            if ai.get('active_cons'):
                parts.append(_('Active: %s') % ai['active_cons'])
            desc = ' | '.join(parts)
        self.addDir({'category': 'list_bouquets', 'title': _('LIVE CHANNELS'), 'desc': desc})

    def listBouquets(self, cItem):
        url = self._makeApiUrl('get_live_categories')
        sts, data = self._requestJson(url)
        if not sts or not data:
            self.addMarker({'title': _('Failed to fetch categories')})
            return
        for cat in data:
            cid = cat.get('category_id', '')
            name = cat.get('category_name', '')
            self.addDir({'category': 'list_channels', 'title': name, 'category_id': cid})

    def listChannels(self, cItem):
        cat_id = cItem.get('category_id', '')
        url = self._makeApiUrl('get_live_streams', '&category_id=%s' % cat_id)
        sts, data = self._requestJson(url)
        if not sts or not data:
            self.addMarker({'title': _('Failed to load channels')})
            return
        for elm in data:
            title = elm.get('name', '')
            stream_id = elm.get('stream_id', '')
            icon = elm.get('stream_icon', '')
            stream_url_m3u8 = '%s/live/%s/%s/%s.m3u8' % (self.host.rstrip('/'), self.username, self.password, stream_id)
            stream_url_ts = '%s/live/%s/%s/%s.ts' % (self.host.rstrip('/'), self.username, self.password, stream_id)
            self.addVideo({
                'title': title,
                'url': strwithmeta(stream_url_m3u8, {'User-Agent': self.defaultParams['header'].get('User-Agent', '')}),
                'url_alt': stream_url_ts,
                'icon': icon,
                'hst': 'direct',
                'allow_fav': True
            })

    def getLinksForVideo(self, cItem):
        url = cItem.get('url', '')
        alt = cItem.get('url_alt', '')
        links = []
        if url:
            links.append({'name': 'M3U8 Stream', 'url': url, 'need_resolve': 0})
        if alt:
            links.append({'name': 'TS Stream', 'url': alt, 'need_resolve': 0})
        return links

    def getVideoLinks(self, videoUrl):
        if 0 != self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return [{'name': _('Direct'), 'url': videoUrl, 'need_resolve': 0}]

    def getArticleContent(self, cItem, data=None):
        title, icon = cItem.get('title', ''), cItem.get('icon', '')
        return [{'title': title, 'text': _('Xtream Live Stream'), 'images': [{'url': icon}], 'other_info': {}}]

    ###################################################
    # Handle Service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        self.currList = []
        self._readConfig()

        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_bouquets':
            self.listBouquets(self.currItem)
        elif category == 'list_channels':
            self.listChannels(self.currItem)
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, XtreamApiHost(), True, [])

    def withArticleContent(self, cItem):
        return True
