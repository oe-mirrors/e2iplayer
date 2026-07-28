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

    def getMainMenu(self, cItem):
        printDBG("WkylinewebcamsCom.getMainMenu")
        STATIC_TAB = [
                      # {'title': _('NEW'), 'url': self.getFullUrl('/%s/new-livecams.html' % self.lang), 'cat': 'list_cams2'},
                      # {'title': _('NEARBY CAMS'), 'url': self.getFullUrl('/skyline/morewebcams.php?w=you&l=' + self.lang), 'cat': 'list_cams2'},
                      # {'title': _('TOP live cams'), 'url': self.getFullUrl(self.lang + '/top-live-cams.html'), 'cat': 'list_cams'},
                      ]
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list

        tab = []
        # Pobieranie kontynentów i krajów
        statesPart = self.cm.ph.getDataBeetwenMarkers(data, 'class="dropdown-menu mega-dropdown-menu"', '<div class="collapse navbar')[1]
        stateData = statesPart.split('class="continent')
        for region in stateData:
            continent = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(region, '<strong>', '</strong>')[1])
            catData = region.split('</a>')
            for item in catData:
                url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
                titletext = self.cm.ph.getSearchGroups(item, '''html">([^"]+?)$''', 1, True)[0]
                title = "%s: %s" % (continent.capitalize(), self.cleanHtmlStr(titletext))
                if url != '' and title != '':
                   tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'})

        tab = sorted(tab, key=lambda x: x['title'], reverse=True)
        for item in tab:
            params = dict(cItem)
            params.update(item)
            list.insert(0, params)

        # Kategorie
        tab = []
        data_cat = self.cm.ph.getDataBeetwenMarkers(data, 'cat"><div class="container-fluid">', '</li>')[1]
        catData = data_cat.split('</a>')
        for item in catData:
           url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
           title = self.cleanHtmlStr("Category: " + self.cm.ph.getSearchGroups(item, '''class="tcam">([^<]+?)<''', 1, True)[0])
           if url != '' and title != '':
               tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'})

        for item in tab[::-1]:
            params = dict(cItem)
            params.update(item)
            list.insert(0, params)

        # Kategorie z cache
        for idx in range(2):
            if idx >= len(data_cat):
                continue
            catData = data_cat[idx]
            catData = catData.split('</a>')
            if len(catData) < 2:
                continue
            catTitle = self.cleanHtmlStr(catData[0])
            catUrl = self.cm.ph.getSearchGroups(catData[0], '''<a[^>]*?href="([^"]+?)"''', 1, True)[0]
            catData = self.cm.ph.getAllItemsBeetwenMarkers(catData[-1], '<a ', '</a>')
            tab = []
            for item in catData:
                url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
                title = self.cleanHtmlStr(item)
                if url != '' and title != '':
                    tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'})
            if len(tab):
                tab.insert(0, {'url': self.getFullUrl(catUrl), 'title': _('All'), 'cat': 'list_cams'})
                self.mainMenuCache[idx] = tab
                params = dict(cItem)
                params.update({'title': catTitle, 'cat': 'list_main_category', 'idx': idx})
                list.append(params)

        for item in STATIC_TAB:
                params = dict(cItem)
                params.update(item)
                list.insert(0, params)
        return list

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

    def listCams(self, cItem):
        printDBG("WkylinewebcamsCom.listCams url[%s]" % cItem['url'])
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list

        # Próba znalezienia kamer różnymi metodami
        found_items = []

        # Metoda 1: Oryginalna metoda z markerami
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
                found_items.append((url, icon, title, desc))

        # Metoda 2: Szukanie w strukturze z klasą webcam-item
        if not found_items:
            pattern = r'<div[^>]*?class="[^"]*?webcam-item[^"]*?"[^>]*?>.*?<a[^>]*?href="([^"]+?)"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)".*?</a>'
            matches = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
            for url, icon, title in matches:
                if url:
                    found_items.append((url, icon, title, ''))

        # Metoda 3: Szukanie w strukturze z klasą cam
        if not found_items:
            pattern = r'<div[^>]*?class="[^"]*?cam[^"]*?"[^>]*?>.*?<a[^>]*?href="([^"]+?)"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"'
            matches = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
            for url, icon, title in matches:
                if url:
                    found_items.append((url, icon, title, ''))

        # Metoda 4: Szukanie w liście
        if not found_items:
            pattern = r'<li[^>]*?class="[^"]*?webcam[^"]*?"[^>]*?>.*?<a[^>]*?href="([^"]+?)"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"'
            matches = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
            for url, icon, title in matches:
                if url:
                    found_items.append((url, icon, title, ''))

        # Metoda 5: Proste szukanie linków
        if not found_items:
            links = re.findall(r'<a[^>]*?href="([^"]*?webcam[^"]*?)"[^>]*?>', data, re.IGNORECASE)
            for link in links:
                if link and not link.startswith('#'):
                    # Szukaj tytułu i ikony w kontekście
                    context = re.search(r'<a[^>]*?href="%s"[^>]*?>.*?<img[^>]*?src="([^"]+?)"[^>]*?alt="([^"]*?)"' % re.escape(link), data, re.DOTALL | re.IGNORECASE)
                    if context:
                        icon, title = context.group(1), context.group(2)
                    else:
                        icon, title = '', ''
                    if not title:
                        title = link.split('/')[-1].replace('.html', '').replace('-', ' ').title()
                    found_items.append((link, icon, title, ''))

        # Dodawanie znalezionych kamer do listy
        for url, icon, title, desc in found_items:
            if not url.startswith('http'):
                url = self.getFullUrl(url)
            if icon and not icon.startswith('http'):
                icon = self.getFullUrl(icon)
            if not title:
                title = url.split('/')[-1].replace('.html', '').replace('-', ' ').title()

            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': desc or title,
                'type': 'video'
            })
            list.append(params)

        printDBG("Found %d cameras" % len(list))
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
            cItem['url'] = self.MAIN_URL + lang + '.html'
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

    def getVideoLink(self, cItem):
        printDBG("WkylinewebcamsCom.getVideoLink url[%s]" % cItem.get('url', ''))
        urlsTab = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return urlsTab

        # Sprawdzenie czy to YouTube
        if self.cm.ph.getSearchGroups(data, '''(youtube.com/iframe_api)''', 1, True)[0]:
            url = self.cm.ph.getSearchGroups(data, '''videoId:\'([^']+?)\'''', 1, True)[0]
            if url:
                url = 'https://www.youtube.com/watch?v=%s' % url
                url = self.up.getVideoLink(url)
                if url:
                    urlsTab.append({'name': "YouTube", 'url': url})
                return urlsTab

        # Szukanie URL strumienia
        video_url = ''
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
                break

        if video_url:
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            elif not video_url.startswith('http'):
                if video_url.startswith('livee.m3u8'):
                    video_url = 'https://hd-auth.skylinewebcams.com/' + video_url.replace('livee', 'live')
                else:
                    video_url = 'https://hd-auth.skylinewebcams.com/' + video_url

            urlsTab = getDirectM3U8Playlist(video_url)
            if not urlsTab:
                urlsTab.append({'name': 'skylinewebcams.com', 'url': video_url})

        return urlsTab
