# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'http://bajeczki.org/'


class BajeczkiOrg(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'bajeczki.org', 'cookie': 'bajeczki.org.cookie'})
        self.MAIN_URL = 'http://bajeczki.org/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/wp-content/uploads/1397134512_5b47d5c61cb3523b0ff67e3168ded910-1-640x360.jpg')
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheLinks = {}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category': 'categories', 'title': 'Wszystkie bajki', 'url': self.getFullUrl('/all-categories/')},
                        {'category': 'list_items', 'title': 'Ostatnio dodane', 'url': self.getFullUrl('/?s=')},
                        {'category': 'list_items', 'title': 'Filmy', 'url': self.getFullUrl('/pelnometrazowe/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("BajeczkiOrg.listCategories")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'category-bar'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            item = item.split('</span>', 1)
            title = ph.clean_html(item[0])
            desc = ph.clean_html(item[-1])
            icon = url + '?fake=need_resolve.jpeg'
            params = dict(cItem)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("BajeczkiOrg.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        nextPage = ph.find(data, ('<a', '>', 'next page-'))[1]
        nextPage = self.getFullUrl(ph.getattr(nextPage, 'href'), self.cm.meta['url'])

        descObj = re.compile('''<span[^>]+?>''')
        data = ph.find(data, '<main', '</main>', flags=0)[1]
        printDBG(data)
        data = re.compile('<(?:div|article)[^>]+?hentry[^>]+?>').split(data)
        for idx in range(1, len(data), 1):
            item = data[idx]

            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
            if url == '':
                continue
#            icon = self.getFullUrl( ph.search(item, ph.IMAGE_SRC_URI_RE)[1] )
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data-src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            item = item.split('</h2>', 1)
            title = ph.clean_html(item[0])

            desc = []
            tmp = descObj.split(item[-1])
            for t in tmp:
                t = ph.clean_html(t)
                if t != '':
                    desc.append(t)
            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
            self.addVideo(params)

        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'url': nextPage}))

    def listSubItems(self, cItem):
        printDBG("BajeczkiOrg.listSubItems")
        self.currList = cItem['sub_items']

    def getLinksForVideo(self, cItem):
        printDBG("BajeczkiOrg.getLinksForVideo [%s]" % cItem)
        urlTab = self.cacheLinks.get(cItem['url'], [])
        if urlTab:
            return urlTab

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'entry-content'), ('<aside', '>'))[1]
        data = re.sub("<!--[\s\S]*?-->", "", data)

        tmp = ph.find(data, '<video', '</video>', flags=ph.IGNORECASE)[1]
        tmp = ph.findall(tmp, '<source', '>', flags=ph.IGNORECASE)
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            type = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''', ignoreCase=True)[0].lower()
            if 'mp4' in type:
                name = self.up.getDomain(url)
                urlTab.append({'name': name, 'url': strwithmeta(url, {'direct_link': True, 'Referer': self.cm.meta['url']}), 'need_resolve': 1})

        tmp = ph.findall(data, ('<div', '>', 'data-item'), flags=ph.IGNORECASE | ph.START_E)
        for item in tmp:
            if 'sources' not in item:
                continue
            item = ph.clean_html(ph.getattr(item, 'data-item'))
            try:
                item = json_loads(item)
                for it in item['sources']:
                    it['type'] = it.get('type', it['src'].split('?', 1)[0].rsplit('.', 1)[-1]).lower()
                    url = strwithmeta(it['src'], {'direct_link': True, 'Referer': self.cm.meta['url']})
                    if 'mp4' in it['type']:
                        urlTab.append({'name': it['type'], 'url': url, 'need_resolve': 1})
                    elif 'mpeg' in it['type']:
                        urlTab.extend(getDirectM3U8Playlist(url))
            except Exception:
                printExc()

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>', caseSensitive=False)
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            if 1 == self.up.checkHostSupport(url):
                name = self.up.getDomain(url)
                urlTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})

        if not urlTab:
            unique = set()
            data = re.compile('''['">]\s*?(https?://[^'^"^<]*?/watch\?v=[^'^"]+?)\s*?[<'"]''').findall(data)
            for url in data:
                if url not in unique:
                    urlTab.append({'name': 'Youtube', 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})
                    unique.add(url)

        if urlTab:
            self.cacheLinks[cItem['url']] = urlTab

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("BajeczkiOrg.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
        if videoUrl.meta.get('direct_link'):
            return [{'name': 'direct', 'url': videoUrl}]
        urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmeHD.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({'category': 'list_items', 'url': self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)})
        self.listItems(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
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
        CHostBase.__init__(self, BajeczkiOrg(), True, [])
