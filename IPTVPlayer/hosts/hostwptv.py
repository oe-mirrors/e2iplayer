# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, CSelOneLink
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.wpDefaultformat = ConfigSelection(default="2", choices=[("1", "Niska"), ("2", "Wysoka")])
config.plugins.iptvplayer.wpUseDF = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Domyślny jakość video:", config.plugins.iptvplayer.wpDefaultformat))
    optionList.append(getConfigListEntry("Używaj domyślnej jakości video:", config.plugins.iptvplayer.wpUseDF))
    return optionList
###################################################


def gettytul():
    return 'http://wp.tv/'


class WpTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'WpTV.tv', 'cookie': 'WpTV.cookie'})
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.cm.HEADER = self.HEADER # default header
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'http://wp.tv/'
        self.DEFAULT_ICON_URL = 'http://static.wirtualnemedia.pl/media/top/wp-kanaltv-logo655ciemne.png'

        self.MAIN_CAT_TAB = [{'category': 'list_sections', 'title': _('Main'), 'url': self.MAIN_URL},
                             {'category': 'list_sections', 'title': _('Series'), 'url': self.getFullUrl('seriale')},
                             {'category': 'list_sections', 'title': _('Programs'), 'url': self.getFullUrl('programy')},
                             {'category': 'list_groups', 'title': _('Others'), 'url': self.getFullUrl('inne')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}
                            ]

        self.cacheSections = {}
        self.cacheGroups = {}

    def _getAttrVal(self, data, attr):
        val = self.cm.ph.getSearchGroups(data, '[<\s][^>]*' + attr + '=([^\s^>]+?)[\s>]')[0].strip()
        if len(val) > 2:
            if val[0] in ['"', "'"]:
                val = val[1:]
            if val[-1] in ['"', "'"]:
                val = val[:-1]
            return val
        return ''

    def getSectionItems(self, section):
        sectionItemsTab = []
        tmp = self.cm.ph.rgetAllItemsBeetwenNodes(section, ('</div', '>'), ('<div', '>', 'teaser teaser'))
        if 0 == len(tmp):
            tmp = self.cm.ph.getAllItemsBeetwenNodes(section, ('<a', '>', 'teaser teaser'), ('</a', '>'))
        for item in tmp:
            cat = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<em', '</em>')[1])
            dur = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<time', '</time>')[1])
            des = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'description'), ('</div', '>'))[1])

            url = self.getFullUrl(self._getAttrVal(item, 'href'))
            icon = self._getAttrVal(item, 'src')
            if icon == '' or icon.startswith('data:image'):
                icon = self._getAttrVal(item, 'data-src')
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            if title == '':
                title = self.cleanHtmlStr(self._getAttrVal(item, 'alt'))
            if 'odcinek' in cat.lower():
                title += ' - ' + cat

            if cat != '' and dur != '' and des != '':
                desc = '%s | %s [/br]%s' % (dur, cat, des)
            else:
                desc = self.cleanHtmlStr(item)
            if not self.cm.isValidUrl(url):
                continue
            params = {'title': title, 'url': url, 'icon': self.getFullUrl(icon), 'desc': desc}
            if ',klip.html' in url:
                params['type'] = 'video'
            else:
                params.update({'type': 'category'})
            sectionItemsTab.append(params)
        return sectionItemsTab

    def listSections(self, cItem, nextCategory):
        printDBG("WpTV.listSections cItem[%s] nextCategory[%s]" % (cItem, nextCategory))

        self.cacheSections = {}
        page = cItem.get('page', 1)
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]+?\,page\,%d\,[^'^"]+?)['"]''' % (page + 1))[0])

        titlesTab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section', '</section>')
        for section in data:
            title = self.cm.ph.getDataBeetwenMarkers(section, '<header', '</header>')[1].split('<span')[0]
            title = self.cleanHtmlStr(title)
            itemsTab = self.getSectionItems(section)
            if len(itemsTab):
                self.cacheSections[title] = itemsTab
                titlesTab.append(title)

        if len(titlesTab) > 1:
            for title in titlesTab:
                params = dict(cItem)
                params.update({'title': title, 'category': nextCategory})
                self.addDir(params)
        elif len(titlesTab) == 1:
            params = dict(cItem)
            params.update({'title': titlesTab[0]})
            self.listSectionItems(params, 'list_episodes')

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.pop('good_for_fav', None)
            params.update({'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSectionItems(self, cItem, nextCategory):
        printDBG("WpTV.listSectionItems cItem[%s] nextCategory[%s]" % (cItem, nextCategory))

        key = cItem['title']
        tab = self.cacheSections.get(key, [])
        for params in tab:
            params = dict(params)
            params.update({'good_for_fav': True})
            if params['type'] != 'video':
                params.update({'category': nextCategory})
                self.addDir(params)
            else:
                self.addVideo(params)

    def listGroups(self, cItem, nextCategory):
        printDBG("WpTV.listGroups cItem[%s] nextCategory[%s]" % (cItem, nextCategory))

        self.cacheGroups = {}

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        titlesTab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="others__cols', '</ul>')
        for group in data:
            groupTitle = self.cm.ph.getDataBeetwenMarkers(group, '<header', '</header>')[1].split('<span')[0]
            groupTitle = self.cleanHtmlStr(groupTitle)
            itemTab = []
            group = self.cm.ph.getAllItemsBeetwenMarkers(group, '<li', '</li>')
            for item in group:
                url = self.getFullUrl(self._getAttrVal(item, 'href'))
                title = self.cleanHtmlStr(item)
                itemTab.append({'title': title, 'url': url})

            if len(itemTab):
                self.cacheGroups[groupTitle] = itemTab
                params = dict(cItem)
                params.update({'title': groupTitle, 'category': nextCategory})
                self.addDir(params)

    def listGroupItems(self, cItem, nextCategory):
        printDBG("WpTV.listGroupItems cItem[%s] nextCategory[%s]" % (cItem, nextCategory))
        key = cItem['title']
        tab = self.cacheGroups.get(key, [])

        cItem = dict(cItem)
        cItem.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(tab, cItem)

    def listEpisodes(self, cItem):
        printDBG("WpTV.listEpisodes")

        page = cItem.get('page', 1)
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]+?\,page\,%d\,[^'^"]+?)['"]''' % (page + 1))[0])
        mainDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<main class="main-content"', '</p>')[1])

        if page == 1:
            trailerData = self.cm.ph.getDataBeetwenMarkers(data, '<a class="see-trailer"', '</a>', withMarkers=True)[1]
            trailerTitle = '{0} - {1}'.format(cItem['title'], self.cleanHtmlStr(trailerData))
            trailerUrl = self.getFullUrl(self._getAttrVal(trailerData, 'href'))
            if self.cm.isValidUrl(trailerUrl) and ',klip.html' in trailerUrl:
                params = {'good_for_fav': True, 'url': trailerUrl, 'title': trailerTitle, 'icon': cItem.get('icon', ''), 'desc': mainDesc}
                self.addVideo(params)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section', '</section>')
        for section in data:
            if 'Zobacz także' in section:
                continue
            itemsTab = self.getSectionItems(section)
            for item in itemsTab:
                item.update({'good_for_fav': True, 'desc': item['desc'] + '[/br]' + mainDesc}) #, 'title':item['desc']
                self.addVideo(item)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.pop('good_for_fav', None)
            params.update({'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WpTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        cItem = dict(cItem)
        page = cItem.get('page', 1)
        if page == 1:
            cItem['url'] = self.getFullUrl('/query,%s,szukaj.html?' % urllib_quote(searchPattern))
        self.listEpisodes(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("WpTV.getLinksForVideo [%s]" % cItem)
        urlTab = []

        rm(self.COOKIE_FILE)
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        vidId = self.cm.ph.getSearchGroups(data, 'data-mid="([^"]+?)"')[0]
        vidUrl = self.MAIN_URL + "player/mid,%s,embed.json" % vidId
        try:
            sts, data = self.cm.getPage(vidUrl, self.defaultParams)
            if not sts:
                return []

            tmpTab = []
            qMap = {"HQ": '2', "LQ": '1'}
            data = byteify(json.loads(data))
            for item in data['clip']['url']:
                if 'mp4' not in item['type']:
                    continue
                urlTab.append({'name': item['quality'] + ' ' + item['type'], 'url': self.getFullUrl(item['url']), 'quality': qMap.get(item['quality'], '3'), 'need_resolve': 0})

            if 0 < len(urlTab):
                max_bitrate = int(config.plugins.iptvplayer.wpDefaultformat.value)

                def __getLinkQuality(itemLink):
                    if 'mobile' in itemLink['name']:
                        return 0
                    return int(itemLink['quality'])
                urlTab = CSelOneLink(urlTab, __getLinkQuality, max_bitrate).getSortedLinks()
                if config.plugins.iptvplayer.wpUseDF.value:
                    urlTab = [urlTab[0]]
        except Exception:
            printExc()
        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('WpTV.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('WpTV.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('WpTV.setInitListFromFavouriteItem')
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
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'list_sections' == category:
            self.listSections(self.currItem, 'list_section_items')
        elif 'list_section_items' == category:
            self.listSectionItems(self.currItem, 'list_episodes')
        elif 'list_groups' == category:
            self.listGroups(self.currItem, 'list_group_items')
        elif 'list_group_items' == category:
            self.listGroupItems(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, WpTV(), True, [])
