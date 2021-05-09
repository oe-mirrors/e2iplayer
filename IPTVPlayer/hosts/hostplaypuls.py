# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
import re
import urllib
import random
try:
    import simplejson as json
except Exception:
    import json
###################################################
###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.playpuls_defaultformat = ConfigSelection(default="999999", choices=[("0", "najgorsza"), ("600", "średnia"), ("800", "dobra"), ("999999", "najlepsza")])
config.plugins.iptvplayer.playpuls_usedf = ConfigYesNo(default=False)
config.plugins.iptvplayer.playpuls_defaultproto = ConfigSelection(default="hls", choices=[("rtmp", "dash (mpd)"), ("hls", "hls (m3u8)")])
config.plugins.iptvplayer.playpuls_proxy = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Preferowany protokół:", config.plugins.iptvplayer.playpuls_defaultproto))
    optionList.append(getConfigListEntry("Domyślny jakość video:", config.plugins.iptvplayer.playpuls_defaultformat))
    optionList.append(getConfigListEntry("Używaj domyślnej jakości video:", config.plugins.iptvplayer.playpuls_usedf))
    optionList.append(getConfigListEntry("PlayPuls korzystaj z proxy?", config.plugins.iptvplayer.playpuls_proxy))
    return optionList
###################################################


def gettytul():
    return 'http://playpuls.pl/'


class Playpuls(CBaseHostClass):
    def __init__(self):
        printDBG("Playpuls.__init__")
        self.MAIN_URL = 'http://playpuls.pl/'
        self.SEARCH_URL = self.getMainUrl() + 'search/node/'
        self.DEFAULT_ICON_URL = self.getMainUrl() + 'sites/all/themes/play/logo.png'
        self.HOST = 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'
        self.HEADER = {'User-Agent': self.HOST, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        CBaseHostClass.__init__(self, {'history': 'Playpuls', 'proxyURL': config.plugins.iptvplayer.proxyurl.value, 'useProxy': config.plugins.iptvplayer.playpuls_proxy.value, 'cookie': 'playpuls.cookie'})
        self.cacheMenuTree = []

    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)

    def listsMainMenu(self):
        printDBG("Playpuls.listsMainMenu")
        sts, data = self.cm.getPage(self.getMainUrl())
        if sts:
            menuData = self.cm.ph.getDataBeetwenMarkers(data, '<div id="navigation">', '</div>', False)[1]
            menuData = re.compile('<li class="menu__item menu-[0-9]+? menuparent[^"]*?"><a href="[/]*?([^"]+?)" title="([^"]+?)" class="menu__link">([^<]+?)</a>').findall(menuData)
            for item in menuData:
                if item[1] in 'Filmy':
                    continue
                params = {'name': 'category', 'title': item[1], 'category': 'menu', 'url': self.getFullUrl(item[0]), 'icon': self.DEFAULT_ICON_URL}
                self.addDir(params)
            #
            self.addDir({'name': 'category', 'title': _('Search'), 'category': 'search', 'search_item': True})
            self.addDir({'name': 'category', 'title': _('Search history'), 'category': 'search_history'})

    def listCategory(self, cItem, searchMode=False):
        printDBG("Playpuls.listCategory cItem[%s]" % cItem)
        data = None
        if 'data' not in cItem:
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return
            if searchMode:
              data = self.cm.ph.getDataBeetwenMarkers(data, '<ol class="search-results', '</ol>', False)[1]
            elif '<div class="region region-vod-list">' in data:
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="region region-vod-list">', '</section>', False)[1]
                data = data.split('<div class="line-break">')
                del data[0]
                tmpList = []
                for item in data:
                    title = self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<h2[^>]*?>'), re.compile('</h2>'), False)[1].strip()
                    if '' == title or 'Zobacz również' in title:
                        continue
                    tmpList.append({'title': title, 'data': item})
                if 1 == len(tmpList):
                    data = tmpList[0]['data']
                elif 1 < len(tmpList):
                    for item in tmpList:
                        params = dict(cItem)
                        params.update(item)
                        self.addDir(params)
                    data = None
                else:
                    printExc()
                    data = None
            else:
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="view-content">', '</section>', False)[1]
        else:
            data = cItem['data']
        if None != data:
            self._listItems(data)

    def _listItems(self, data):
        printDBG("Playpuls._listItems")
        data = data.split(' row">')
        del data[0]
        descMarker = '<div class="video-description">'
        for idx in range(len(data)):
            if idx < len(data) - 1:
                item = data[idx] + '>'
            else:
                item = data[idx]
            #printDBG("============================================")
            #printDBG(item)
            #printDBG("============================================")
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(item, 'class="cover" src="([^"]+?)"')[0]
            if '' == icon:
                icon = self.cm.ph.getSearchGroups(item, 'class="screenshot" src="([^"]+?)"')[0]

            # parse title
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="video-caption">', '</div>', False)[1])
            if '' == title:
                title = self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1]
            if '' == title:
                title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]

            # parse description
            if descMarker in item:
                desc = self.cleanHtmlStr(item.split(descMarker)[-1])
            else:
                desc = self.cleanHtmlStr(item)#self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1]

            if '/vod' in url:
                category = 'vod'
            else:
                category = 'menu'
            if '' != url:
                params = {'name': 'category', 'category': category, 'title': title, 'url': self.getFullUrl(url), 'icon': icon, 'desc': desc}
                if 'vod' == category:
                    self.addVideo(params)
                else:
                    self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Playpuls.getLinksForVideo [%s]" % cItem['url'])
        videoUrls = []
        header = dict(self.HEADER)
        header['Referer'] = cItem['url']
        sts, data = self.cm.getPage(cItem['url'], {'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'header': header})
        if not sts:
            return videoUrls
        sts, data = self.cm.getPage(cItem['url'], {'use_cookie': True, 'load_cookie': True, 'save_cookie': False, 'cookiefile': self.COOKIE_FILE, 'header': header, 'cookie_items': {'has_js': '1'}})
        if not sts:
            return videoUrls

        sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<section id="section-player" ', '</section>', False)
        if not sts:
            return videoUrls

        printDBG(data)

        source1Data = self.cm.ph.getSearchGroups(data, "source = '([^']+?)'")[0]
        source2Data = re.compile("([MDmd][123]) = '([^']+?)'").findall(data)
        source3Data = self.cm.ph.getSearchGroups(data, "sources[ ]*=[ ]*(\{[^;]+?);")[0]
        source4Data = re.compile("([MDmd][123])\s*:\s*\{\s*source\s*\:\s*'([^']+?)'").findall(data)
        quality = self.cm.ph.getSearchGroups(data, "quality = '([01])';")[0]

        if (source1Data + source3Data + quality) == '' and 0 == len(source2Data) and 0 == len(source4Data):
            url = 'http://playpuls.pl/sites/all/modules/vod/player.php'
            id = self.cm.ph.getSearchGroups(data, 'id\s*=\s*([0-9]+?);')[0]
            post_data = None #{'id':id}
            url += '?id=%s' % id
            header['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            sts, source3Data = self.cm.getPage(url, {'use_cookie': True, 'load_cookie': True, 'save_cookie': False, 'cookiefile': self.COOKIE_FILE, 'header': header, 'cookie_items': {'has_js': '1'}}, post_data=post_data)
            if not sts:
                return videoUrls
            printDBG(source3Data)

        sources = []
        proto = config.plugins.iptvplayer.playpuls_defaultproto.value
        printDBG("Playpuls.getLinksForVide proto[%s] source1Data[%s] source2Data[%s] source3Data[%s] source4Data[%s] quality[%s] " % (proto, source1Data, source2Data, quality, source3Data, source4Data))
        if '' != source1Data:
            if '' != quality:
                mobileSrc = ''
                urlBase = 'http://redir.atmcdn.pl/http/o2/pulstv/vod/' + source1Data
                if '1' == quality:
                    if 'hls' != proto:
                        mobileSrc = urlBase + '/mp4/864x486_800_bp.mp4'
                    desktopHtmlHdHighSrc = urlBase + '/mp4/1280x720_2500_hp.mp4'
                    desktopHtmlHdMediumSrc = urlBase + '/mp4/864x486_1600_hp.mp4'
                    desktopHtmlHdLowSrc = urlBase + '/mp4/864x486_800_bp.mp4'
                    videoUrls.append({'bitrate': '2500', 'name': 'High - 2500', 'url': desktopHtmlHdHighSrc})
                    videoUrls.append({'bitrate': '1600', 'name': 'Medium - 1600', 'url': desktopHtmlHdMediumSrc})
                    videoUrls.append({'bitrate': '800', 'name': 'Low - 800', 'url': desktopHtmlHdLowSrc})

                elif '0' == quality:
                    if 'hls' != proto:
                        mobileSrc = urlBase + '/mp4/720x576_800_bp.mp4'
                    desktopHtmlSdHighSrc = urlBase + '/mp4/720x576_1600_hp.mp4'
                    desktopHtmlSdLowSrc = urlBase + '/mp4/720x576_800_bp.mp4'
                    videoUrls.append({'bitrate': '1600', 'name': 'Medium - 1600', 'url': desktopHtmlSdHighSrc})
                    videoUrls.append({'bitrate': '800', 'name': 'Low - 800', 'url': desktopHtmlSdLowSrc})

                if '' != mobileSrc:
                    videoUrls.append({'bitrate': '800', 'name': 'Mobile - 800', 'url': mobileSrc})
                else:
                    mobileSrc = 'http://redir.atmcdn.pl/hls/o2/pulstv/vod/' + source1Data + '/hls/playlist.hls/playlist.m3u8'
                    mobileSrc = getDirectM3U8Playlist(mobileSrc, checkExt=False)
                    for item in mobileSrc:
                        item['url'] = self.up.decorateUrl(item['url'], {'iptv_proto': 'm3u8', 'iptv_livestream': False})
                        item['bitrate'] = str(int(item.get('bitrate', '800000')) / 1000)
                        item['name'] = 'Mobile(hls) - %s' % item['bitrate']
                        videoUrls.append(item)
            else:
                sources.append({'quality': 'M1', 'src': '/bucket/%s/m1.mp4' % source1Data})
                sources.append({'quality': 'M2', 'src': '/bucket/%s/m2.mp4' % source1Data})
                sources.append({'quality': 'D1', 'src': '/bucket/%s/d1.mp4' % source1Data})
                sources.append({'quality': 'D2', 'src': '/bucket/%s/d2.mp4' % source1Data})
                sources.append({'quality': 'D3', 'src': '/bucket/%s/d3.mp4' % source1Data})
        elif len(source2Data) > 0:
            for item in source2Data:
                sources.append({'quality': item[0].upper(), 'src': '/play/%s' % item[1]})
        elif len(source4Data) > 0:
            for item in source4Data:
                sources.append({'quality': item[0].upper(), 'src': '/play/%s' % item[1]})
        elif source3Data != '':
            try:
                source3Data = byteify(json.loads(source3Data))
                if 'sources' in source3Data:
                    source3Data = source3Data['sources']
                for key, val in source3Data.iteritems():
                    if val != '':
                        key = key.replace('src', '')
                        sources.append({'quality': key, 'src': '/play/%s' % val})
            except Exception:
                printExc()

        if len(sources):
            qualityMap = {'M1': '400', 'M2': '600', 'D1': '600', 'D2': '800', 'D3': '1000'}
            for item in sources:
                # ["http://vod1.playpuls.pl:1716/Edge/_definst_/amlst:", "http://vod6.playpuls.pl:1935/Edge/_definst_/amlst:"]
                servers = ["http://vod1.playpuls.pl:1716/Edge/_definst_/mp4:s3", "http://vod6.playpuls.pl:1716/Edge/_definst_/mp4:s3"]
                server = servers[random.randrange(len(servers))]
                url = server + item['src'] #.replace("videos/converted/", "X").replace(".mp4", "")
                if 'hls' == proto:
                    url += '/playlist.m3u8'
                else:
                    url += '/manifest.mpd'
                videoUrls.append({'bitrate': qualityMap.get(item['quality'], '0'), 'name': '%s - %s' % (item['quality'], qualityMap.get(item['quality'], '0')), 'url': url})

        if 0 < len(videoUrls):
            max_bitrate = int(config.plugins.iptvplayer.playpuls_defaultformat.value)

            def __getLinkQuality(itemLink):
                return int(itemLink['bitrate'])
            videoUrls = CSelOneLink(videoUrls, __getLinkQuality, max_bitrate).getSortedLinks()
            if config.plugins.iptvplayer.playpuls_usedf.value:
                videoUrls = [videoUrls[0]]
        return videoUrls

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Playpuls.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib.quote_plus(searchPattern)
        self.listCategory(cItem, True)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Playpuls.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Playpuls.handleService: ---------> name[%s], category[%s] " % (name, category))
        self.currList = []

        if None == name:
            self.listsMainMenu()
        elif 'menu' == category:
            self.listCategory(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Playpuls(), True)
