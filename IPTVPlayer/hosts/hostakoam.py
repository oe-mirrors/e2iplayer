# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
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
config.plugins.iptvplayer.akoam_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                     ("proxy_1", _("Alternative proxy server (1)")),
                                                                                     ("proxy_2", _("Alternative proxy server (2)"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.akoam_proxy))
    return optionList
###################################################


def gettytul():
    return 'https://ar.akoam.net/'


class AkoAm(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ako.am', 'cookie': 'ako.am.cookie'})
        self.MAIN_URL = 'https://ar.akoam.net/'

        self.USER_AGENT = self.cm.getDefaultHeader()['User-Agent']
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = MergeDicts(self.HTTP_HEADER, {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.DEFAULT_ICON_URL = self.getFullIconUrl('/scripts/site/img/main_logo.png')

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def setMainUrl(self, url):
        CBaseHostClass.setMainUrl(self, url)
        self.HTTP_HEADER['Referer'] = self.getMainUrl()
        self.HTTP_HEADER['Origin'] = self.getMainUrl()[:-1]

    def getProxy(self):
        proxy = config.plugins.iptvplayer.akoam_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
        else:
            proxy = None
        return proxy

    def getPage(self, baseUrl, addParams={}, post_data=None):
        while True:
            if addParams == {}:
                addParams = dict(self.defaultParams)
            origBaseUrl = baseUrl
            baseUrl = self.cm.iriToUri(baseUrl)

            proxy = self.getProxy()
            if proxy != None:
                addParams = MergeDicts(addParams, {'http_proxy': proxy})
            addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
            sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)

            if sts and 'class="loading"' in data:
                GetIPTVSleep().Sleep(5)
                continue
            break
        return sts, data

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

    def listMainMenu(self, cItem, nextCategory):
        printDBG("AkoAm.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'partions'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0])
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url, 'desc': desc})
            self.addDir(params)

        if 0 == len(self.currList):
            return

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("AkoAm.listSubMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sect_parts'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory1, 'title': title, 'url': url})
            self.addDir(params)

        if len(self.currList) > 0:
            params = dict(cItem)
            params.update({'category': nextCategory1, 'title': _('All')})
            self.currList.insert(0, params)
        else:
            cItem = dict(cItem)
            cItem['category'] = nextCategory1
            self.listItems(cItem, nextCategory2, data)

    def listSubItems(self, cItem):
        printDBG("AkoAm.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("InteriaTv.listItems")
        page = cItem.get('page', 1)

        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<li', '>', 'pagination_next'), ('</li', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0])

        if '/search/' in cItem['url']:
            m1 = 'tags_box'
        else:
            m1 = 'subject_box'

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', m1), ('</a', '>'))
        for item in data:
            if 'next_prev' in item:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            if icon == '':
                icon = self.getFullIconUrl(self.cm.ph.getDataBeetwenMarkers(item, 'url(', ');', False)[1].strip())
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'), False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'desc'), ('</span', '>'), False)[1])
            params = {'good_for_fav': True, 'priv_has_art': True, 'category': nextCategory, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AkoAm.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        url = self.getFullUrl('/search/') + urllib.quote(searchPattern)
        cItem = dict(cItem)
        cItem.update({'url': url, 'category': 'list_items'})
        self.listItems(cItem, 'explore_item')

    def _getLinksTab(self, data):
        printDBG("AkoAm._getLinksTab")
        hostMap = {'1458117295': 'openload.co', '1477487601': 'estream.to', '1505328404': 'streamango', '1423080015': 'flashx.tv', '1430052371': 'ok.ru'}

        playable = False
        urlsTab = []
        for linksSection in data:
            baseLinkName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(linksSection, '<h5', '</h5>')[1])
            baseFileName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(linksSection, ('<span', '>', 'file_title'), ('</span', '>'))[1])
            linksSection = linksSection.split('</div>')
            for link in linksSection:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(link, '''href=['"]([^"^']+?)['"]''')[0])
                if url == '':
                    continue
                nameTab = []
                if baseFileName != '':
                    nameTab.append(baseFileName)
                    if not playable:
                        ext = baseFileName.split(' - ', 1)[0].strip().split('.')[-1].lower()
                        if ext not in ['pdf', 'rar', 'zip', '7zip']:
                            playable = True
                else:
                    playable = True
                name = self.cleanHtmlStr(link)
                if name != '':
                    nameTab.append(name)
                hostId = self.cm.ph.getSearchGroups(link, '/files/([0-9]+?)\.')[0]
                if hostId in hostMap:
                    nameTab.append(hostMap[hostId])
                urlsTab.append({'name': ' '.join(nameTab), 'url': url, 'need_resolve': 1})
        return playable, urlsTab

    def exploreItem(self, cItem, nextCategory):
        printDBG("AkoAm.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        iIcon = self.cm.ph.getDataBeetwenNodes(data, ('<img', '>', 'main_img'), ('<', '>'))[1]
        iIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(iIcon, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
        iTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<', '>', 'sub_title'), ('</h', '>'))[1])
        iDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sub_desc'), ('</div', '>'))[1])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sub_trailer'), ('</div', '>'))[1]
        iTrailer = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"]([^"^']+?youtube[^"^']+?)['"]''', 1, True)[0])
        if iTrailer != '':
            params = {'good_for_fav': False, 'url': iTrailer, 'title': '%s - %s' % (iTitle, _('trailer')), 'icon': iIcon}
            self.addVideo(params)

        m1 = 'sub_episode_links'
        if m1 in data:
            reObj = re.compile('<div[^>]+?direct_box[^>]+?>')
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', m1), ('<a', '>', 'javascript'), False)[1]
            tmp = re.compile('''<div[^>]+?%s[^>]+?>''' % m1).split(tmp)
            for item in tmp:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>', 'sub_epsiode_title'), ('</h2', '>'))[1])
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'sub_create_date'), ('</span', '>'))[1])
                item = reObj.split(item, 1)
                playable, urlsTab = self._getLinksTab(item)
                if len(urlsTab):
                    params = {'title': '%s - %s' % (iTitle, title), 'url': cItem['url'] + '#iptvplayer=' + title, 'icon': iIcon, 'desc': desc + '[/br]' + iDesc, 'iptv_urls': urlsTab}
                    if playable:
                        self.addVideo(params)
                    else:
                        self.addData(params)

            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>'), ('</a', '>'))
            for item in data:
                if '#FFD700' not in item:
                    continue
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                params = dict(cItem)
                params.update({'title': '%s - %s' % (iTitle, title), 'url': url, 'icon': iIcon, 'desc': ''})
                self.addDir(params)
        else:
            urlsTab = []
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'sub_direct_links'), ('</div></div></div', '>'))
            playable, urlsTab = self._getLinksTab(data)
            if len(urlsTab):
                params = {'title': iTitle, 'url': cItem['url'], 'icon': iIcon, 'desc': iDesc, 'iptv_urls': urlsTab}
                if playable:
                    self.addVideo(params)
                else:
                    self.addData(params)

    def getLinksForVideo(self, cItem):
        printDBG("AkoAm.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        retTab = cItem.get('iptv_urls', [])

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab

        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("AkoAm.getVideoLinks [%s]" % baseUrl)
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

        if 1 != self.up.checkHostSupport(baseUrl):
            paramsUrl = {'header': dict(self.HTTP_HEADER)}
            paramsUrl['header']['Referer'] = baseUrl.meta.get('Referer', self.getMainUrl())
            paramsUrl['max_data_size'] = 0
            try:
                self.cm.clearCookie(self.COOKIE_FILE, removeNames=['golink'])
                paramsUrl['use_new_session'] = True
                self.getPage(baseUrl, paramsUrl)
                paramsUrl.pop('use_new_session')
                cUrl = self.cm.meta['url']
                data = self.cm.getCookieItems(self.COOKIE_FILE)
                if 'golink' in data:
                    data = data['golink']
                    printDBG(data)
                    data = urllib.unquote(data)
                    data = byteify(json.loads(data))
                    printDBG(data)
                    baseUrl = data['route']

                    paramsUrl = dict(self.defaultParams)
                    paramsUrl['header'] = dict(self.HTTP_HEADER)
                    paramsUrl['header']['Referer'] = cUrl
                    sts, data = self.getPage(baseUrl, paramsUrl)
                    if sts:
                        cUrl = data.meta['url']
                        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                        if url == '':
                            time = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'timerHolder'), ('</div', '>'), False)[1])
                            GetIPTVSleep().Sleep(int(time))
                            paramsUrl = dict(self.defaultParams)
                            paramsUrl['header'] = dict(self.AJAX_HEADER)
                            paramsUrl['header']['Referer'] = cUrl
                            sts, data = self.getPage(cUrl, paramsUrl, {})
                            if sts:
                                printDBG(data)
                                data = byteify(json.loads(data))
                                urlTab.append({'name': 'direct_link', 'url': self.getFullUrl(data['direct_link'])})
                        else:
                            baseUrl = strwithmeta(url, {'Referer': cUrl})
            except Exception:
                printExc()

        urlTab.extend(self.up.getVideoLinkExt(baseUrl))
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("AkoAm.getVideoLinks [%s]" % cItem)
        retTab = []
        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        icon = self.cm.ph.getDataBeetwenNodes(data, ('<img', '>', 'main_img'), ('<', '>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<', '>', 'sub_title'), ('</h', '>'))[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sub_desc'), ('</div', '>'))[1])

        descData = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sub_mainInfo'), ('<div', '>', 'sub_socialMedia'), False)[1]

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(descData, ('<li', '>', 'imdb'), ('</li', '>'), False)[1])
        if tmp != '':
            otherInfo['imdb_rating'] = tmp.replace(' ', '')

        descTabMap = {"المدة الزمنية": "duration",
                      "سنة الانتاج": "year",
                      "محتوى الفيلم": "genre",
                      "اللغة": "language",
                      "جودة الصورة": "quality"}

        reObj = re.compile('''<i[^>]*?>''', re.I)
        descData = self.cm.ph.getAllItemsBeetwenNodes(descData, ('<li', '>'), ('</li', '>'), False)
        for item in descData:
            item = reObj.split(item)
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            val = self.cleanHtmlStr(item[1])
            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = val
                except Exception:
                    continue

        reObj = re.compile('''<[\s\\/]*?br[\s\\/]*?>''', re.I)
        descTabMap = {"بطولة الفيلم": "actors",
                      "ﺇﺧﺮاﺝ": "director",
                      "ﺗﺄﻟﻴﻒ": "writers",
                      "التصنيف": "categories",
                      }
        descData = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sub_desc'), ('<div', '>', 'clear'), False)[1]
        descData = re.compile('''<span[^>]+?color\:[^>]+?>''').split(descData)
        for item in descData:
            item = item.split('</span>', 1)
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            vals = []
            tmp = reObj.split(item[1])
            for val in tmp:
                val = self.cleanHtmlStr(val)
                if val != '':
                    vals.append(val)
            if key in descTabMap and len(vals):
                try:
                    otherInfo[descTabMap[key]] = ', '.join(vals)
                except Exception:
                    continue

        if title == '':
            title = cItem['title']
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
        if name == None and category == '':
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'}, 'sub_menu')
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem, 'list_items', 'explore_item')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'top':
            self.listTop(self.currItem, 'sub_items', 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'sub_items')
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
        CHostBase.__init__(self, AkoAm(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('priv_has_art', False):
            return True
        else:
            return False
