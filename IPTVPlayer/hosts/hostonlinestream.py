# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 15.07.2022 - Blindspot
# 10.10.2026 - host standard: the lists are read from the list page itself (one request instead of one per
#   station; a station with several channels opens as a folder), radio / TV / webcam told apart by the stream
#   format of the row (MP3/AAC -> audio, else video, MJPEG webcams as their stream), First/Jump/Next paging with the last
#   page, favourites (stations and channels reopen from their own page), INFO from the station page
#   (description, website, genre, audio/stream info, status, listeners, last 10 tracks), links: the direct
#   stream plus the site's own proxy/HLS link, MTVA channels (M1, M2, M4 Sport, M5, Duna ...) through the
#   mediaklikk player, YouTube webcams through urlparser; English menu texts, no crash on an empty page
# 10.10.2026 - review: the last page only when the site's pager shows it (its 9-number window made
#   "Next page (2/9)" and a Jump limit of 9 on longer lists)
###################################################
HOST_VERSION = "1.5"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://onlinestream.live/'


LIST_URL = 'https://onlinestream.live/main.cgi?search=%s&broad=%s&feat=&chtype=&server=&format=&sort=%s&fp=20&p={page}'
MEDIAKLIKK_PLAYER = 'https://player.mediaklikk.hu/playernew/player.php?video=%s&noflash=yes&osfamily=Android&osversion=7.0&browsername=Chrome%%20Mobile&browserversion=&title=&contentid=%s&embedded=1'
M3_API = 'https://nemzetiarchivum.hu/api/m3/v3/stream?target=live'
AUDIO_FORMATS = ('MP3', 'AAC', 'OGG', 'OPUS', 'FLAC', 'WMA')


class OnlineStream(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'onlinestream', 'cookie': 'onlinestream.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/gh-pages/Thumbnails/onlinestream.jpg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG('OnlineStream.listMainMenu')
        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Radio stations'), 'page_tpl': LIST_URL % ('', '1', 'listen')},
                        {'category': 'list_items', 'title': 'Internet radio stations', 'page_tpl': LIST_URL % ('', '0', 'listen')},
                        {'category': 'list_items', 'title': _('TV channels'), 'page_tpl': LIST_URL % ('', '7', 'listenpeak')},
                        {'category': 'list_items', 'title': 'Webcams', 'page_tpl': LIST_URL % ('', '4', '')}]
        for item in MAIN_CAT_TAB:
            item.update({'good_for_fav': True, 'page': 1})
        self.listsTab(MAIN_CAT_TAB + self.searchItems(), cItem)

    def _rowFormat(self, row):
        formats = re.findall(r'<span class="([A-Z0-9]+)"></span>', row)
        return formats[0] if formats else ''

    def _rowInfo(self, row):
        """the fields of one list row"""
        info = self.cm.ph.getSearchGroups(row, r'href="(/[^"]+/online/\d+-\d+)"')[0]
        name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'class="allomasnev_allomasnev[^"]*">([^<]+)<')[0])
        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'<p class="allomasnev_mufaj[^"]*">([^<]*)<')[0])
        quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(row, '<td class="minoseg', '</td>', False)[1].split('>', 1)[-1]).replace(' ,', ',')
        listeners = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(row, '<td class="kapcs', '</td>', False)[1].split('>', 1)[-1])
        track = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'class="allomasnev_szamcim">(.*?)</a>', 1, True)[0])
        return {'info': info, 'name': name, 'genre': genre, 'quality': quality, 'listeners': listeners, 'track': track, 'format': self._rowFormat(row)}

    def _desc(self, row):
        parts = [x for x in (row.get('genre', ''), row.get('quality', ''), row.get('listeners', '')) if x]
        desc = ' | '.join(parts)
        if row.get('track'):
            desc += '[/br]%s %s' % (_('Now playing'), row['track'])
        return desc

    def _addChannel(self, cItem, title, url, icon, desc, fmt):
        params = stripPagerKeys(dict(cItem), ('page_tpl', 'query'))
        params.update({'good_for_fav': True, 'category': 'os_channel', 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'stream_format': fmt, 'is_live': True})
        if fmt in AUDIO_FORMATS:
            self.addAudio(params)
        else:
            # MJPEG webcams too: the picture viewer can not show a multipart stream, and the old
            # "video -> image" snapshot guess answers 404 on the cameras checked
            self.addVideo(params)

    def listItems(self, cItem):
        printDBG('OnlineStream.listItems')
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageTpl = cItem.get('page_tpl', '')
        if not pageTpl:
            # lists saved by the old version: the url ends with "&p="
            pageTpl = cItem.get('url', '').replace('{', '{{').replace('}', '}}') + '{page}'
        sts, data = self.getPage(pageTpl.format(page=page))
        if not sts:
            return
        table = data[data.find('>Lejátszás</th>'):] if '>Lejátszás</th>' in data else ''
        stations = []
        for row in table.split('<tr class="lista_')[1:]:
            row = row.split('</tr>')[0]
            if row.startswith('collapse_'):
                if stations:
                    stations[-1]['channels'].append(self._rowInfo(row))
            elif row.startswith(('paratlan_sor', 'paros_sor')):
                station = self._rowInfo(row)
                if not station['info']:
                    continue
                logo = self.cm.ph.getSearchGroups(row, r"background-image: url\('([^']+)'\)")[0]
                station.update({'icon': self.getFullIconUrl(logo) if logo else '', 'channels': []})
                stations.append(station)
        for station in stations:
            channels = station['channels']
            title = station['name'] or self.cleanHtmlStr(station['info'].split('/')[1].replace('-', ' '))
            if len(channels) > 1:
                params = stripPagerKeys(dict(cItem), ('page_tpl', 'query'))
                params.update({'good_for_fav': True, 'category': 'os_station', 'title': title, 'url': self.getFullUrl(station['info']), 'icon': station['icon'],
                               'desc': '%s: %d[/br]%s' % (_('Channels'), len(channels), self._desc(station)),
                               'stream_format': channels[0]['format'] or station['format']})
                self.addDir(params)
            else:
                row = channels[0] if channels else station
                fmt = row['format'] or station['format']
                self._addChannel(cItem, title, self.getFullUrl(row['info'] or station['info']), station['icon'], self._desc(dict(station, **{k: v for k, v in row.items() if v})), fmt)
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination">', '</ul>', False)[1]
        hasNext = bool(pager) and 'disabled"><a><span class="glyphicon glyphicon-chevron-right' not in pager and bool(re.search(r'[?&]p=\d+"[^>]*>(?:<[^>]+>)*<span class="glyphicon glyphicon-chevron-right', pager))
        # the pager shows a window of 9 numbers; the last page is only known when the window
        # reaches past it (the numbers after the last page are greyed out) or there is no next page
        numbers = re.findall(r'<li class="([^"]*)"><a[^>]*>(\d+)</a>', pager)
        if not hasNext:
            lastPage = page
        elif any('disabled' in cls for cls, _num in numbers):
            lastPage = max([int(num) for cls, num in numbers if 'disabled' not in cls] + [page])
        else:
            lastPage = 0
        addPagingItems(self, dict(cItem, page_tpl=pageTpl), page, hasNext, lastPage, pageTpl)

    def listStation(self, cItem):
        printDBG('OnlineStream.listStation')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        fmt = cItem.get('stream_format', '')
        if not fmt:
            # a station saved as favourite by the old version: the page title tells radio from TV / webcam
            pageTitle = self.cm.ph.getSearchGroups(data, r'<title>([^<]*)')[0]
            fmt = 'MP3' if 'Online rádió' in pageTitle else ('MJPEG' if 'MJPEG' in data else 'HLS')
        select = self.cm.ph.getDataBeetwenMarkers(data, 'info_csatornalista_select', '</ul>', False)[1]
        channels = re.findall(r'<a class="ajax_link" href="(/[^"]+/online/\d+-\d+)"[^>]*>([^<]+)</a>', select)
        if not channels:
            channels = [(cItem['url'].replace(self.MAIN_URL, '/'), cItem['title'])]
        for href, label in channels:
            self._addChannel(cItem, self.cleanHtmlStr(label), self.getFullUrl(href), cItem.get('icon', ''), cItem.get('desc', ''), fmt)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OnlineStream.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({'category': 'list_items', 'page': 1, 'page_tpl': LIST_URL % (urllib_quote_plus(searchPattern), '', '')})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _infoField(self, data, label):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<td>%s:</td><th[^>]*>(.*?)</th>' % re.escape(label), 1, True)[0])

    def _mediaklikk(self, name):
        sts, data = self.getPage(MEDIAKLIKK_PLAYER % (name, name))
        if not sts:
            return ''
        files = re.findall(r'"file":\s*"([^"]+)"', data)
        url = files[-1].replace('\\/', '/') if files else ''
        return 'https:' + url if url.startswith('//') else url

    def getLinksForVideo(self, cItem):
        printDBG('OnlineStream.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if '/online/' not in url:
            return []
        sts, data = self.getPage(url)
        if not sts:
            return []
        urlTab = []
        playlists = self.cm.ph.getDataBeetwenMarkers(data, 'Lejátszási listák:', '</ul>', False)[1]
        direct = ''
        for href, label in re.findall(r'<a (?:target="_blank" )?href="([^"]+)"><span[^>]*>([^<]*)</span>', playlists):
            if '&#9658;' in label:
                direct = href
        hlsLink = self.cm.ph.getSearchGroups(playlists, r'href="(/play\.m3u8\?[^"]+)"')[0]
        proxy = self.cm.ph.getSearchGroups(data, r'data-stream-url="(/?play\.cgi\?[^"]+)"')[0]
        if '/m3/online/' in url and not direct:
            sts, api = self.getPage(M3_API)
            try:
                direct = json_loads(api)['hls']['url'] if sts else ''
            except Exception:
                printExc()
        if 'mkredir' in direct:
            direct = self._mediaklikk(self.cm.ph.getSearchGroups(direct, r'[?&]video=([^&]+)')[0])
        fmt = cItem.get('stream_format', '')
        if direct:
            if self.up.checkHostSupport(direct) == 1:
                # YouTube webcams and the like
                urlTab.append({'name': self.up.getHostName(direct).replace('www.', '').capitalize(), 'url': direct, 'need_resolve': 1})
            elif '.m3u8' in direct or fmt == 'HLS':
                urlTab.extend(getDirectM3U8Playlist(direct, checkExt=False, checkContent=True, sortWithMaxBitrate=99999999) or [{'name': 'HLS', 'url': direct}])
            else:
                urlTab.append({'name': 'Direct link', 'url': urlparser.decorateParamsFromUrl(direct)})
        if proxy:
            urlTab.append({'name': 'OnlineStream proxy', 'url': strwithmeta(self.getFullUrl(proxy.lstrip('/')), {'User-Agent': self.HTTP_HEADER['User-Agent']})})
        elif hlsLink and not urlTab:
            urlTab.append({'name': 'OnlineStream HLS', 'url': strwithmeta(self.getFullUrl(hlsLink.lstrip('/')), {'User-Agent': self.HTTP_HEADER['User-Agent']})})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG('OnlineStream.getVideoLinks [%s]' % videoUrl)
        urlTab = self.up.getVideoLinkExt(videoUrl) if self.cm.isValidUrl(videoUrl) else []
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return urlTab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('OnlineStream.getArticleContent [%s]' % cItem)
        title = cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        sts, data = self.getPage(cItem.get('url', ''))
        if sts:
            name = self._infoField(data, 'Név')
            title = name or title
            textTab = [x for x in (self._infoField(data, 'Leírás, szlogen'), self._infoField(data, 'Weboldal')) if x]
            for key, label in (('genre', 'Műfaj'), ('quality', 'Audió infó'), ('quality', 'Videó infó'), ('status', 'Állapot'), ('views', 'Kapcsolódások')):
                value = self._infoField(data, label)
                if value and key not in other:
                    other[key] = value
            tracks = self.cm.ph.getDataBeetwenMarkers(data, 'Műsorlista (utolsó 10)', 'Mégtöbb műsor', False)[1]
            times = re.findall(r'<span class="badge">([^<]*)</span>', tracks)
            names = [self.cleanHtmlStr(x) for x in re.findall(r'<div class="info_tracklist_szamcim">(.*?)</div>', tracks, re.S)]
            lines = ['%s  %s' % (t, n) for t, n in zip(times, names) if n]
            if lines:
                textTab.append('%s:[/br]%s' % (_('Tracklist'), '[/br]'.join(lines)))
            if textTab:
                text = '[/br][/br]'.join(textTab)
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('OnlineStream.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: >> name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ('os_station', 'list_more'):
            # list_more: a station saved by the old version
            self.listStation(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, OnlineStream(), True, [])

    def withArticleContent(self, cItem):
        return '/online/' in cItem.get('url', '') and (cItem.get('type') in ('video', 'audio') or cItem.get('category') == 'os_station')
