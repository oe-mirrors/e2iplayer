# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetCookieDir
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
############################################

###################################################
# E2 GUI COMMPONENTS
###################################################
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


class WkylinewebcamsComApi:
    MAIN_URL = 'https://www.skylinewebcams.com/'
    HTML_EXT = '.html'

    def __init__(self):
        self.COOKIE_FILE = GetCookieDir('skylinewebcamscom.cookie')
        self.cm = common()
        self.up = urlparser()
        self.http_params = {}
        self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.cacheList = {}
        self.mainMenuCache = {}
        self.lang = config.plugins.iptvplayer.skylinewebcams_lang.value

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

    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)

    def _extract_countries(self, data, cItem):
        """Extract countries from menu"""
        tab = []
        states_part = self.cm.ph.getDataBeetwenMarkers(data, 'class="dropdown-menu mega-dropdown-menu"', '<div class="collapse navbar')[1]
        state_data = states_part.split('class="continent')
        for region in state_data:
            continent = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(region, '<strong>', '</strong>')[1])
            cat_data = region.split('</a>')
            for item in cat_data:
                url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
                titletext = self.cm.ph.getSearchGroups(item, '''html">([^"]+?)$''', 1, True)[0]
                title = "%s: %s" % (continent.capitalize(), self.cleanHtmlStr(titletext))
                if url != '' and title != '':
                    tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'})
        return sorted(tab, key=lambda x: x['title'], reverse=True)

    def _extract_categories(self, data, cItem):
        """Extract categories from page"""
        tab = []
        data_cat = self.cm.ph.getDataBeetwenMarkers(data, 'cat"><div class="container-fluid">', '</li>')[1]
        cat_data = data_cat.split('</a>')
        for item in cat_data:
            url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
            title = self.cleanHtmlStr("Category: " + self.cm.ph.getSearchGroups(item, '''class="tcam">([^<]+?)<''', 1, True)[0])
            if url != '' and title != '':
                tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'})
        return tab[::-1]

    def _extract_category_subitems(self, data_cat, cItem):
        """Extract subitems from categories"""
        for idx in range(2):
            if idx >= len(data_cat):
                continue
            cat_data = data_cat[idx]
            cat_data = cat_data.split('</a>')
            if len(cat_data) < 2:
                continue
            cat_title = self.cleanHtmlStr(cat_data[0])
            cat_url = self.cm.ph.getSearchGroups(cat_data[0], '''<a[^>]*?href="([^"]+?)"''', 1, True)[0]
            cat_data = self.cm.ph.getAllItemsBeetwenMarkers(cat_data[-1], '<a ', '</a>')
            tab = []
            for item in cat_data:
                url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
                title = self.cleanHtmlStr(item)
                if url != '' and title != '':
                    tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'})
            if len(tab):
                tab.insert(0, {'url': self.getFullUrl(cat_url), 'title': _('All'), 'cat': 'list_cams'})
                self.mainMenuCache[idx] = tab
                params = dict(cItem)
                params.update({'title': cat_title, 'cat': 'list_main_category', 'idx': idx})
                yield params

    def getMainMenu(self, cItem):
        printDBG("WkylinewebcamsCom.getMainMenu")
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list

        # Kraje
        countries = self._extract_countries(data, cItem)
        for item in countries:
            params = dict(cItem)
            params.update(item)
            list.insert(0, params)

        # Kategorie
        categories = self._extract_categories(data, cItem)
        for item in categories:
            params = dict(cItem)
            params.update(item)
            list.insert(0, params)

        # Subkategorie z cache
        data_cat = self.cm.ph.getDataBeetwenMarkers(data, 'cat"><div class="container-fluid">', '</li>')[1]
        for item in self._extract_category_subitems(data_cat, cItem):
            list.append(item)

        return list

    def _extract_cams_method1(self, data):
        """Method 1: Original method with markers"""
        found = []
        data_parts = self.cm.ph.getAllItemsBeetwenMarkers(data, '</h1><hr>', '<div class="footer">')
        if data_parts:
            items = self.cm.ph.getAllItemsBeetwenMarkers(data_parts[0], '<a ', '</a>')
            for item in items:
                url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
                icon = self.cm.ph.getSearchGroups(item, r'''"([^"]+?\.(?:jpg|webp))"''', 1, True)[0]
                if '' == url:
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt="([^"]+?)"''', 1, True)[0])
                if '' == title:
                    title = self.cleanHtmlStr(item)
                desc = self.cleanHtmlStr(item)
                found.append((url, icon, title, desc))
        return found

    def _extract_cams_method2(self, data):
        """Method 2: Search in webcam-item class"""
        found = []
        pattern = r'<div[^>]*?class="[^"]*?webcam-item[^"]*?"[^>]*?>.*?<a[^>]*?href="([^"]+?)"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"'
        matches = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
        for url, icon, title in matches:
            if url:
                found.append((url, icon, title, ''))
        return found

    def _extract_cams_method3(self, data):
        """Method 3: Search in cam class"""
        found = []
        pattern = r'<div[^>]*?class="[^"]*?cam[^"]*?"[^>]*?>.*?<a[^>]*?href="([^"]+?)"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"'
        matches = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
        for url, icon, title in matches:
            if url:
                found.append((url, icon, title, ''))
        return found

    def _extract_cams_method4(self, data):
        """Method 4: Search in webcam list"""
        found = []
        pattern = r'<li[^>]*?class="[^"]*?webcam[^"]*?"[^>]*?>.*?<a[^>]*?href="([^"]+?)"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"'
        matches = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
        for url, icon, title in matches:
            if url:
                found.append((url, icon, title, ''))
        return found

    def _extract_cams_method5(self, data):
        """Method 5: Simple link search"""
        found = []
        links = re.findall(r'<a[^>]*?href="([^"]*?webcam[^"]*?)"[^>]*?>', data, re.IGNORECASE)
        for link in links:
            if link and not link.startswith('#'):
                context = re.search(
                    r'<a[^>]*?href="%s"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"' % re.escape(link),
                    data,
                    re.DOTALL | re.IGNORECASE
                )
                if context:
                    icon, title = context.group(1), context.group(2)
                else:
                    icon, title = '', ''
                if not title:
                    title = link.split('/')[-1].replace(self.HTML_EXT, '').replace('-', ' ').title()
                found.append((link, icon, title, ''))
        return found

    def _process_found_items(self, found_items, cItem):
        """Process found items and create list"""
        result = []
        for url, icon, title, desc in found_items:
            if not url.startswith('http'):
                url = self.getFullUrl(url)
            if icon and not icon.startswith('http'):
                icon = self.getFullUrl(icon)
            if not title:
                title = url.split('/')[-1].replace(self.HTML_EXT, '').replace('-', ' ').title()

            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': desc or title,
                'type': 'video'
            })
            result.append(params)
        return result

    def listCams(self, cItem):
        printDBG("WkylinewebcamsCom.listCams url[%s]" % cItem['url'])
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        # Próba znalezienia kamer różnymi metodami
        methods = [
            self._extract_cams_method1,
            self._extract_cams_method2,
            self._extract_cams_method3,
            self._extract_cams_method4,
            self._extract_cams_method5
        ]

        found_items = []
        for method in methods:
            found_items = method(data)
            if found_items:
                break

        result = self._process_found_items(found_items, cItem)
        printDBG("Found %d cameras" % len(result))
        return result

    def listCams2(self, cItem):
        printDBG("WkylinewebcamsCom.listCams2")
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            if not item.startswith('<a href="%s/webcam/' % self.lang):
                continue
            url = self.cm.ph.getSearchGroups(item, '''[^r]><a href="([^"]+?)"''', 1, True)[0]
            icon = self.cm.ph.getSearchGroups(item, '''src="([^"]+?)"''', 1, True)[0]
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'title': title, 'url': self.getFullUrl(url), 'icon': self.getFullUrl(icon), 'type': 'video'})
            list.append(params)
        return list

    def exploreItem(self, cItem):
        printDBG("WkylinewebcamsCom.exploreItem")
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="webcam">', '</li>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
            icon = self.cm.ph.getSearchGroups(item, r'''"([^"]+?\.(?:jpg|webp))"''', 1, True)[0]
            if '' == url:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt="([^"]+?)"''', 1, True)[0])
            desc = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'title': title, 'url': self.getFullUrl(url), 'icon': self.getFullUrl(icon), 'desc': desc, 'type': 'video'})
            list.append(params)
        return list

    def getChannelsList(self, cItem):
        printDBG("WkylinewebcamsCom.getChannelsList")
        list = []
        cat = cItem.get('cat', None)
        lang = config.plugins.iptvplayer.skylinewebcams_lang.value
        self.lang = lang
        if None is cat:
            cItem = dict(cItem)
            cItem['url'] = self.MAIN_URL + lang + self.HTML_EXT
            return self.getMainMenu(cItem)
        elif 'list_main_category' == cat:
            tab = self.mainMenuCache.get(cItem['idx'], [])
            for item in tab:
                params = dict(cItem)
                params.update(item)
                list.append(params)
        elif 'list_cams2' == cat:
            return self.listCams2(cItem)
        elif 'list_cams' == cat:
            return self.listCams(cItem)
        elif 'explore_item' == cat:
            return self.exploreItem(cItem)
        return list

    def _extract_youtube_url(self, data):
        """Extract YouTube URL if present"""
        if self.cm.ph.getSearchGroups(data, '''(youtube.com/iframe_api)''', 1, True)[0]:
            video_id = self.cm.ph.getSearchGroups(data, '''videoId:\'([^']+?)\'''', 1, True)[0]
            if video_id:
                return 'https://www.youtube.com/watch?v=%s' % video_id
        return None

    def _extract_video_url(self, data):
        """Extract video stream URL"""
        patterns = [
            r'''source:\s*['"]([^"']+?m3u8[^"']*?)['"]''',
            r'''file:\s*['"]([^"']+?m3u8[^"']*?)['"]''',
            r'''video\s*src\s*=\s*['"]([^"']+?m3u8[^"']*?)['"]''',
            r'''data-video-url\s*=\s*['"]([^"']+?m3u8[^"']*?)['"]''',
            r'''<video[^>]*?src="([^"]+\.m3u8[^"]*?)"[^>]*?>''',
            r'''https?://[^"']+\.m3u8[^"']*''',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, data, re.IGNORECASE)
            if matches:
                video_url = matches[0]
                if isinstance(video_url, tuple):
                    video_url = video_url[0]
                return video_url
        return None

    def _normalize_video_url(self, video_url):
        """Normalize video URL"""
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        elif not video_url.startswith('http'):
            if video_url.startswith('livee.m3u8'):
                video_url = 'https://hd-auth.skylinewebcams.com/' + video_url.replace('livee', 'live')
            else:
                video_url = 'https://hd-auth.skylinewebcams.com/' + video_url
        return video_url

    def getVideoLink(self, cItem):
        printDBG("WkylinewebcamsCom.getVideoLink url[%s]" % cItem.get('url', ''))
        urlsTab = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return urlsTab

        # Sprawdzenie czy to YouTube
        youtube_url = self._extract_youtube_url(data)
        if youtube_url:
            youtube_url = self.up.getVideoLink(youtube_url)
            if youtube_url:
                urlsTab.append({'name': "YouTube", 'url': youtube_url})
            return urlsTab

        # Szukanie URL strumienia
        video_url = self._extract_video_url(data)
        if video_url:
            video_url = self._normalize_video_url(video_url)
            urlsTab = getDirectM3U8Playlist(video_url)
            if not urlsTab:
                urlsTab.append({'name': 'skylinewebcams.com', 'url': video_url})

        return urlsTab
