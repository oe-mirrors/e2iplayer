# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ngolos_language = ConfigSelection(default="en", choices=[("en", _("English")), ("es", _("Spanish")), ("pt", _("Portuguese"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.ngolos_language))
    return optionList
###################################################


def gettytul():
    return 'https://ngolos.com/'


class NGolosCOM(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ngolos.com', 'cookie': 'ngolos.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = None
        self.cacheCategories = []
        self.cacheTeams = {}

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def selectDomain(self):
        self.MAIN_URL = 'https://www.ngolos.com/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/assets/images/thumbnail.png')

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        lang = config.plugins.iptvplayer.ngolos_language.value
        cookieItems = addParams.get('cookie_items', {})
        cookieItems.update({'language': lang})
        addParams['cookie_items'] = cookieItems
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem, nextCategory):
        printDBG("NGolosCOM.listMainMenu")
        self.cacheCategories = []

        params = dict(cItem)
        params.update({'category': 'list_items', 'title': _('Home page'), 'url': cItem['url']})
        self.addDir(params)
        self.addMarker({})

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'competitions_sidebar'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'url': url})
            self.addDir(params)

        self.addMarker({})

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '"competitions"'), ('<div', '>', 'other_settings'))[1]
        data = re.compile('''(<div[^>]+?card\-header collapsed[^>]+?>)''').split(data)
        for idx in range(1, len(data), 2):
            parent = self.cm.ph.getSearchGroups(data[idx], '''data\-parent=['"]([^'^"]+?)['"]''')[0]
            current = self.cm.ph.getSearchGroups(data[idx], '''href=['"](#[^'^"]+?)['"]''')[0]

            tmp = self.cm.ph.getDataBeetwenNodes(data[idx + 1], ('<a', '>', 'card-title'), ('</a', '>'))[1]
            cUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^'^"]+?)['"]''')[0])
            cTitle = self.cleanHtmlStr(tmp)
            if cTitle == '':
                cTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data[idx + 1], '<i', '</a>')[1])

            if parent == '.competitions':
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': cTitle, 'cat_id': current})
                self.addDir(params)
            else:
                subItems = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx + 1].split('card-body', 1)[-1], '<a', '</a>')
                for item in tmp:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                    title = self.cleanHtmlStr(item)
                    params = dict(cItem)
                    params.update({'category': 'list_items', 'title': title, 'url': url, 'parent': current})
                    subItems.append(params)

                if len(subItems):
                    if self.cm.isValidUrl(cUrl):
                        params = dict(cItem)
                        params.update({'category': 'list_items', 'title': _('--All--'), 'url': cUrl, 'parent': current})
                        subItems.insert(0, params)
                    params = dict(cItem)
                    params.update({'category': 'sub_items', 'title': cTitle, 'parent': parent, 'sub_items': subItems})
                    self.cacheCategories.append(params)

    def listCatItems(self, cItem, nextCategory):
        printDBG("NGolosCOM.listCatItems")

        for item in self.cacheCategories:
            if cItem['cat_id'] == item['parent']:
                self.currList.append(item)

    def listItems(self, cItem, nextCategory):
        printDBG("NGolosCOM.listItems |%s|" % cItem)

        page = cItem.get('page', 1)

        params = dict(self.defaultParams)
        params['cookie_items'] = {'orderby': cItem.get('orderby', '')} #'latest'
        sts, data = self.getPage(cItem['url'], params)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        if page == 1:
            if 'team' not in cItem:
                team = self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'competition'), ('</p', '>'), False)[1].strip()
                if self.cacheTeams == {}:
                    url = self.getFullUrl('/assets/json/clubs.json')
                    sts, tmp = self.getPage(url, params)
                    try:
                        self.cacheTeams = byteify(json.loads(tmp))
                    except Exception:
                        printExc()
                try:
                    for item in self.cacheTeams['data'][team]:
                        title = self.cleanHtmlStr(item['name'])
                        url = self.getFullUrl('/team/' + item['url'])
                        desc = [self.cleanHtmlStr(item['location'])]
                        desc.append(self.cleanHtmlStr(item['alias']))
                        icon = self.getFullIconUrl('/assets/images/logos/' + item['logo'])
                        params = dict(cItem)
                        params.update({'good_for_fav': True, 'title': title, 'url': url, 'team': team, 'icon': icon, 'desc': ' | '.join(desc)})
                        self.addDir(params)
                except Exception:
                    printExc()

                if len(self.currList):
                    params = dict(cItem)
                    params.update({'title': _('--All--'), 'team': ''})
                    self.currList.insert(0, params)
                    return

            if 'orderby' not in cItem:
                tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<input', '>', 'orderby_sidebar'), ('</label', '>'))
                for item in tmp:
                    title = self.cleanHtmlStr(item)
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                    if '0' == value:
                        value = 'latest'
                    else:
                        value = ''
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': title, 'orderby': value})
                    self.addDir(params)

                if len(self.currList):
                    return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'match row'), ('<', '>', 'reportlink_before'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'match row'))
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')

            title = self.cleanHtmlStr(item[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item[0], '''href=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(item[-1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': desc})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("NGolosCOM.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tabs = {}
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'nav-tabs'), ('</ul', '>'))[1]
        tmp = re.compile('''<a[^>]+?href=['"]#([^'^"]+?)['"][^>]*?>([^<]+?)<''').findall(tmp)
        for item in tmp:
            tabs[item[0]] = self.cleanHtmlStr(item[1])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'tab-pane'), ('</script', '>'))[1]
        tmp = self.cm.ph.rgetAllItemsBeetwenNodes(tmp, ('</div', '>'), ('<div', '>', 'tab-pane'))
        for section in tmp:
            sId = self.cm.ph.getSearchGroups(section, '''id=['"]([^'^"]+?)['"]''')[0]
            subItems = []
            section = section.split('<br />')
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                if url == '':
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0])
                if url == '':
                    continue
                title = '%s : %s' % (cItem['title'], self.cleanHtmlStr(item))
                params = dict(cItem)
                params.update({'good_for_fav': False, 'type': 'video', 'title': title, 'url': url})
                subItems.append(params)

            if len(subItems) and '' != tabs.get(sId, ''):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': tabs[sId], 'sub_items': subItems})
                self.addDir(params)
            else:
                self.currList.extend(subItems)

        if 0 == len(self.currList):

            tmp = self.cm.ph.rgetDataBeetwenNodes(data, ('</iframe', '>'), ('<div', '>', 'font-weight-bold'), False)[1]
            tmp = tmp.split('</iframe>')
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                if url == '':
                    continue
                title = '%s : %s' % (cItem['title'], self.cleanHtmlStr(item))
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': title, 'url': url})
                self.addVideo(params)

        return
        data = re.sub('''unescape\(["']([^"^']+?)['"]\)''', lambda m: urllib.unquote(m.group(1)), data)

        titles = []
        titles2 = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="tab-1"', '</strong>')[1]
        tmp2 = tmp.split('</div>')
        tmp = tmp.split('</iframe>')

        for title in tmp:
            title = self.cleanHtmlStr(title)
            if title != '':
                titles.append(title)

        for title in tmp2:
            title = self.cleanHtmlStr(title)
            if title != '':
                titles2.append(title)

        if len(titles2) > len(titles):
            titles = titles2

        tmp = re.compile('''['"]([^'^"]*?//config\.playwire\.com[^'^"]+?\.json)['"]''').findall(data)
        tmp.extend(re.compile('<iframe[^>]+?src="([^"]+?)"').findall(data))
        tmp.extend(re.compile('''<a[^>]+?href=['"](https?://[^'^"]*?ekstraklasa.tv[^'^"]+?)['"]''').findall(data))
        urlsTab = []
        for idx in range(len(tmp)):
            if 'facebook' in tmp[idx]:
                continue
            url = self.getFullUrl(tmp[idx])
            if not self.cm.isValidUrl(url):
                continue
            if 'playwire.com' not in url and self.up.checkHostSupport(url) != 1:
                try:
                    url = self.getFullUrl(base64.b64decode(url.split('link=', 1)[-1]))
                    if self.up.checkHostSupport(url) != 1:
                        continue
                except Exception:
                    printExc()
                    continue

            urlsTab.append(url)

        for idx in range(len(urlsTab)):
            title = cItem['title']
            if len(titles) == len(urlsTab):
                title += ' - ' + titles[idx]
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': urlsTab[idx]})
            self.addVideo(params)

    def listSubItems(self, cItem):
        printDBG("NGolosCOM.listSubItems")
        self.currList = cItem['sub_items']

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("NGolosCOM.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        page = cItem.get('page', 1)
        if page == 1:
            cItem['url'] = self.SEARCH_URL + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("NGolosCOM.getLinksForVideo [%s]" % cItem)
        urlTab = []
        videoUrl = cItem['url']
        if 'playwire.com' in videoUrl:
            sts, data = self.cm.getPage(videoUrl)
            if not sts:
                return []
            try:
                data = byteify(json.loads(data))
                if 'content' in data:
                    url = data['content']['media']['f4m']
                else:
                    url = data['src']
                sts, data = self.cm.getPage(url)
                baseUrl = self.cm.ph.getDataBeetwenMarkers(data, '<baseURL>', '</baseURL>', False)[1].strip()
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<media ', '>')
                for item in data:
                    url = self.cm.ph.getSearchGroups(item, '''url=['"]([^'^"]+?)['"]''')[0]
                    height = self.cm.ph.getSearchGroups(item, '''height=['"]([^'^"]+?)['"]''')[0]
                    bitrate = self.cm.ph.getSearchGroups(item, '''bitrate=['"]([^'^"]+?)['"]''')[0]
                    name = '[%s] bitrate:%s height: %s' % (url.split('.')[-1], bitrate, height)
                    if not url.startswith('http'):
                        url = baseUrl + '/' + url
                    if url.startswith('http'):
                        if 'm3u8' in url:
                            hlsTab = getDirectM3U8Playlist(url)
                            for idx in range(len(hlsTab)):
                                hlsTab[idx]['name'] = '[hls] bitrate:%s height: %s' % (hlsTab[idx]['bitrate'], hlsTab[idx]['height'])
                            urlTab.extend(hlsTab)
                        else:
                            urlTab.append({'name': name, 'url': url})
            except Exception:
                printExc()
        elif '.me/player' in videoUrl:
            sts, data = self.cm.getPage(videoUrl)
            if not sts:
                return []
            url = self.cm.ph.getSearchGroups(data, '''file:[^"^']*?["'](http[^'^"]+?)["']''')[0]
            urlTab.append({'name': self.up.getDomain(videoUrl), 'url': url})
        elif videoUrl.startswith('http'):
            urlTab.extend(self.up.getVideoLinkExt(videoUrl))
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("NGolosCOM.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            baseItem = {'type': 'category', 'name': 'category', 'url': self.getMainUrl()}
            self.listMainMenu(baseItem, 'list_cat_items')
        elif 'list_cat_items' == category:
            self.listCatItems(self.currItem, 'list_items')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'explore_item')
        elif 'explore_item' == category:
            self.exploreItem(self.currItem, 'sub_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
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
        CHostBase.__init__(self, NGolosCOM(), True, [])
