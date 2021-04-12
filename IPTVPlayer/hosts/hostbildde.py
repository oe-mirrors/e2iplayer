# -*- coding: utf-8 -*-

import requests

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist


DEFAULT_ICON = 'https://bilder.bild.de/fotos/bild-logo-35166394/Bild/45.bild.png'

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Pin protection for plugin")+" :", config.plugins.iptvplayer.Bildde_pin))
    return optionList

def gettytul():
    return 'https://www.bild.de'


class Bildde(CBaseHostClass):

    def __init__(self):

        CBaseHostClass.__init__(self, {'history':'bild.de', 'cookie':'bild.de.cookie'})

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'}

        self.MAIN_URL = 'https://www.bild.de/'

        self.session = None

    def getPage(self, baseUrl):
        if not self.session:
            self.session = requests.Session()
        self.session.headers.update(self.HEADER)
        resp = self.session.get(baseUrl, verify=False)
        return resp.content

    def buildMainCatTab(self):
        urlTab = [
            {'category': 'listCat', 'sub': 'news', 'title': _('News'), 'url': self.getFullUrl('/news'), 'icon': DEFAULT_ICON},
            {'category': 'listCat', 'sub': 'media', 'title': _('Mediathek'), 'url': self.getFullUrl('/video/mediathek'), 'icon': DEFAULT_ICON}]

        return urlTab

    def listCat(self, cItem):
        url = cItem['url']
        sub = cItem['sub']
        data = self.getPage(url)
        if not data:
            return
        sections = self.cm.ph.getAllItemsBeetwenMarkers(data, ('<section', '>'), '</section>', False)
        for section in sections:
            h2 = self.cm.ph.getDataBeetwenMarkers(section, '<h2>', '</h2>', False)[1]

            if 'news' in sub:
                if 'Videos' in h2:
                    pagination = self.cm.ph.getDataBeetwenMarkers(section, ('<div','class="pag"', '>'), '</div>', False)[1]
                    pages = self.cm.ph.getAllItemsBeetwenMarkers(pagination, ('<li', '>'), '</li>', False)
                    for page in pages:
                        href = self.getFullUrl(self.cm.ph.getSearchGroups(page, 'data-ajax-href="([^"]+?)"')[0])
                        data = self.getPage(self.getFullUrl(href))
                        if not data:
                            return
                        for video in self.getVideos(data):
                            self.addVideo(video)
            else:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(h2, ('<a', '>'), '</a>', False)[1])
                href = self.getFullUrl(self.cm.ph.getSearchGroups(h2, 'href="([^"]+?)"')[0])
                if title and href:
                    self.addDir({'category': 'listItems', 'title': title, 'url': href, 'icon': DEFAULT_ICON})

    def listItems(self, cItem):
        printDBG("bildde.listItems citem [%s]" % cItem)

        url = cItem['url']
        data = self.getPage(url)
        if not data:
            return

        for video in self.getVideos(data):
            self.addVideo(video)

        return []

    def getVideos(self, data):
        urltabs = []
        divs = self.cm.ph.getAllItemsBeetwenMarkers(data, ('<div', '>', 'data-tb-region-item='), '</div>', False)
        for div in divs:
            if div:
                a = self.cm.ph.getDataBeetwenMarkers(div, '<a', '</a>', True)[1]
                if 'playerIcon' in a:
                    printDBG("bildde.listItems [a] %s" % a)
                    img = self.cm.ph.getDataBeetwenMarkers(a, '<img',  '/>', False)[1]
                    icon = self.cm.ph.getSearchGroups(img, 'src="([^"]+?.(jpg|png))"')[0]
                    href = self.getFullUrl(self.cm.ph.getSearchGroups(a, 'href="([^"]+?)"')[0])
                    title = self.cm.ph.getSearchGroups(a, 'data-tb-title="([^"]+?)"')[0]

                    if title and href:
                        urltabs.append({'title': title, 'url': href, 'need_resolve': True, 'good_for_fav': True, 'icon': icon})
        return urltabs

    def getLinksForVideo(self, cItem):
        printDBG("bildde.getLinksForVideo cItem [%s]" % cItem)
        urlTab = []

        url = cItem['url']
        data = self.getPage(url)
        if not data:
            return
        meta = self.cm.ph.getDataBeetwenMarkers(data, ('<meta', 'roperty="og:video:url"'),  '/>', False)[1]
        if not meta:
            meta = self.cm.ph.getDataBeetwenMarkers(data, ('<meta', 'roperty="og:video:secure_ur"'),  '/>', False)[1]

        link = self.cm.ph.getSearchGroups(meta, 'content="([^"]+?)"')[0]

        urlTab.append({'name': 'direct', 'url': link, 'need_resolve': 0})

        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):

        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )

        self.currList = []

        #MAIN MENU
        if name is None:
            self.listsTab(self.buildMainCatTab(), {})
        elif category == 'listCat':
            self.listCat(self.currItem)
        elif category == 'listItems':
            self.listItems(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Bildde(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
