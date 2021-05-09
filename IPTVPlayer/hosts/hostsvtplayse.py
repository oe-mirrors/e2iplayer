# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta

###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import urlparse
try:
    import json
except Exception:
    import simplejson as json
from datetime import datetime, timedelta
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.svt_default_quality = ConfigSelection(default="99999999", choices=[
("0", _("the worst")),
("500", "360p"),
("600", "480p"),
("900", "720p"),
("99999999", _("the best"))
])
config.plugins.iptvplayer.svt_use_default_quality = ConfigYesNo(default=False)
config.plugins.iptvplayer.svt_prefered_format = ConfigSelection(default="hls", choices=[
("hls", _("HLS/m3u8")),
("dash", _("DASH/mpd"))
])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.svt_default_quality))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.svt_use_default_quality))
    optionList.append(getConfigListEntry(_("Preferred format:"), config.plugins.iptvplayer.svt_prefered_format))

    return optionList
###################################################


def gettytul():
    return 'https://svtplay.se/'


class SVTPlaySE(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'SVTPlaySE.tv', 'cookie': 'svtplayse.cookie'})
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.cm.HEADER = self.HEADER # default header
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://www.svtplay.se/'
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/en/5/54/SVT_Play.png'

        self.MAIN_CAT_TAB = [
                             #{'category':'list_items2',        'title': 'POPULÄRT',                            'url':'/populara'        },
                             #{'category':'list_items2',        'title': 'SENASTE PROGRAM',                     'url':'/senaste'         },
                             #{'category':'list_items2',        'title': 'SISTA CHANSEN',                       'url':'/sista-chansen'   },
                             #{'category':'list_items2',        'title': 'LIVESÄNDNINGAR',                      'url':'/live'            },

                             {'category': 'list_items', 'title': _('Popular'), 'url': '/popular'},
                             {'category': 'list_items', 'title': _('Latest programs'), 'url': '/latest'},
                             {'category': 'list_items', 'title': _('Latest news broadcast'), 'url': '/cluster_latest?cluster=nyheter'},
                             {'category': 'list_items', 'title': _('Last chance'), 'url': '/last_chance'},
                             {'category': 'list_items', 'title': _('Live broadcasts'), 'url': '/live'},
                             {'category': 'list_channels', 'title': _('Channels'), 'url': '/kanaler'},
                             {'category': 'list_az_menu', 'title': _('Programs A-Ö'), 'url': '/program'},   #/all_titles
                             {'category': 'list_items', 'title': _('Categories'), 'url': '/active_clusters'},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, 'icon': 'https://raw.githubusercontent.com/vonH/plugin.video.iplayerwww/master/media/search.png'},
                             {'category': 'search_history', 'title': _('Search history'), }]
        self.itemsPerPage = 48
        self.programsAZCache = {'keys': [], 'dict': {}}

    def getFullApiUrl(self, url):
        if url.startswith('/'):
            url = '/api' + url
        return self.getFullUrl(url)

    def getIcon(self, item):
        try:
            url = item.get('poster', '')
            if url == '' or url == None:
                url = item.get('thumbnail', '')
            if url == '' or url == None:
                url = item.get('thumbnailImage', '')
            if url != None and url != '':
                url = url.replace('{format}', 'medium')
        except Exception:
            printExc()
            url = ''
        return str(self.getFullIconUrl(url))

    def listMainMenu(self, cItem, nextCategory):
        printDBG("SVTPlaySE.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listAZMenu(self, cItem, nextCategory):
        self.programsAZCache = {'keys': [], 'dict': {}}

        url = self.getFullUrl(cItem['url'])

        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, "root['__svtplay'] = ", ";\n", withMarkers=False)[1]
        try:
            data = byteify(json.loads(data))
            data = data['programsPage']['alphabeticList']
            for item in data:
                letter = item['letter']
                self.programsAZCache['keys'].append(letter)
                self.programsAZCache['dict'][letter] = []
                for program in item['titles']:
                    self.programsAZCache['dict'][letter].append(program)
        except Exception:
            printExc()

        params = {'good_for_fav': False, 'category': nextCategory, 'title': _('--All--'), 'letters': list(self.programsAZCache['keys'])}
        self.addDir(params)

        for letter in self.programsAZCache['keys']:
            params = {'good_for_fav': False, 'category': nextCategory, 'title': letter, 'letters': [letter]}
            self.addDir(params)

    def listAZ(self, cItem, nextCategory):

        letters = cItem.get('letters', [])
        for letter in letters:
            for item in self.programsAZCache['dict'].get(letter, []):
                try:
                    title = self.cleanHtmlStr(item['programTitle'])
                    url = item['contentUrl']
                    descTab = []
                    if item.get('onlyAvailableInSweden', False):
                        descTab.append(_('Only available in Sweden.'))
                    if item.get('closedCaptioned', False):
                        descTab.append(_('With closed captioned.'))
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': self.getFullUrl(url), 'desc': '[/br]'.join(descTab)})
                    self.addDir(params)
                except Exception:
                    printExc()

    def listChannels(self, cItem):
        url = self.getFullUrl(cItem['url'])

        OFFSET = datetime.now() - datetime.utcnow()

        def _parseDate(dateStr):
            date = datetime.strptime(dateStr[:-7], "%Y-%m-%dT%H:%M:%S")
            offsetDir = dateStr[-6]
            offsetHours = int(dateStr[-5:-3])
            offsetMins = int(dateStr[-2:])
            if offsetDir == "+":
                offsetHours = -offsetHours
                offsetMins = -offsetMins
            utc_date = date + timedelta(hours=offsetHours, minutes=offsetMins) + OFFSET
            if utc_date.time().second == 59:
                utc_date = utc_date + timedelta(0, 1)
            return utc_date

        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, "root['__svtplay'] = ", ";\n", withMarkers=False)[1]
        try:
            data = byteify(json.loads(data))
            for key in data['channelsPage']['schedule']:
                try:
                    item = data['channelsPage']['schedule'][key]
                    if 'channelName' in item and 'channel' in item:
                        if 'poster' in item and self.cm.isValidUrl(str(item['poster'])):
                            icon = item['poster']
                        else:
                            icon = ''

                        # get description
                        descTab = []
                        try:
                            utc_date = _parseDate(item['publishingTime'])
                            if utc_date.day == datetime.now().day:
                                timeHeader = utc_date.strftime('%H:%M:%S')
                            else:
                                timeHeader = utc_date.strftime('%Y-%m-%d %H:%M:%S')
                            descTab.append('%s %s' % (timeHeader, self.cleanHtmlStr(item['programmeTitle'])))
                            desc = self.cleanHtmlStr(item.get('description', ''))
                            if desc != '':
                                descTab.append(desc)
                            descTab.append('')
                        except Exception:
                            printExc()

                        self.addVideo({'title': item['channelName'], 'url': self.getFullUrl('/kanaler/' + item['channel']), 'icon': icon, 'desc': '[/br]'.join(descTab)})
                except Exception:
                    printExc()

        except Exception:
            printExc()

    def listItems(self, cItem, nextCategory):
        printDBG("SVTPlaySE.listItems")

        url = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'page=%s&pageSize=%s' % (page, self.itemsPerPage)

        url = self.getFullApiUrl(url)
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        nextPage = False
        try:
            data = byteify(json.loads(data))

            try:
                if page < data.get('totalPages', 0):
                    nextPage = True
            except Exception:
                pass

            if 'data' in data:
                data = data['data']

            for item in data:
                title = self.cleanHtmlStr(item.get('programTitle', ''))
                url = self.getFullUrl(item['contentUrl'])
                desc = item.get('description', '')
                if desc == None:
                    desc = ''
                else:
                    self.cleanHtmlStr(desc)
                icon = self.getIcon(item)

                descTab = []
                if item.get('onlyAvailableInSweden', False):
                    descTab.append(_('Only available in Sweden.\n'))
                descTab.append(desc)

                if str(item.get('titleType')) == 'SERIES_OR_TV_SHOW':
                    title += ' ' + self.cleanHtmlStr(item.get('title', ''))

                if title == '':
                    title = item.get('name', '')

                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(descTab)}
                #if not item.get('hasEpisodes', False):
                if '/klipp/' in url or '/video/' in url:
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)
        except Exception:
            printExc()

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def explorePage(self, cItem, nextCategory):
        printDBG("SVTPlaySE.explorePage")

        url = self.getFullUrl(cItem['url'])

        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section', '</section>', withMarkers=True)
        for sectionData in tmp:
            m1 = '<h2 class="play_grid'
            if 'sok?q=' in url and m1 in sectionData:
                sections = sectionData.split(m1)
                for idx in range(1, len(sections)):
                    sections[idx] = '<h2 ' + sections[idx]
            else:
                sections = [sectionData]

            for section in sections:
                idx = section.find('<article')
                if idx < 0:
                    continue
                title = section[0:idx]
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(title, '<h2', '</h2>', withMarkers=True)[1])
                if title == '':
                    continue
                articleItems = self.getArticleItems(section[idx:])
                if len(articleItems):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': 'list_section_items', 'title': title, 'article_items': articleItems})
                    self.addDir(params)

        # list tabs if available
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="play_tab-list', '</li>', withMarkers=True)
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if url == '':
                tmp = self.cm.ph.getSearchGroups(item, '''<a[^>]+?id=['"]([^'^"]+?)['"]''')[0].split('-')
                if len(tmp) >= 2:
                    url = '?%s=%s' % (tmp[-1], '-'.join(tmp[0:-1]))
            if url.startswith('?'):
                url = cItem['url'] + url

            params = dict(cItem)
            if 'klip' not in url:
                params['program_title'] = cItem['title']
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listSectionItems(self, cItem, nextCategory):
        printDBG("SVTPlaySE.listSections")

        baseParams = dict(cItem)
        del baseParams['article_items']
        data = cItem.get('article_items', [])
        for item in data:
            params = dict(baseParams)
            params.update(item)
            if params['type'] == 'category':
                params['category'] = nextCategory
            params['good_for_fav'] = True
            self.currList.append(params)

    def getArticleItems(self, data):
        retTab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>', withMarkers=True)
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<h'), re.compile('</h[0-9]>'), withMarkers=True)[1])
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            icon = self.cm.ph.getSearchGroups(item, '''data-src=['"]([^'^"]+?)['"]''')[0]
            if icon == '':
                icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            descTab = []
            if '-geo-block' in item:
                descTab.append(_('Only available in Sweden.'))
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>', withMarkers=True)
            for desc in tmp:
                descTab.append(self.cleanHtmlStr(desc))

            params = {'title': title, 'url': url, 'icon': self.getFullIconUrl(icon), 'desc': '[/br]'.join(descTab)}
            if '/klipp/' in url or '/video/' in url:
                params['type'] = 'video'
            else:
                params['type'] = 'category'
            retTab.append(params)
        return retTab

    def listTabItems(self, cItem, nextCategory):
        printDBG("SVTPlaySE.listTabItems")

        url = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'sida=%s' % (page)

        url = self.getFullUrl(url)
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        # select related section
        sections = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section', '</section>', withMarkers=True)
        sectionIdx = -1
        for idx in range(len(sections)):
            if 'id="related"' in sections[idx]:
                sectionIdx = idx
                break
        if sectionIdx >= 0:
            data = sections[sectionIdx]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="play_tab-list', '</section>', withMarkers=True)[1]

        del sections

        if '' != self.cm.ph.getSearchGroups(data, '''sida=(%s)[^0-9]''' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.getArticleItems(data)
        for item in data:
            params = dict(cItem)
            params.update(item)
            if 'program_title' in cItem and cItem['program_title'] not in params['title']:
                params['title'] = cItem['program_title'] + ' - ' + params['title']
            if params['type'] == 'category':
                params['category'] = nextCategory
            params['good_for_fav'] = True
            self.currList.append(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SVTPlaySE.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        baseUrl = self.getFullUrl('sok?q=' + urllib.quote_plus(searchPattern))
        cItem = dict(cItem)
        cItem['url'] = baseUrl
        self.explorePage(cItem, 'list_tab_items')

    def getLinksForVideo(self, cItem):
        printDBG("SVTPlaySE.getLinksForVideo [%s]" % cItem)
        videoUrls = []

        hlsUrl = cItem.get('hls_url')
        dashUrl = cItem.get('dash_url')

        subtitlesTab = []

        if hlsUrl == None or dashUrl == None:
            if 'api' not in self.up.getDomain(cItem['url']):
                url = self.getFullUrl(cItem['url'])
                sts, data = self.cm.getPage(url, self.defaultParams)
                if not sts:
                    return []
                videoId = self.cm.ph.getSearchGroups(data, '<video\s+?data-video-id="([^"]+?)"')[0]
                url = 'https://api.svt.se/video/' + videoId
            else:
                url = cItem['url']

            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts:
                return []

            printDBG(data)

            try:
                data = byteify(json.loads(data))

                videoItem = data.get('video', None)
                if videoItem == None:
                    videoItem = data
                for item in videoItem['videoReferences']:
                    if self.cm.isValidUrl(item['url']):
                        if 'dashhbbtv' in item['format']:
                            dashUrl = item['url']
                        elif 'hls' in item['format']:
                            hlsUrl = item['url']

                for item in videoItem['subtitleReferences']:
                    format = item['url'][-3:]
                    if format in ['srt', 'vtt']:
                        subtitlesTab.append({'title': format, 'url': self.getFullIconUrl(item['url']), 'lang': 'n/a', 'format': format})
            except Exception:
                printExc()

        tmpTab = []
        if config.plugins.iptvplayer.svt_prefered_format.value == 'hls':
            tmpTab.append(hlsUrl)
            tmpTab.append(dashUrl)
        else:
            tmpTab.append(dashUrl)
            tmpTab.append(hlsUrl)

        max_bitrate = int(config.plugins.iptvplayer.svt_default_quality.value)
        for item in tmpTab:
            if item == '':
                continue
            if item == dashUrl:
                item = getMPDLinksWithMeta(item, False)
            elif item == hlsUrl:
                vidTab = []
                # item = strwithmeta(item, {'X-Forwarded-For':'83.172.75.170'})
                try:
                    tmp = urlparse.urlparse(item)
                    tmp = urlparse.parse_qs(tmp.query)['alt'][0]
                    vidTab = getDirectM3U8Playlist(tmp, False, checkContent=True)
                except Exception:
                    printExc()
                if 0 == len(vidTab):
                    item = getDirectM3U8Playlist(item, False, checkContent=True)
                else:
                    item = vidTab
            else:
                continue

            if len(item):
                def __getLinkQuality(itemLink):
                    try:
                        return int(itemLink['height'])
                    except Exception:
                        return 0
                item = CSelOneLink(item, __getLinkQuality, max_bitrate).getSortedLinks()
                if config.plugins.iptvplayer.svt_use_default_quality.value:
                    videoUrls.append(item[0])
                    break
                videoUrls.extend(item)

        if len(subtitlesTab):
            for idx in range(len(videoUrls)):
                videoUrls[idx]['url'] = strwithmeta(videoUrls[idx]['url'], {'external_sub_tracks': subtitlesTab})
                videoUrls[idx]['need_resolve'] = 0

        return videoUrls

    def getVideoLinks(self, url):
        printDBG("SVTPlaySE.getVideoLinks [%s]" % url)
        retTab = []
        url = strwithmeta(url)
        return retTab

    def getFavouriteData(self, cItem):
        printDBG('SVTPlaySE.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('SVTPlaySE.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('SVTPlaySE.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'url': self.MAIN_URL}, 'list_items')
        elif 'live_streams' == category:
            self.listLive(self.currItem)
        elif 'list_channels' == category:
            self.listChannels(self.currItem)
        elif 'list_channel' == category:
            self.listChannelMenu(self.currItem, 'list_items')
        elif 'list_az_menu' == category:
            self.listAZMenu(self.currItem, 'list_az')
        elif 'list_az' == category:
            self.listAZ(self.currItem, 'explore_page')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'explore_page')
        elif 'explore_page' == category:
            self.explorePage(self.currItem, 'list_tab_items')
        elif 'list_tab_items' == category:
            self.listTabItems(self.currItem, 'explore_page')
        elif 'list_section_items' == category:
            self.listSectionItems(self.currItem, 'explore_page')

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

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SVTPlaySE(), True, [])
