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
                      #{'title': _('NEW'), 'url': self.getFullUrl('/%s/new-livecams.html' % self.lang), 'cat': 'list_cams2'},
                      #{'title': _('NEARBY CAMS'), 'url': self.getFullUrl('/skyline/morewebcams.php?w=you&l=' + self.lang), 'cat': 'list_cams2'},
                      #{'title': _('TOP live cams'), 'url': self.getFullUrl(self.lang + '/top-live-cams.html'), 'cat': 'list_cams'},
                      ]
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list
        
        tab = []
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
                   tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'}) #explore_item            

        tab = sorted(tab, key = lambda x:x, reverse=True)
        for item in tab:
            params = dict(cItem)
            params.update(item)
            list.insert(0, params)    
        
        tab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, 'cat"><div class="container-fluid">', '</li>')[1]
        catData = data.split('</a>')
        for item in catData:
           url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
           title = self.cleanHtmlStr("Category: " + self.cm.ph.getSearchGroups(item, '''class="tcam">([^<]+?)<''', 1, True)[0])
           if url != '' and title != '':
               tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'}) #explore_item
                           
        for item in tab[::-1]:
            params = dict(cItem)
            params.update(item)
            list.insert(0, params)    
        
        for idx in range(2):
            if idx >= len(data):
                continue
            catData = data[idx]
            catData = catData.split('</a>')     
            if url != '' and title != '':
                    tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'}) #explore_item
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
                    tab.append({'url': self.getFullUrl(url), 'title': title, 'cat': 'list_cams'}) #explore_item
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
        printDBG("WkylinewebcamsCom.listCams")
        list = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return list
        data = self.cm.ph.getAllItemsBeetwenMarkers(data,'</h1><hr>', '<div class="footer">')
        if data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data[0], '<a ', '</a>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''', 1, True)[0]
                icon = self.cm.ph.getSearchGroups(item, '''"([^"]+?\.(?:jpg|webp))"''', 1, True)[0]
                if '' == url:
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt="([^"]+?)"''', 1, True)[0])
                if '' == title:
                    continue
                desc = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'title': title, 'url': self.getFullUrl(url), 'icon': self.getFullUrl(icon), 'desc': desc, 'type': 'video'})
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
            icon = self.cm.ph.getSearchGroups(item, '''"([^"]+?\.(?:jpg|webp))"''', 1, True)[0]
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
        if None == cat:
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
        printDBG("WkylinewebcamsCom.getVideoLink")
        urlsTab = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return urlsTab
        if not self.cm.ph.getSearchGroups(data, '''(youtube.com/iframe_api)''', 1, True)[0]:
            url = self.cm.ph.getSearchGroups(data, '''source:['"]([^"^']+?m3u8[^"^']*?)["']''', 1, True)[0]
            if url.startswith('http'):
                urlsTab = getDirectM3U8Playlist(url)
                return urlsTab
            elif url.startswith('livee.m3u8'):
                url = 'https://hd-auth.skylinewebcams.com/'+ url.replace('livee','live')
                urlsTab = getDirectM3U8Playlist(url)
                return urlsTab
        else:
            url = self.cm.ph.getSearchGroups(data, '''videoId:\'([^']+?)\'''', 1, True)[0]
            if url:
                url = 'https://www.youtube.com/watch?v=%s' % url
                url = self.up.getVideoLink(url)
                urlsTab = getDirectM3U8Playlist(url)
                urlsTab.append({'name': "YouTuBe", 'url': url})
                return urlsTab
        return urlsTab
