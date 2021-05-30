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
import urlparse
import time
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://shahiid-anime.net/'


class ShahiidAnime(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'shahiid-anime.net.to', 'cookie': 'shahiid-anime.net.cookie'})
        self.DEFAULT_ICON_URL = 'https://www.shahiid-anime.net/wp-content/uploads/shahiid-anime-1.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www.shahiid-anime.net/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'raw_post_data': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'list_filters', 'title': _('Anime list'), 'url': self.getFullUrl('/filter'), },
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def fillCacheFilters(self, cItem):
        printDBG("ShahiidAnime.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title.lower() in ['all', 'default', 'any']:
                    addAll = False
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<select', '>', 'Select2'), ('</', 'select>'))
        for tmp in data:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            addFilter(tmp, 'value', key)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("ShahiidAnime.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listMainMenu(self, cItem, nextCategory):
        printDBG("ShahiidAnime.listMainMenu")

        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("ShahiidAnime.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        url = cItem['url']
        if page > 1:
            url += '/page/%s/' % page

        query = {}
        keys = list(self.cacheFiltersKeys)
        keys.append('f_s')
        for key in keys:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = cItem[key]
        query = urllib.urlencode(query)
        if query != '':
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getAllItemsBeetwenNodes(data, ('<nav ', '>', 'pagination'), ('</nav', '>'), False, numNodes=1)
        if len(nextPage) and ('/page/%s/' % (page + 1)) in nextPage[0]:
            nextPage = True
        else:
            nextPage = False

        splitObj = re.compile('''<div[^>]+?class=['"]online\-block['"][^>]*?>''')
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div ', '>', 'online-block'), ('<div', '>', 'clear:'), False)
        for dat in data:
            dat = splitObj.split(dat)
            for item in dat:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                descTab = []
                desc = ''
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div', '</div>')
                for it in tmp:
                    val = self.cleanHtmlStr(it).replace(' , ', ', ')
                    if val != '':
                        if '"title' in it or 'title"' in it:
                            continue
                        elif '"story"' in it:
                            desc = val
                        else:
                            descTab.append(val)
                desc = ' | '.join(descTab) + '[/br]' + desc
                params = dict(cItem)
                params.pop('page', None)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("ShahiidAnime.exploreItem")

        page = cItem.get('page', 1)

        url = cItem['url']
        if url.endswith('/'):
            url = url[:-1]
        if page > 1:
            url += '/page/%s/' % page

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div ', '>', 'pagination'), ('</div', '>'), False)[1]
        if ('/page/%s/' % (page + 1)) in nextPage:
            nextPage = True
        else:
            nextPage = False

        if page == 1:
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div ', '>', 'imgboxsinpost'), ('</div', '>'), False)
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                title = self.cleanHtmlStr(item)
                if title == '':
                    title = _('Trailer')
                title = cItem['title'] + (' [%s]' % title)
                if 1 == self.up.checkHostSupport(url):
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title': title, 'url': url})
                    self.addVideo(params)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div ', '>', 'online-block'), ('</a', '>'), False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            try:
                title = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(item, ('<div ', '>', 'title-online'), ('</div', '>'), False, numNodes=1)[0])
            except Exception:
                continue
            try:
                title += ' - ' + self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(item, ('<div ', '>', 'numepisode'), ('</div', '>'), False, numNodes=1)[0])
            except Exception:
                pass

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon})
            self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShahiidAnime.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['f_s'] = searchPattern
        cItem['url'] = self.getMainUrl()
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("ShahiidAnime.getLinksForVideo [%s]" % cItem)
        retTab = []
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul ', '>', 'server-position'), ('</ul', '>'), False)
        for dat in data:
            dat = self.cm.ph.getAllItemsBeetwenMarkers(dat, '<li', '</li>')
            for item in dat:
                dataId = self.cm.ph.getSearchGroups(item, '''\s=['"]([^'^"]+?)['"]''')[0]
                dataType = self.cm.ph.getSearchGroups(item, '''\sdata\-type=['"]([^'^"]+?)['"]''')[0]
                dataCode = self.cm.ph.getSearchGroups(item, '''\sdata\-code=['"]([^'^"]+?)['"]''')[0]
                id = self.cm.ph.getSearchGroups(item, '''\sid=['"]([^'^"]+?)['"]''')[0]
                name = self.cleanHtmlStr(item)
                url = '%s|%s|%s|%s' % (dataId, dataType, dataCode, id)
                retTab.append({'name': name, 'url': url, 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab

        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("ShahiidAnime.getVideoLinks [%s]" % videoUrl)
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
        data = videoUrl.split('|')
        query = {'action': 'play_video', 'code': data[2], 'type': data[1], '_': str(int(time.time() * 1000))}
        query = urllib.urlencode(query)
        url = self.getFullUrl('?' + query)

        sts, data = self.getPage(url)
        if not sts:
            return []

        palyerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        if 1 == self.up.checkHostSupport(palyerUrl):
            urlTab = self.up.getVideoLinkExt(palyerUrl)
            if 0 == len(urlTab) and '--' in palyerUrl:
                # try to fix broken link
                urlTab = self.up.getVideoLinkExt(palyerUrl.replace('--', '-'))

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("ShahiidAnime.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        tmp = ''.join(self.cm.ph.getAllItemsBeetwenMarkers(data, '<h5', '</h5>'))
        try:
            title = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(data, ('<h3', '>', 'entry-title'), ('</h3', '>'), numNodes=1)[0])
        except Exception:
            title = ''
        desc = self.cleanHtmlStr(tmp)
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tmp, '''src=['"]([^'^"]+?)['"]''')[0])

        keysMap = {'الأسم بالعربى': 'alternate_title',
                   'عدد الحلقات': 'episodes',
                   'النوع': 'type',
                   'المنتج': 'production',
                   'تاريخ الأنتاج': 'released',
                   'الحالة': 'status',
                   'التصنيف': 'genres', }

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>', 'class="name"'), ('</div', '>'))
        for item in data:
            item = item.split('</span>', 1)
            if len(item) != 2:
                continue
            keyMarker = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            value = self.cleanHtmlStr(item[1]).replace(' , ', ', ')
            key = keysMap.get(keyMarker, '')
            if key != '' and value != '':
                otherInfo[key] = value

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

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, ShahiidAnime(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('category', '') == 'explore_item':
            return True
        return False
