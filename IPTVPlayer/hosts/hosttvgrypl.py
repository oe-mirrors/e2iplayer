# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
try:
    import simplejson as json
except Exception:
    import json
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tvgrypl_default_quality = ConfigSelection(default="SD", choices=[("MOB", "MOB: niska"), ("SD", "SD: standardowa"), ("HD", "HD: wysoka")]) #, ("FHD", "FHD: bardzo wysoka")
config.plugins.iptvplayer.tvgrypl_use_dq = ConfigYesNo(default=True)
config.plugins.iptvplayer.tvgrypl_date_of_birth = ConfigText(default="2017-01-31", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Domyślna jakość wideo:", config.plugins.iptvplayer.tvgrypl_default_quality))
    optionList.append(getConfigListEntry("Używaj domyślnej jakości wideo:", config.plugins.iptvplayer.tvgrypl_use_dq))
    optionList.append(getConfigListEntry("Wprowadź datę urodzenia [RRRRR-MM-DD]:", config.plugins.iptvplayer.tvgrypl_date_of_birth))
    return optionList
###################################################


def gettytul():
    return 'https://tvgry.pl/'


class TvGryPL(CBaseHostClass):

    def __init__(self):
        printDBG("TvGryPL.__init__")
        CBaseHostClass.__init__(self, {'history': 'TvGryPL.tv', 'cookie': 'grypl.cookie'})
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://www.gry-online.pl/apple-touch-icon-120x120.png'
        self.MAIN_URL = 'https://tvgry.pl/'
        self.SEARCH_URL = self.getFullUrl('wyszukiwanie.asp')
        self.MAIN_CAT_TAB = [{'category': 'list_tabs', 'title': 'Materiały', 'url': self.getFullUrl('/wideo-tvgry.asp')},
                             {'category': 'list_items', 'title': 'Tematy', 'url': self.getFullUrl('/tematy.asp')},
                             {'category': 'list_tabs', 'title': 'Zwiastuny gier', 'url': self.getFullUrl('/trailery-z-gier.asp')},
                             {'category': 'list_tabs', 'title': 'Zwiastuny filmów', 'url': self.getFullUrl('/trailery-filmowe.asp')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]

    def getPage(self, url, params={}, post_data=None):
        return self.cm.getPage(url, params, post_data)

    def listTabs(self, cItem, post_data=None):
        printDBG("TvGryPL.listTabs")
        tabIdx = cItem.get('tab_idx', 0)
        sts, data = self.getPage(cItem['url'], {}, post_data)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="tvgry-lista-menu', '</div>')[1]
        data = data.split('<br>')
        if tabIdx < len(data):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data[tabIdx], '<a ', '</a>')
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                if self.cm.isValidUrl(url):
                    params = dict(cItem)
                    params.update({'tab_idx': tabIdx + 1, 'title': title, 'url': url})
                    self.addDir(params)

        if 0 == len(self.currList):
            self.listItems(cItem, post_data)

    def listItems(self, cItem, post_data=None):
        printDBG("TvGryPL.listItems")
        page = cItem.get('page', 1)
        url = cItem['url']
        if 1 < page:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'STR=%d' % page

        sts, data = self.getPage(url, {}, post_data)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '-wide">', '<div class="clr">', False)[1]
        data = data.split('<div class="next-prev')

        if len(data) == 2 and '' != self.cm.ph.getSearchGroups(data[1], '''STR=(%s)[^0-9]''' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data[0], '<a ', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p class="tv-box-title"', '</p>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p class="title"', '</p>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])

            descTab = []
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="tv-box-time"', '</div>')[1])
            if tmp != '':
                descTab.append(tmp)
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="tv-box-thumb-c"', '</div>')[1])
            if tmp != '':
                descTab.append(tmp.replace(' ', '/'))
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p class="tv-box-desc"', '</p>')[1])
            if tmp != '':
                descTab.append(tmp)

            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(descTab)}
            if '/wideo.asp' in url:
                self.addVideo(params)
            elif '/temat.asp' in url:
                params.update({'name': 'category', 'category': 'list_tabs'})
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'name': 'category', 'category': 'list_items', 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TvGryPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        baseUrl = 'https://tvgry.pl/wyszukiwanie.asp'
        post_data = {'search': searchPattern}

        cItem = dict(cItem)
        cItem.update({'url': baseUrl})
        self.listItems(cItem, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("TvGryPL.getLinksForVideo [%s]" % cItem)
        allLinksTab = []
        urlTab = []

        rm(self.COOKIE_FILE)

        sts, data = self.getPage(cItem['url'], self.defaultParams) #{'use_cookie':True, 'cookie_items':{'agegate':1}})
        if not sts:
            return urlTab

        ageMarker = '<div class="player-AGEGATE">'
        if ageMarker in data:
            tmp = self.cm.ph.getSearchGroups(config.plugins.iptvplayer.tvgrypl_date_of_birth.value, '''([0-9]{4})[-]?([0-9][0-9]?)[-]?([0-9][0-9]?)''', 3)
            printDBG(">>>>>YEAR[%s] MONTH[%s] DAY[%s]" % (tmp[0], tmp[1], tmp[2]))
            if '' != tmp[0] and '' != tmp[1] and '' != tmp[2]:
                urlParams = dict(self.defaultParams)
                urlParams['header'] = dict(self.AJAX_HEADER)
                urlParams['header']['Referer'] = cItem['url']

                sts, data = self.getPage('https://tvgry.pl/ajax/agegate.asp', urlParams, {'day': int(tmp[2]), 'month': int(tmp[1]), 'year': int(tmp[0])})
                if not sts:
                    return []

                sts, data = self.getPage(cItem['url'], self.defaultParams)
                if not sts:
                    return urlTab

                if ageMarker in data:
                    SetIPTVPlayerLastHostError("Twój wiek nie został poprawnie zweryfikowany przez serwis http://tvgry.pl/.\nSprawdź ustawioną datę urodzenia w konfiguracji hosta.")
            else:
                SetIPTVPlayerLastHostError("Wprowadź datę urodzenia w konfiguracji hosta - wymagane przez serwis http://tvgry.pl/.")

        url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
        if self.cm.isValidUrl(url):
            allLinksTab = self.up.getVideoLinkExt(url)

        urlIDS = []
        urlTemplate = ''
        data = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '{', '}')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''['"]?file['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
            name = self.cm.ph.getSearchGroups(item, '''['"]?label['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
            if self.cm.isValidUrl(url):
                id = self.cm.ph.getSearchGroups(url, '''(/[0-9]+_)[0-9]+''')[0]
                if id != '' and id not in urlIDS:
                    urlIDS.append(id)
                    if urlTemplate == '':
                        urlTemplate = url.replace(id, '{0}')

                q = ""
                if '/500_' in url or "Mobile" in url:
                    q = 'MOB'
                elif '/750_' in url or "SD" in url:
                    q = 'SD'
                elif '/1280_' in url or "720p" in url:
                    q = 'HD'
                if q != '':
                    urlTab.append({'name': name, 'url': strwithmeta(url, {"Range": "bytes=0-"}), 'q': q, 'need_resolve': 0})

        if urlTemplate != '':
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Range'] = "bytes=0-"
            params['max_data_size'] = 0
            params['header'].pop('Accept', None)
            for item in [('/500_', 'MOB'), ('/750_', 'SD'), ('/1280_', 'HD')]:
                if item[0] in urlIDS:
                    continue
                url = urlTemplate.format(item[0])
                sts = self.cm.getPage(url, params)[0]
                if sts and 'mp4' in self.cm.meta.get('content-type', '').lower():
                    urlTab.append({'name': item[1], 'url': strwithmeta(url, {"Range": "bytes=0-"}), 'q': item[1], 'need_resolve': 0})

        if 1 < len(urlTab):
            map = {'MOB': 0, 'SD': 1, 'HD': 2, 'FHD': 3}
            oneLink = CSelOneLink(urlTab, lambda x: map[x['q']], map[config.plugins.iptvplayer.tvgrypl_default_quality.value])
            if config.plugins.iptvplayer.tvgrypl_use_dq.value:
                urlTab = oneLink.getOneLink()
            else:
                urlTab = oneLink.getSortedLinks()

        if 0 == len(urlTab):
            return allLinksTab

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('TvGryPL.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('TvGryPL.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('TvGryPL.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TvGryPL.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #ITEMS
        elif 'list_tabs' == category:
            self.listTabs(self.currItem)
        elif 'list_items' == category:
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, TvGryPL(), True)
