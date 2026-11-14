# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
import re
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, getConfigListEntry
try:
    import json
except Exception:
    import simplejson as json
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.skylinewebcams_lang = ConfigSelection(default="en", choices=[("en", "en"), ("it", "it"), ("es", "es"), ("de", "de"), ("fr", "fr"),
                                                                                           ("el", "el"), ("hr", "hr"), ("sl", "sl"), ("zh", "zh")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.skylinewebcams_lang))
    return optionList

###################################################


def gettytul():
    return _("SkylineWebcams")


class WkylinewebcamsComApi(CBaseHostClass):

    MAIN_URL = 'https://www.skylinewebcams.com/'
    # the 'name' every item is tagged with so hostwebstream.py routes it back here
    ITEM_NAME = 'skylinewebcams.com'

    def __init__(self):
        printDBG("WkylinewebcamsCom.__init__")
        CBaseHostClass.__init__(self, {"history": "skylinewebcamscom", "cookie": "skylinewebcamscom.cookie"})
        self.COOKIE_FILE = GetCookieDir('skylinewebcamscom.cookie')
        self.cm = common()
        self.up = urlparser()
        self.http_params = {}
        self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.cacheList = {}
        self.mainMenuCache = {}
        self.lang = config.plugins.iptvplayer.skylinewebcams_lang.value

    # cleanHtmlStr is inherited from CBaseHostClass (a @staticmethod) -
    # do NOT override it here.

    def getFullUrl(self, url):
        if url == '':
            return ''
        if url.startswith('//'):
            return 'http:' + url
        if url.startswith('http'):
            return url
        elif url.startswith('/'):
            url = url[1:]
        return self.MAIN_URL + url

    # ------------------------------------------------------------------
    # SkylineWebcams v4 layout - two tile formats:
    #
    #   (A) categories / countries pages:
    #       <a class="cam cam-link" href="URL">
    #         <span class="thumb"><img src="ICON" alt="TITLE"></span>
    #         <span class="cam-body"><span class="cam-title">TITLE</span>...</span>
    #       </a>
    #
    #   (B) camera listing pages (TOP Live Cams, "Plaże", a country, ...):
    #       <div class="cam">
    #         <span class="thumb"><img src="ICON" ...></span>
    #         <div class="cam-body">
    #           <a class="cam-title" href="URL">TITLE</a>
    #           <div class="meta">...</div>
    #         </div>
    #       </div>
    # ------------------------------------------------------------------
    _CAM_LINK_RE = re.compile(
        r'<a[^>]*class="[^"]*\bcam-link\b[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL)

    _CAM_TILE_RE = re.compile(
        r'<div[^>]*class="[^"]*\bcam\b[^"]*"[^>]*>\s*'
        r'<span[^>]*class="[^"]*\bthumb\b[^"]*"[^>]*>\s*'
        r'<img[^>]*\bsrc="([^"]+)"[^>]*>.*?'
        r'<a[^>]*class="[^"]*\bcam-title\b[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL)

    def _parseCamLinks(self, data):
        # -> [(url, icon, title)] from <a class="cam cam-link">
        found = []
        for m in self._CAM_LINK_RE.finditer(data):
            href, inner = m.group(1), m.group(2)
            icon = self.cm.ph.getSearchGroups(inner, r'<img[^>]*\bsrc="([^"]+)"', 1, True)[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'<span class="cam-title">([^<]+)</span>', 1, True)[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'\balt="([^"]+)"', 1, True)[0])
            if href and title:
                found.append((href, icon, title))
        return found

    def _parseCamTiles(self, data):
        # -> [(url, icon, title)] from <div class="cam"> ... <a class="cam-title" href>
        found = []
        seen = set()
        for m in self._CAM_TILE_RE.finditer(data):
            icon, href, rawTitle = m.group(1), m.group(2), m.group(3)
            if href in seen:
                continue
            if '/webcam/' not in href:
                continue
            seen.add(href)
            title = self.cleanHtmlStr(re.sub(r'<[^>]+>', ' ', rawTitle)).strip()
            if not title:
                title = self._generate_title_from_url(href)
            found.append((href, icon, title))
        return found

    def _categoryEntries(self, data, cat):
        # the tiles of a "categories" / "countries" page as menu rows
        result = []
        for href, icon, title in self._parseCamLinks(data):
            result.append({'name': self.ITEM_NAME, 'title': title, 'url': self.getFullUrl(href),
                           'icon': self.getFullUrl(icon), 'cat': cat, 'type': 'category'})
        # safety net: also accept the tile format, in case the page mixes them
        for href, icon, title in self._parseCamTiles(data):
            if '/webcam/' not in href:
                continue
            if href.rstrip('/').count('/') <= 5:
                result.append({'name': self.ITEM_NAME, 'title': title, 'url': self.getFullUrl(href),
                               'icon': self.getFullUrl(icon), 'cat': cat, 'type': 'category'})
        return result

    def getMainMenu(self, cItem):
        printDBG("WkylinewebcamsCom.getMainMenu")
        result = []
        sts, data = self.cm.getPage(self.getFullUrl('/%s/categories.html' % self.lang))
        if sts:
            result.extend(self._categoryEntries(data, 'list_cams'))
        sts, data = self.cm.getPage(self.getFullUrl('/%s/webcam.html' % self.lang))
        if sts:
            result.extend(self._categoryEntries(data, 'list_cams'))
        return result

    def _generate_title_from_url(self, url):
        return url.split('/')[-1].replace('.html', '').replace('-', ' ').title()

    def _find_cams(self, data):
        """Find cameras on a listing page: <div class="cam"> tiles (v4 layout)
        with <span class="thumb"><img src> and <a class="cam-title" href>.
        Falls back to <a class="cam cam-link"> for older layouts."""
        found = self._parseCamTiles(data)
        if found:
            return found
        return self._parseCamLinks(data)

    def _process_found_cams(self, found, cItem):
        result = []
        for url, icon, title in found:
            url = self.getFullUrl(url)
            icon = self.getFullUrl(icon) if icon else ''
            if not title:
                title = self._generate_title_from_url(url)
            params = dict(cItem)
            params.update({'name': self.ITEM_NAME, 'title': title, 'url': url,
                           'icon': icon, 'type': 'video'})
            result.append(params)
        return result

    def listCams(self, cItem):
        printDBG("WkylinewebcamsCom.listCams url[%s]" % cItem['url'])
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            printDBG("WkylinewebcamsCom.listCams getPage FAILED")
            return []
        found = self._find_cams(data)
        result = self._process_found_cams(found, cItem)
        printDBG("WkylinewebcamsCom.listCams Found %d cameras" % len(result))
        if len(result) == 0:
            printDBG("WkylinewebcamsCom.listCams WARNING: 0 cams, page size[%d]" % len(data))
        return result

    def getChannelsList(self, cItem):
        printDBG("WkylinewebcamsCom.getChannelsList cItem[%s] cat[%s]" % (cItem, cItem.get('cat', None)))
        cat = cItem.get('cat', None)
        lang = config.plugins.iptvplayer.skylinewebcams_lang.value
        self.lang = lang
        if None is cat:
            cItem = dict(cItem)
            cItem['url'] = self.MAIN_URL + lang + '.html'
            return self.getMainMenu(cItem)
        elif 'list_cams' == cat:
            return self.listCams(cItem)
        return []

    def getVideoLink(self, cItem):
        printDBG("WkylinewebcamsCom.getVideoLink url[%s]" % cItem.get('url', ''))
        urlsTab = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return urlsTab

        # 1) YouTube embed (a few cams)
        if self.cm.ph.getSearchGroups(data, r'(youtube\.com/iframe_api)', 1, True)[0]:
            videoId = self.cm.ph.getSearchGroups(data, r'''videoId\s*:\s*['"]([^'"]+?)['"]''', 1, True)[0]
            if videoId:
                url = 'https://www.youtube.com/watch?v=%s' % videoId
                url = self.up.getVideoLink(url)
                urlsTab = getDirectM3U8Playlist(url)
                urlsTab.append({'name': "YouTuBe", 'url': url})
                return urlsTab
            return urlsTab

        # 2) SkylineWebcams v4 Clappr player:
        #    source: "livee.m3u8?a=TOKEN"  (also "live.m3u8?a=TOKEN", full URLs)
        src = self.cm.ph.getSearchGroups(data, r'''source\s*:\s*["']([^"']*?\.m3u8[^"']*)["']''', 1, True)[0]
        if not src:
            src = self.cm.ph.getSearchGroups(
                data,
                r'''["']((?:livee?\.m3u8[^"']*)|(?:[^"']*hd-auth\.skylinewebcams\.com[^"']*\.m3u8[^"']*))["']''',
                1, True)[0]

        if src:
            if src.startswith('livee.m3u8'):
                src = 'https://hd-auth.skylinewebcams.com/' + src.replace('livee', 'live', 1)
            elif src.startswith('live.m3u8'):
                src = 'https://hd-auth.skylinewebcams.com/' + src
            elif src.startswith('//'):
                src = 'https:' + src
            elif not src.startswith('http'):
                src = self.getFullUrl(src)
            printDBG("SkylineWebcams stream url[%s]" % src)
            urlsTab = getDirectM3U8Playlist(src)
            return urlsTab

        printDBG("SkylineWebcams getVideoLink: no m3u8 source found")
        return urlsTab
