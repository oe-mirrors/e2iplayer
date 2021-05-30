# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from urlparse import urlparse
###################################################


def gettytul():
    return 'http://33sk.tv/'


class C3skTv(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '3sk.tv', 'cookie': '3sk.tv.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://33sk.tv/images/logo-footer.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*'})
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.seasonsCache = {}
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def selectDomain(self):
        domain = 'http://33sk.tv/'
        addParams = dict(self.defaultParams)
        addParams['with_metadata'] = True

        sts, data = self.getPage(domain, addParams)
        if sts:
            self.MAIN_URL = self.cm.getBaseUrl(data.meta['url'])
        else:
            self.MAIN_URL = domain

    def listMainMenu(self, cItem):
        printDBG("C3skTv.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'zone_2'), ('<div', '>', 'banner2'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                nextCategory = ''
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if url == '' or 'pdep43.' in url:
                    continue

                parsedUri = urlparse(url)
                if parsedUri.path == '' and self.cm.isValidUrl(url):
                    url += '/'
                    parsedUri = urlparse(url)

                if 'forumdisplay.php' in url or (parsedUri.path == '/vb' and parsedUri.query == ''):
                    nextCategory = 'list_threads'
                elif '/pdep' in url or (parsedUri.path == '/' and parsedUri.query == ''):
                    nextCategory = 'list_items'
                title = self.cleanHtmlStr(item)
                printDBG(">>>>>>>>>>>>>>>>> title[%s] url[%s] path[%s] query[%s]" % (title, url, parsedUri.path, parsedUri.query))
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                self.addDir(params)
        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("C3skTv.listItems")

        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        currentUrl = data.meta['url']

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</table', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''\shref=['"]([^'^"]*?p%s\.html)['"]''' % (page + 1))[0], currentUrl)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', '"article"'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], currentUrl)
            if url == currentUrl:
                continue

            if 'forumdisplay.php' in url:
                nextCategory = 'list_threads'
            elif 'showthread.php' in url:
                nextCategory = 'list_thread'
            else:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0], currentUrl)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listThreads(self, cItem, nextCategory):
        printDBG("C3skTv.listThreads")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        currentUrl = data.meta['url']

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            if 'vbmenu_option' in item:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], currentUrl)
            if url == currentUrl:
                continue
            #printDBG("++++++++ [%s]" % url)
            if 'forumdisplay.php' in url:
                nextCategory = 'list_threads'
            elif 'showthread.php' in url:
                nextCategory = 'list_thread'
            else:
                continue
            title = self.cleanHtmlStr(item)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0], currentUrl)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon})
            self.addDir(params)

    def listThread(self, cItem):
        printDBG("C3skTv.listThread")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        currentUrl = data.meta['url']
        domain = self.up.getDomain(currentUrl)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'post_message_'), ('<script', '>'), False)[1]
        data = re.compile('''</?br[^>]*?>''').split(data)

        for tmp in data:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<font', '</a>')
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], currentUrl)
                printDBG(">>>>>>>>>>>>>>> " + url)
                tmp = self.cm.getBaseUrl(url)
                if domain in tmp and '/vid/' not in url and '/show/' not in url:
                    continue
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': '%s - %s' % (cItem['title'], title), 'url': url})
                self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("C3skTv.getLinksForVideo [%s]" % cItem)
        videoUrl = cItem['url']
        urlTab = []

        if 1 == self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        if cItem['url'] in self.cacheLinks:
            return self.cacheLinks[videoUrl]

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        currentUrl = data.meta['url']

        if '/vid/' in currentUrl:
            nameMap = {'1': "الاول", '2': "الثانى", '3': "الثالث", '4': "الرابع", '5': "الخامس", '6': "السادس", '7': "السابع", '8': "الثامن"}
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>', caseSensitive=False)
            for idx in range(len(data)):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data[idx], '''\ssrc=['"]([^"^']+?)['"]''', 1, True)[0], currentUrl)
                if url == '':
                    continue
                name = str(idx + 1)
                name = 'الجزء ' + nameMap.get(name, name)
                urlTab.append({'url': url, 'name': name, 'need_resolve': 1})

        if len(urlTab):
            self.cacheLinks[videoUrl] = urlTab

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("C3skTv.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        return self.up.getVideoLinkExt(videoUrl)

    def listSearchResult(self, cItem, searchPattern=None, searchType=None):
        marker = 'google.search.Search.csqr2538'
        page = cItem.get('page', 0)
        if page == 0:
            url = self.getFullUrl('/search.htm?q=%s&btnG=' % urllib.quote(searchPattern))
            sts, data = self.getPage(url)
            if not sts:
                return
            cx = ph.search(data, '''var\s+?cx\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
            url = 'http://cse.google.com/cse.js?cx=' + cx
            sts, data = self.getPage(url)
            if not sts:
                return
            tmp = ph.find(data, ')(', ');', flags=0)[1]
            try:
                tmp = json_loads(tmp)
                url = tmp['protocol'] + '://' + tmp['uds'] + '/' + tmp['loaderPath']
                url += '?autoload=%7B%22modules%22%3A%5B%7B%22name%22%3A%22search%22%2C%22version%22%3A%221.0%22%2C%22callback%22%3A%22__gcse.scb%22%2C%22style%22%3A%22http%3A%2F%2Fwww.google.com%2Fcse%2Fstatic%2Fstyle%2Flook%2Fv2%2Fdefault.css%22%2C%22language%22%3A%22'
                url += tmp['language'] + '%22%7D%5D%7D'
                lang = tmp['language']
                token = tmp['cse_token']
                sts, tmp = self.getPage(url)
                if not sts:
                    return
                hash = ph.search(tmp, '''google\.search\.JSHash\s*?=\s*?['"]([^'^"]+?)['"]''')[0]

                baseUrl = 'https://cse.google.com/cse/element/v1?rsz=filtered_cse&num=10&hl='
                baseUrl += lang + '&source=gcsc&gss=.tv&sig=' + hash + '&start={0}&cx=' + cx
                baseUrl += '&q=dead&safe=off&cse_tok=' + token + '&googlehost=www.google.com&callback=' + marker
            except Exception:
                printExc()
        else:
            baseUrl = cItem['url']

        try:
            url = baseUrl.format(str(page * 10))
            sts, data = self.getPage(url)
            if not sts:
                return

            data = data.strip()
            data = json_loads(data[data.find(marker) + len(marker) + 1:-2])
            for item in data['results']:
                url = item['unescapedUrl']

                if 'forumdisplay.php' in url:
                    nextCategory = 'list_threads'
                elif 'showthread.php' in url:
                    nextCategory = 'list_thread'
                else:
                    continue

                title = item['titleNoFormatting']
                desc = item['contentNoFormatting']

                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': desc}))
            page += 1
            if page * 10 < int(data['cursor']['resultCount']):
                self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'url': baseUrl, 'page': page}))
        except Exception:
            printExc()

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_threads':
            self.listThreads(self.currItem, 'list_thread')
        elif category == 'list_thread':
            self.listThread(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
    #SEARCH
        elif category in ["search"]:
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
        CHostBase.__init__(self, C3skTv(), True, [])
