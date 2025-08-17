# -*- coding: utf-8 -*-
# Last Modified: 21.06.2025
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return 'https://basketball-video.com/'


class BasketballVideo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'basketball-video.com', 'cookie': 'basketball-video.cookie'})

        self.DEFAULT_ICON_URL = 'https://basketball-video.com/_pu/75/37346371.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0', 'DNT': '1', 'Accept': 'text/html'}
        self.MAIN_URL = 'https://basketball-video.com/'
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        return self.cm.getPage(url, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("BasketballVideo.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'sub_menu', 'title': 'Basketball-Video', 'url': 'https://basketball-video.com/', 'desc': 'https://basketball-video.com/'},
                        {'category': 'sub_menu', 'title': 'MLBLive', 'url': 'https://mlblive.net/', 'desc': 'https://mlblive.net/'},
                        {'category': 'sub_menu', 'title': 'NFL-Video', 'url': 'https://nfl-video.com/', 'desc': 'https://nfl-video.com/'},
                        # {'category': 'sub_menu', 'title': 'Tennis Replays', 'url': 'https://tennisreplays.com/', 'desc': 'https://tennisreplays.com/'},
                        {'category': 'sub_menu', 'title': 'FullRaces', 'url': 'https://fullraces.com/', 'desc': 'https://fullraces.com/'}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubMenu(self, cItem, nextCategory):
        printDBG("BasketballVideo.listSubMenu [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'nav block_elem'), ('</nav', '>'), False)[1]
        sub = self.cm.ph.getAllItemsBeetwenMarkers(tmp, ('<li', '>', 'submenu'), '</ul>')
        for item in sub:
            tmp = tmp.replace(item, '')
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            if '>DCMA<' in item:
                continue
            if '<ul' in item:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<li', '>'), ('</a', '>'), False)[1])
                self.addMarker({'title': title, 'desc': ''})
                item = self.cm.ph.getDataBeetwenNodes(item, ('<ul', '>'), ('</li', '>'), False)[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("BasketballVideo.listItems")

        page = cItem.get('page', 1)
        url = cItem['url'] + '?page{0}'.format(page)
        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'paging'), '</div>')[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, '>(%s)<' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = data.split('<div class="poster">')[1:]
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''\ssrc=['"]([^"^']+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short_descr'), ('</div', '>'), False)[1]).replace('&nbsp;', ' ')
            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addVideo(params)
        if nextPage:
            page += 1
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': cItem['url'], 'page': page})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("BasketballVideo.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="fullstory block_elem"', 'class="full_info block_elem"')[0]
        data = self.cm.ph.getSearchGroups(data, r'''(?:src|href)=['"]([^'^"]+?)['"]\s(?:width|rel)''')

        for url in data:
            url = 'https:' + url if url.startswith('//') else url
            if "gamesontvtoday.com" in url or "nfl-video.com" in url:
                sts, d = self.getPage(url)
                if not sts:
                    continue
                url = self.cm.ph.getSearchGroups(d, 'src="([^"]+)" w')[0]
                url = 'https:' + url if url.startswith('//') else url
            urlTab.append({'name': self.up.getDomain(url), 'url': url, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("BasketballVideo.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BasketballVideo(), True, [])
