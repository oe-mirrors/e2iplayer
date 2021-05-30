# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.cimaclub_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                        ("proxy_1", _("Alternative proxy server (1)")),
                                                                                        ("proxy_2", _("Alternative proxy server (2)"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.cimaclub_proxy))
    return optionList
###################################################


def gettytul():
    return 'http://cimaclub.com/'


class CimaClubCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cimaclub.com', 'cookie': 'cimaclub.com.cookie'})
        self.USER_AGENT = self.cm.getDefaultHeader()['User-Agent']
        self.MAIN_URL = 'http://cimaclub.com/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/originals/f2/67/05/f267052cb0ba96d70dd21e41a20a522e.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.cacheSubSections = {}
        self.cacheMainMenu = []
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.cacheEpisodes = []

    def getProxy(self):
        proxy = config.plugins.iptvplayer.cimaclub_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
        else:
            proxy = None
        return proxy

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy != None:
            addParams = MergeDicts(addParams, {'http_proxy': proxy})
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '':
            return url
        proxy = self.getProxy()
        if proxy != None:
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance', '__cfduid'])
        url = strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.HTTP_HEADER['User-Agent']})
        return url

    def _addSubSection(self, cItem, sectionTitle, key, data, revert=False):
        self.cacheSubSections[key] = self.cacheSubSections.get(key, [])
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = {'title': title, 'url': url}
            if revert:
                self.cacheSubSections[key].insert(0, params)
            else:
                self.cacheSubSections[key].append(params)

        if len(self.cacheSubSections[key]):
            params = dict(cItem)
            params.update({'title': sectionTitle, 'category': 'list_sub_section', 'f_sub_key': key})
            self.addDir(params)

    def listMainMenu(self, cItem):
        printDBG("CimaClubCom.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        self.cacheSubSections = {'sub_1': []}

        # main menu
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'MainMenu'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            self.cacheMainMenu.append({'title': title, 'url': url})
        self.addDir({'name': 'category', 'type': 'category', 'category': 'list_sub_main', 'title': _('Main menu')})

        mapUrls = {'toprating': '/top-imdb/', 'featured': '/most-views/'}
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'data-filter'), ('</li', '>'))
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''data\-filter=['"]([^'^"]+?)['"]''')[0]
            url = mapUrls.get(url, '/wp-content/themes/Cimaclub/filter/{0}.php'.format(url))
            self.cacheSubSections['sub_1'].append({'title': self.cleanHtmlStr(item), 'url': self.getFullUrl(url)})

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'dataFilter'), ('</ul', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        self._addSubSection(cItem, 'الاقسام الفرعية', 'sub_1', tmp)

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', '/release-year/'), ('</a', '>'))
        self._addSubSection(cItem, _('By year'), 'by_year', tmp, True)

        self.fillCacheFilters(cItem, data)
        if len(self.cacheFiltersKeys):
            self.addDir({'name': 'category', 'type': 'category', 'category': 'list_filters', 'title': _('Filters'), 'url': self.getMainUrl()})

        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listSubMenu(self, cItem, nextCategory):
        printDBG("CimaClubCom.listSubMenu [%s]" % cItem)

        for item in self.cacheMainMenu:
            if item['url'] == '#':
                self.addMarker({'title': item['title']})
                continue
            params = {'name': 'category', 'type': 'category', 'category': 'list_items'}
            params.update(item)
            self.addDir(params)

    def listSubSections(self, cItem, nextCategory):
        printDBG("CimaClubCom.listSubSections [%s]" % cItem)
        key = cItem.get('f_sub_key', '')
        tab = self.cacheSubSections.get(key, [])
        self.listsTab(tab, {'name': 'category', 'type': 'category', 'category': 'list_items'})

    def fillCacheFilters(self, cItem, data):
        printDBG("CimaClubCom.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''=['"]([^"^']+?)['"]''')[0]
                title = self.cleanHtmlStr(item)
                if title.lower() in ['all', 'default', 'any']:
                    addAll = False
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'searchandfilter'), ('</form', '>'))[1]
        self.cacheFilters['operators'] = []
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '</li>')
        for item in tmp:
            name = self.cm.ph.getSearchGroups(item, '''name=['"]([^"^']+?)['"]''')[0]
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
            self.cacheFilters['operators'].append({name: value})

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))
        for tmp in data:
            key = self.cm.ph.getSearchGroups(tmp, '''name=['"]([^"^']+?)['"]''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            addFilter(tmp, 'value', key, False)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("CimaClubCom.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("CimaClubCom.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        if 'f_idx' in cItem:
            post_data = {}
            for key in self.cacheFiltersKeys:
                baseKey = key[2:] # "f_"
                if key in cItem:
                    post_data[baseKey] = cItem[key]
            for item in self.cacheFilters.get('operators', []):
                post_data.update(item)
        else:
            post_data = None

        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts:
            return

        self.setMainUrl(data.meta['url'])
        baseItem = {'good_for_fav': False, 'name': 'category', 'type': 'category', 'category': cItem['category']}

        idx1 = data.find('overlayBOBOB')
        idx2 = data.rfind('footerEndSection')
        if idx1 >= 0 and idx2 >= 0:
            data = data[idx1:idx2]

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</ul', '>'))[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<li', '</a>', '&laquo;'), ('<', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'movie'), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''[\s\-]src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            if title == '':
                printDBG("ERROR: NO TITLE IN ITEM")
                continue
            desc = []
            views = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'views'), ('</span', '>'))[1])
            if views != '':
                desc.append(_('%s views') % views)
            cats = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'category'), ('</span', '>'))[1])
            if cats != '':
                desc.append(cats)
            raiting = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<i', '>', 'StarLabels'), ('</i', '>'))[1])
            if raiting != '':
                desc.append(_('%s/10') % raiting)
            desc = ' | '.join(desc)
            desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])

            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(baseItem)
            params.update({'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("CimaClubCom.exploreItem [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        self.cacheEpisodes = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'data-season'), ('</div', '>'))
        for item in tmp:
            title = self.cleanHtmlStr(item)
            sId = self.cm.ph.getSearchGroups(item, '''data\-season=['"]([^'^"]+?)['"]''')[0]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            self.cacheEpisodes.append({'title': title, 'url': url, 's_id': sId})

        # series title
        sTitle = ''
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mpbreadcrumbs'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        if len(tmp):
            sTitle = self.cleanHtmlStr(tmp[-1])

        baseItem = {'good_for_fav': False, 'name': 'category', 'type': 'category', 'category': nextCategory, 'icon': cItem.get('icon', '')}
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'data-filter'), ('</div', '>'))
        for item in tmp:
            sId = self.cm.ph.getSearchGroups(item, '''data\-filter=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            params = dict(baseItem)
            params.update({'title': title, 's_title': sTitle, 's_id': sId})
            self.addDir(params)

        if 0 == len(self.currList) and 'embedServer' in data:
            params = dict(cItem)
            params['good_for_fav'] = True
            self.addVideo(params)
        elif 1 == len(self.currList):
            item = self.currList.pop()
            self.listEpisodes(item)

    def listEpisodes(self, cItem):
        printDBG("CimaClubCom.listEpisodes [%s]" % cItem)
        sId = cItem['s_id']
        sTitle = cItem['s_title']
        for item in self.cacheEpisodes:
            if item['s_id'] != sId:
                continue
            title = '%s - %s - %s' % (sTitle, cItem['title'], item['title'])
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': True, 'title': title})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaClubCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 1 == cItem.get('page', 1):
            cItem['category'] = 'list_items'
            cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("CimaClubCom.getLinksForVideo [%s]" % cItem)

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

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        tmp = self.cm.ph.getSearchGroups(data, '''(<a[^>]+?viewMovie[^>]+?>)''')[0]
        viewUrl = self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)['"]''')[0]

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])
        urlParams['header']['Referer'] = cUrl

        sts, data = self.getPage(self.getFullUrl(viewUrl), urlParams)
        if not sts:
            return

        retTab = []

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'embedServer'), ('<div', '>'))[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        if 1 == self.up.checkHostSupport(url):
            retTab.append({'name': self.up.getDomain(url), 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'serversList ', '</script>')[1]
        serwerUrl = self.cm.ph.getSearchGroups(tmp, '''['"\s]url['"]?\s*?:\s*?['"]([^"^']+?)['"]''')[0]
        serwerQuery = self.cm.ph.getSearchGroups(tmp, '''['"\s]data['"]?\s*?:\s*?['"]([^"^']+?)['"]''')[0]

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'data-server'), ('</li', '>'))
        for item in tmp:
            sId = self.cm.ph.getSearchGroups(item, '''data\-server=['"]([^'^"]+?)['"]''')[0]
            name = self.cleanHtmlStr(item)
            url = self.getFullUrl(serwerUrl + '?' + serwerQuery + sId)
            retTab.append({'name': name, 'url': strwithmeta(url, {'Referer': viewUrl}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("CimaClubCom.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        if 1 == self.up.checkHostSupport(baseUrl):
            return self.up.getVideoLinkExt(baseUrl)

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])
        urlParams['header']['Referer'] = baseUrl.meta.get('Referer', self.getMainUrl())

        sts, data = self.getPage(baseUrl, urlParams)
        if not sts:
            return

        videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        videoUrl = strwithmeta(videoUrl, {'Referer': urlParams['header']['Referer']})
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None):
        printDBG("CimaClubCom.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'CoverIntroMovie'), ('<script', '>'))[1]

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'contentFilm'), ('</div', '>'))[1])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h1', '>', 'entry-title'), ('</h1', '>'))[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''\ssrc=['"]([^'^"]+?(:?\.jpe?g|\.png)(:?\?[^'^"]*?)?)['"]''')[0])

        item = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'views'), ('</div', '>'))[1])
        if item != '':
            otherInfo['rating'] = item

        keysMap = {'quality': 'quality',
                   'category': 'category',
                   'genre': 'genre',
                   'year': 'year',
                   'runtime': 'duration',
                   'datePublished': 'released', }
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>', 'class='), ('</span', '>'))
        printDBG(data)
        for item in data:
            marker = self.cm.ph.getSearchGroups(item, '''\sitemprop=['"]([^'^"]+?)['"]''')[0]
            if marker == '':
                marker = self.cm.ph.getSearchGroups(item, '''\sclass=['"]([^'^"]+?)['"]''')[0]
            printDBG(">>> %s" % marker)
            if marker not in keysMap:
                continue
            value = self.cleanHtmlStr(item)
            printDBG(">>>>> %s" % value)
            if value == '':
                continue
            if marker == 'genre' and '' != self.cm.ph.getSearchGroups(value, '''([0-9]{4})''')[0]:
                marker = 'year'
            otherInfo[keysMap[marker]] = value

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

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_sub_main':
            self.listSubMenu(self.currItem, 'list_items')
        elif category == 'list_sub_section':
            self.listSubSections(self.currItem, 'list_items')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, CimaClubCom(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        else:
            return False
