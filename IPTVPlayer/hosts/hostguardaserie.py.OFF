# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://www.guardaserie.digital/'


class GuardaSerieClick(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'guardaserie.click', 'cookie': 'guardaserie.click.cookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = MergeDicts(self.HEADER, {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://www.guardaserie.digital/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/wp-content/themes/guardaserie/images/logogd.png')

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'domain': 'guardaserie.digital', 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("GuardaSerieClick.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        item = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'lista-serie'), ('</a', '>'))[1]
        title = self.cleanHtmlStr(item)
        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
        params = dict(cItem)
        params.update({'name': 'category', 'category': 'sections', 'title': title, 'url': url})
        self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'dropdown'), ('</ul', '>'))[1].split('<ul', 1)
        sTitle = self.cleanHtmlStr(data[0])
        subtItems = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data[-1], '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'name': 'category', 'category': 'list_items', 'title': title, 'url': url})
            subtItems.append(params)

        params = dict(cItem)
        params.update({'name': 'category', 'category': 'sub_items', 'sub_items': subtItems, 'title': sTitle})
        self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def getSeriesItems(self, cItem, nextCategory, rawItems):
        printDBG("GuardaSerieClick.listItems")
        items = []
        for item in rawItems:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            if title == '':
                continue
            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '' and 'star' not in t:
                    desc.append(t)
            try:
                item = self.cm.ph.getSearchGroups(item, '''star\s*?s([0-5][^'^"]*?)['"]''')[0].split('_', 1)
                star = str(int(item[0]))
                if 'half' in item[-1]:
                    star += '.5'
                else:
                    star += '.0'
                desc.append(star)
            except Exception:
                printExc()
            params = dict(cItem)
            params.update({'name': 'category', 'category': nextCategory, 'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
            items.append(params)
        return items

    def listSections(self, cItem, nextCategory):
        printDBG("GuardaSerieClick.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        marker = 'container-fluid greybg followMeBar containerTopBarTitle'
        data = self.cm.ph.getDataBeetwenMarkers(data, marker, 'container-foote', False)[1].split(marker)
        for sData in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(sData, '<h2', '</h2>')[1])
            subtItems = self.getSeriesItems(cItem, nextCategory, self.cm.ph.getAllItemsBeetwenMarkers(sData, '<a', '</a>'))
            if len(subtItems):
                params = dict(cItem)
                params.update({'name': 'category', 'category': 'sub_items', 'sub_items': subtItems, 'title': sTitle})
                self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("GuardaSerieClick.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenMarkers(data, 'box-container', 'container-foote', False)[1]
        self.currList = self.getSeriesItems(cItem, nextCategory, self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>'))

    def exploreItem(self, cItem):
        printDBG("GuardaSerieClick.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']

        reObj = re.compile('''meta\-embed[0-9]*?=['"]([^'^"]+?)['"]''')
        marker = 'stagioni row-stagione-'
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', marker), ('<div', '>', 'container'), False)[1].split(marker)
        for sData in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(sData, '<h2', '</h2>')[1])
            subtItems = []
            data = self.cm.ph.getAllItemsBeetwenMarkers(sData, '<a', '</a>')
            for item in data:
                title = '%s - %s' % (cItem['title'], self.cleanHtmlStr(item.split('<p', 1)[0]))
                icon = self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0]
                if icon == '':
                    icon = self.cm.ph.getSearchGroups(item, '''<img[^>]+?data\-original=['"]([^"^']+?)['"]''')[0]
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'desc'), ('</p', '>'))[1])
                season = self.cm.ph.getSearchGroups(item, '''meta\-stag=['"]([^"^']+?)['"]''')[0]
                episode = self.cm.ph.getSearchGroups(item, '''meta\-ep=['"]([^"^']+?)['"]''')[0]
                params = dict(cItem)
                params.update({'type': 'video', 'good_for_fav': False, 'title': title, 'urls': reObj.findall(item), 'url': cItem['url'] + '?s={0}&e={1}'.format(season, episode), 'desc': desc, 'icon': self.getFullIconUrl(icon)})
                subtItems.append(params)

            params = dict(cItem)
            params.update({'name': 'category', 'category': 'sub_items', 'sub_items': subtItems, 'good_for_fav': False, 'title': sTitle})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GuardaSerieClick.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib_quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("GuardaSerieClick.getLinksForVideo [%s]" % cItem)
        urlsTab = []
        for item in cItem['urls']:
            urlsTab.append({'name': self.cm.getBaseUrl(item, True), 'url': self.getFullUrl(item), 'need_resolve': 1})
        return urlsTab

    def getVideoLinks(self, videoUrl):
        printDBG("GuardaSerieClick.getVideoLinks [%s]" % videoUrl)
        if 0 == self.up.checkHostSupport(videoUrl):
            url = ''
            sts, data = self.cm.getPage(videoUrl)
            if sts:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if url == '':
                videoUrl = 'http://www.safersurf.org/browse.php?u={0}&b=8&f=norefer'.format(urllib_quote_plus(videoUrl, ''))
                params = dict(self.defaultParams)
                params['header'] = MergeDicts(params['header'], {'Referer': videoUrl})
                sts, data = self.cm.getPage(videoUrl, params)
                if sts:
                    printDBG(data)
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                    url = urllib_unquote(self.cm.ph.getDataBeetwenMarkers(url, '?u=', '&', False)[1])

            if url != '':
                videoUrl = url
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("GuardaSerieClick.getVideoLinks [%s]" % cItem)
        retTab = []
        itemsList = []

        if 'prev_url' in cItem:
            url = cItem['prev_url']
        else:
            url = cItem['url']

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'container-title-single'), ('<input', '>'), False)[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h', '>'), ('</h', '>'), False)[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'desc'), ('</span', '>'), False)[1])

        try:
            tmp = self.cm.ph.getSearchGroups(data, '''star\s*?s([0-5][^'^"]*?)['"]''')[0].split('_', 1)
            star = str(int(tmp[0]))
            if 'half' in tmp[-1]:
                star += '.5'
            else:
                star += '.0'
            if star != '':
                itemsList.append((_('RATING'), star))
        except Exception:
            printExc()

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<p', '>', 'details'), ('</p', '>'), False)
        for item in tmp:
            item = item.split('</b>', 1)
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0])
            val = self.cleanHtmlStr(item[1])
            if key == '' or val == '':
                continue
            itemsList.append((key, val))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'type': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
        elif category == 'sections':
            self.listSections(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_abc_items')
        elif category == 'list_abc_items':
            self.listABCItems(self.currItem, 'explore_item')
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
        CHostBase.__init__(self, GuardaSerieClick(), True, favouriteTypes=[])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
