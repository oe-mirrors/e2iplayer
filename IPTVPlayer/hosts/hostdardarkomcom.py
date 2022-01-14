# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

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
    return 'http://dardarkom.com/'


class DardarkomCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '  DardarkomCom.tv', 'cookie': 'dardarkomcom.cookie'})
        self.defaultParams = {'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'http://www.dardarkom.com/'
        self.DEFAULT_ICON_URL = "https://lh5.ggpht.com/xTFuZwF3HX9yPcDhbyCNnjDtZZ1l9qEwUVwoWsPW9Pxry9JsNLSPvWpbvL9waHbHMg=h900"

        self.MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]

        self.cacheLinks = {}

    def listMainMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("DardarkomCom.listFooterMenu")

        mobileSection = ''
        sts, data = self.cm.getPage(self.getMainUrl(), {'header': {'User-Agent': 'Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_0 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7A341 Safari/528.16', 'Accept': 'text/html'}})
        if sts:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'collapsible-header'), ('</ul', '>'))
            if len(data) > 1:
                mobileSection = data[1]
                sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(mobileSection, ('</i', '>'), ('</div', '>'), False)[1])
                mobileSection += '<p>%s</p>' % sTitle

        sts, data = self.cm.getPage(self.getMainUrl())
        if not sts:
            return

        section = self.cm.ph.getDataBeetwenNodes(data, ('<li', '>', 'submenu'), ('</div', '>'))[1]
        sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(section, ('<li', '>'), ('<div', '>'), False)[1])
        section += '<p>%s</p>' % sTitle

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'ft-col'), ('</div', '>'))
        data.insert(0, section)
        data.insert(0, mobileSection)
        for section in data:
            tabItems = []
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<p', '</p>')[1])
            section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<a', '</a>')
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if url == '':
                    continue
                if 'howtowatch.' in url:
                    tabItems = []
                    break
                #if 'series-online' in url:
                #    continue
                if url.endswith('#'):
                    continue
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'title': title, 'category': nextCategory2, 'url': url})
                tabItems.append(params)

            if len(tabItems):
                params = dict(cItem)
                params.update({'title': sTitle, 'category': nextCategory1, 'sub_items': tabItems})
                self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("DardarkomCom.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("DardarkomCom.listItems")
        page = cItem.get('page', 1)
        post_data = cItem.get('post_data', None)
        url = cItem['url']

        attempt = 0
        while attempt < 3:
            attempt += 1
            sts, data = self.cm.getPage(url, {'with_metadata': True, 'ignore_http_code_ranges': [(404, 404), (500, 500)]}, post_data)
            if not sts:
                return
            if sts and 404 == data.meta.get('status_code', 200):
                newUrl = url.replace('/page/%s/' % page, '/page/%s/' % (page + 1))
                if newUrl != url:
                    url = newUrl
                    page += 1
                    continue
            break

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagi-nav'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>{0}</a>'''.format(page + 1))[0]
        if '#' == nextPage:
            if '&' in url and post_data == None:
                nextPage = url.split('&search_start')[0] + '&search_start=%s' % (page + 1)
            elif post_data != None:
                nextPage = url

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'short-poster'), ('<div', '>', 'bottom-nav'))[1]
        if tmp == '':
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'short-poster'), ('<h1', '>'))[1]

        #printDBG(tmp)
        data = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?(:?\.jpe?g|\.png)(:?\?[^'^"]*?)?)['"]''')[0])
            title = ''
            desc = []
            item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', 'short-'), ('</div', '>'))
            for it in item:
                t = self.cleanHtmlStr(it)
                if t == '':
                    continue
                if title == '' and '-title' in it:
                    title = t
                else:
                    desc.append(t)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1, 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSearchItems(self, cItem, nextCategory):
        printDBG("DardarkomCom.listSearchItems")
        page = cItem.get('page', 1)
        post_data = cItem.get('post_data', None)
        url = cItem['url']

        post_data.update({'search_start': page, 'result_from': 12 * (page - 1) + 1})
        sts, data = self.cm.getPage(url, post_data=post_data)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagi-nav'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>{0}</a>'''.format(page + 1))[0]

        #printDBG(data)
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'sres-wrap'), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?(:?\.jpe?g|\.png)(:?\?[^'^"]*?)?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'))[1])

            desc = []
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'sres-date'), ('</div', '>'))[1])
            if tmp != '':
                desc.append(tmp)
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'sres-desc'), ('</div', '>'))[1])
            if tmp != '':
                desc.append(tmp)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addDir(params)

        if '' != nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("DardarkomCom.exploreItem")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']

        trailers = []
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>')
        for server in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(server, '''src=['"]([^'^"]+?)['"]''')[0])
            if 'youtube' in url and url not in trailers:
                trailers.append(url)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Trailer - %s') % cItem['title'], 'url': url, 'trailer': True})
                self.addVideo(params)

        if 'featurelist' in data:
            params = dict(cItem)
            self.addVideo(params)
        else:
            if 'insidelinks' not in data:
                tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'aboveposbut'), ('</div', '>'), False)[1]
                sUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<a[^>]+?href=['"]([^"^']+?)['"]''')[0])
                if sUrl != '':
                    sts, tmp = self.cm.getPage(sUrl)
                    if sts:
                        data = tmp

            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'insidelinks'), ('</ul', '>'), False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            for item in tmp:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<a[^>]+?href=['"](https?://[^"^']+?)['"]''')[0])
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': title, 'episode': True, 'url': url})
                self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("DardarkomCom.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if cItem.get('trailer', False):
            return self.up.getVideoLinkExt(cItem['url'])

        cacheKey = cItem['url']
        urlTab = self.cacheLinks.get(cacheKey, [])
        if len(urlTab):
            return urlTab

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        # get tabs names
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'tabs-sel'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
        tabsNames = []
        for item in tmp:
            tabsNames.append(self.cleanHtmlStr(item))

        printDBG(tabsNames)
        uniqueUrls = []

        if cItem.get('episode', False):
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'fplay tabs-b'), ('<div', '>', 'tabs-sel'), False)[1]
        else:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'fplay tabs-b'), ('<div', '>', 'featurelist'), False)[1]
        data = re.compile('<div[^>]+?fplay tabs\-b[^>]+?>').split(data)
        printDBG(data)
        for idx in range(len(data)):
            if idx < len(tabsNames):
                tabName = self.cleanHtmlStr(tabsNames[idx])
            else:
                tabName = 'ERROR'

            #if 'VIP' in tabName.upper():
            #    # vip links are not supported
            #    continue
            #elif 'باقي المشغلات' in tabName:
            #    # download links not supported
            #    continue
            #else:
            url = ''
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<a', '</a>')
            for server in tmp:
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SERVER: " + server)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(server, '''href=['"]([^'^"]+?\.video/[^'^"]+?)['"]''')[0]) #
                if url == '' or url in uniqueUrls:
                    continue
                name = self.cleanHtmlStr(server)
                urlTab.append({'name': name, 'url': url, 'need_resolve': 1})
                uniqueUrls.append(url)

            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<iframe', '</iframe>')
            for server in tmp:
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SERVER: " + server)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(server, '''src=['"]([^'^"]+?)['"]''')[0])
                if url == '' or url in uniqueUrls or '/templates/' in url:
                    continue
                if 'youtube' in url:
                    name = '[TRAILER]'
                    continue
                else:
                    name = tabName
                urlTab.append({'name': name, 'url': url, 'need_resolve': 1})
                uniqueUrls.append(url)

        if len(urlTab):
            self.cacheLinks[cacheKey] = urlTab

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("DardarkomCom.getVideoLinks [%s]" % videoUrl)

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*** %s ***' % self.cacheLinks[key][idx]['name']
                        break

        m1 = '?s=http'
        if m1 in videoUrl:
            videoUrl = videoUrl[videoUrl.find(m1) + 3:]

        referer = ''
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HEADER)
        urlParams['header']['Referer'] = self.getMainUrl()
        tries = 0
        while 1 != self.up.checkHostSupport(videoUrl) and tries < 5:
            tries += 1
            sts, data = self.cm.getPage(videoUrl, urlParams)
            if not sts:
                return []
            url = ''
            urlTmpTab = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe ', '</iframe>', False, True)
            printDBG(urlTmpTab)
            for urlTmp in urlTmpTab:
                url = self.cm.ph.getSearchGroups(urlTmp, '''location\.href=['"]([^"^']+?)['"]''', 1, True)[0]
                if 'javascript' in url:
                    url = ''
            if url == '':
                url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            if url == '':
                url = self.cm.ph.getSearchGroups(data, '''window\.open\(\s*['"](https?://[^"^']+?)['"]''', 1, True)[0]
            printDBG(url)
            url = self.getFullUrl(url)
            urlParams['header']['Referer'] = videoUrl
            videoUrl = strwithmeta(url, {'Referer': videoUrl})

        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DardarkomCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/index.php?do=search')
        cItem['post_data'] = {'do': 'search', 'subaction': 'search', 'story': searchPattern}
        if cItem.get('page', 1) > 1:
            cItem['post_data']['search_start'] = cItem['page']
        cItem['category'] = 'list_search_items'
        self.listSearchItems(cItem, 'explore_item')

    def getArticleContent(self, cItem):
        printDBG("DardarkomCom.getVideoLinks [%s]" % cItem)
        retTab = []
        itemsList = []

        if 'prev_url' in cItem:
            url = cItem['prev_url']
        else:
            url = cItem['url']

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>', False)[1]
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'fposter'), ('</div', '>'), False)[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h', '>', 's-title'), ('</h', '>'), False)[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'desc'), ('</div', '>'), False)[1])

        tmpTab = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'flist-col'), ('</ul', '>'), False)
        for tmp in tmpTab:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            for item in tmp:
                if 'data-label' in item:
                    item = [self.cm.ph.getSearchGroups(item, '''data\-label=['"]([^'^"]+?)['"]''')[0], item]
                else:
                    item = item.split('</span>', 1)
                    if len(item) < 2:
                        continue
                key = self.cleanHtmlStr(item[0])
                val = self.cleanHtmlStr(item[1])
                if key == '' or val == '':
                    continue
                itemsList.append((key, val))

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

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
            baseItem = {'type': 'category', 'name': 'category'}
            self.listMainMenu(baseItem, 'sub_items', 'list_items')
            self.listsTab(self.MAIN_CAT_TAB, baseItem)
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'list_search_items':
            self.listSearchItems(self.currItem, 'explore_item')
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, DardarkomCom(), True, favouriteTypes=[])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
