# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://rte.ie/player'


class RteIE(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'RteIE.tv', 'cookie': 'rte.ie.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://pbs.twimg.com/profile_images/533371112277557248/iJ7Xwp1i.png'
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def selectDomain(self):

        if self.MAIN_URL == None:
            self.MAIN_URL = 'http://www.rte.ie/'

        self.MAIN_CAT_TAB = [{'category': 'list_live', 'title': _('Live'), 'url': self.getFullUrl('player/live')},
                             {'category': 'list_categories', 'title': _('Programmes'), 'url': self.getFullUrl('/player/date/latest/')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def _getIdFromUrl(self, url):
        if '/live/' in url:
            chid = self.cm.ph.getSearchGroups(url, r'https?://(?:www\.)?rte\.ie/player/[^/]{2,3}/live/([0-9]+)')[0]
        else:
            chid = self.cm.ph.getSearchGroups(url, r'https?://(?:www\.)?rte\.ie/player/[^/]{2,3}/show/[^/]+/([0-9]+)')[0]
        printDBG("_getIdFromUrl url[%s] -> chid[%s]" % (url, chid))
        return chid

    def listLiveChannels(self, cItem):
        printDBG("RteIE.listLiveChannels")

        descMap = {}
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="top-live-schedule">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0])
            tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(item, '</span>', '<span class')
            if 0 == len(tmp):
                continue
            title = self.cleanHtmlStr(tmp[0])
            descTab = []
            for desc in tmp[1:]:
                desc = self.cleanHtmlStr(desc)
                if len(desc):
                    descTab.append(desc)
            chId = self._getIdFromUrl(url)
            descMap[chId] = {'title': title, 'url': url, 'desc': '[/br]'.join(descTab)}

        printDBG(descMap)

        for item in [{'ch_id': '8', 'title': 'RTÉ One'}, {'ch_id': '10', 'title': 'RTÉ2'}, {'ch_id': '6', 'title': 'RTÉjr'}, {'ch_id': '7', 'title': 'RTÉ News Now'}]:
            params = dict(item)
            params['good_for_fav'] = True
            params['url'] = self.getFullUrl('/player/ie/live/%s/' % item['ch_id'])
            params.update(descMap.get(item['ch_id'], {}))
            self.addVideo(params)

    def listCategories(self, cItem, nextCategory):
        printDBG("RteIE.listCategories")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        calendarTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<section class="sidebar-content-box', '<table class="calendar">')[1])

        data = self.cm.ph.getDataBeetwenMarkers(data, 'dropdown-programmes', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0])
            title = self.cleanHtmlStr(item)

            if '/a-z/' in url:
                category = 'list_az'
            else:
                category = nextCategory
            params = {'good_for_fav': False, 'category': category, 'title': title, 'url': url}
            self.addDir(params)

        if calendarTitle != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': 'list_calendar', 'title': calendarTitle})
            self.addDir(params)

    def listAZ(self, cItem, nextCategory):
        printDBG("RteIE.listAZ")
        self._listFilters(cItem, nextCategory, '<table class="a-to-z">')

    def listCalendar(self, cItem, nextCategory):
        printDBG("RteIE.listCalendar")
        self._listFilters(cItem, nextCategory, '<table class="calendar">')

    def _listFilters(self, cItem, nextCategory, marker):

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, marker, '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<td', '</td>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = url.split('/')[-2] #self.cleanHtmlStr(item)
            params = dict(cItem)
            params = {'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url}
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("RteIE.listItems |%s|" % cItem)

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        if '/show/' in cItem['url']:
            episodes = True
        else:
            episodes = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section class="main-content-box-', '</section>')
        if len(data) == 1:
            data = data[0]
        elif len(data) > 1:
            tmp = data
            data = ''
            for item in tmp:
                tmpTitle = self.cm.ph.getDataBeetwenMarkers(item, '<header', '</header>')[1]
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> " + tmpTitle)
                if 'Episodes' in tmpTitle:
                    episodes = True
                    data = item
                    break
            del tmp
        else:
            data = ''

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            if '/search/' not in cItem['url']:
                titleTab = []
                if episodes:
                    tmp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
                    if tmp != '':
                        titleTab.append(tmp)
                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="thumbnail-title">', '</span>')[1])
                if tmp != '' and tmp not in titleTab:
                    titleTab.append(tmp)
                title = ' '.join(titleTab)
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="thumbnail-date">', '</span>')[1])
            else:
                tmp = item.split('</h3>')
                title = self.cleanHtmlStr(tmp[0])
                desc = self.cleanHtmlStr(tmp[-1])

            params = dict(cItem)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': desc, 'icon': icon}
            if episodes:
                self.addVideo(params)
            else:
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/player/search/?q=' + urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'list_items')

    def getLinksForVideo(self, cItem):
        printDBG("RteIE.getLinksForVideo [%s]" % cItem)

        linksTab = []
        hlsLinksTab = []
        hdsLinksTab = []
        hdsUrl = ''

        id = self._getIdFromUrl(cItem['url'])
        if id == '':
            return []

        if '/show/' in cItem['url']:
            try:
                sts, data = self.cm.getPage('http://feeds.rasset.ie/rteavgen/player/playlist/?type=iptv&format=json&showId=' + id, self.defaultParams)
                data = byteify(json.loads(data))['shows'][0]["media:group"][0]
                hdsUrl = data['rte:server'] + data['url']
            except Exception:
                printExc()
        elif '/live/' in cItem['url']:

            idsMap = {'8': 'rte1', '10': 'rte2', '6': 'rtejr', '7': 'newsnow'}
            hdsUrl = self.getFullUrl('/manifests/%s.f4m' % idsMap.get(id, ''))

        if self.cm.isValidUrl(hdsUrl):
            try:
                tmpLinksTab = getF4MLinksWithMeta(hdsUrl)[::-1]
                for item in tmpLinksTab:
                    item['name'] = '[f4m/hds] %sk' % item.get('bitrate', item['name'])
                    hdsLinksTab.append(item)

                    if ('/hds-vod/' in item['url'] or '/hds-live/' in item['url']) and item['url'].endswith('.f4m'):
                        hlsUrl = item['url'].replace('/hds-vod/', '/hls-vod/').replace('/hds-live/', '/hls-live/')[:-3] + 'm3u8'
                        hlsUrl = strwithmeta(hlsUrl, {'Referer': cItem['url'], 'User-Agent': self.USER_AGENT})
                        tmp = getDirectM3U8Playlist(hlsUrl, checkContent=True)
                        if 1 == len(tmp):
                            tmp[0]['name'] = '[m3u8/hls] %sk' % item.get('bitrate', item['name'])
                            hlsLinksTab.append(tmp[0])
            except Exception:
                printExc()

        linksTab.extend(hlsLinksTab)
        #if 0 == len(linksTab):
        linksTab.extend(hdsLinksTab)

        return linksTab

    def getArticleContent(self, cItem):
        printDBG("RteIE.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}
        title = ''
        desc = ''
        icon = ''

        if '/show/' in cItem['url']:
            id = self.cm.ph.getSearchGroups(cItem['url'], r'https?://(?:www\.)?rte\.ie/player/[^/]{2,3}/show/[^/]+/([0-9]+)')[0]
            if id == '':
                return []
            live = False
        elif '/live/' in cItem['url']:
            id = self.cm.ph.getSearchGroups(cItem['url'], r'https?://(?:www\.)?rte\.ie/player/[^/]{2,3}/live/([0-9]+)')[0]
            if id == '':
                return []
            live = True

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        if live:
            # prepare idsMap
            idsMap = {}
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="top-live-schedule">', '</ul>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')

            for idx in range(len(tmp)):
                chId = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[idx], '''href=['"]([^"^']+)['"]''')[0])
                chId = self._getIdFromUrl(chId)
                idsMap[chId] = idx

            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<dl class="sidebar-live-schedule-list">', '</dl>')
            dataId = idsMap.get(id, -1)
            if dataId >= 0 and dataId < len(data):
                descTab = []
                data = data[dataId]
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<dt>', '</dd>')
                for event in data:
                    event = self.cm.ph.getAllItemsBeetwenMarkers(event, '>', '<', False)
                    for item in event:
                        item = self.cleanHtmlStr(item)
                        if item != '':
                            descTab.append(item)
                    descTab.append("")
                desc = '[/br]'.join(descTab)
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<article class="video-content"', '</article>')[1]

            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<h2[^>]+?"description"[^>]*?>'), re.compile('</h2>'))[1])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<h1[^>]+?"name"[^>]*?>'), re.compile('</h1>'))[1])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+)['"]''')[0])

            otherInfo = {}
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Duration</strong>', '</li>', False, False)[1])
            if tmp != '':
                otherInfo['duration'] = tmp

            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Broadcast</strong>', '</li>', False, False)[1])
            if tmp != '':
                otherInfo['broadcast'] = tmp

            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'remaining</strong>', '</li>', False, False)[1])
            if tmp != '':
                otherInfo['remaining'] = tmp

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        self.informAboutGeoBlockingIfNeeded('IE')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_live':
            self.listLiveChannels(self.currItem)
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_az':
            self.listAZ(self.currItem, 'list_items')
        elif category == 'list_calendar':
            self.listCalendar(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_items')
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
        CHostBase.__init__(self, RteIE(), True, [])

    def withArticleContent(self, cItem):
        if '/show/' not in cItem.get('url', '') and '/live/' not in cItem.get('url', ''):
            return False
        return True
