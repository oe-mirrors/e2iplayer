# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, MergeDicts, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote, urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import iterDictItems
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ddlme_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                     ("webproxy", _("Web proxy")),
                                                                                     ("proxy_1", _("Alternative proxy server (1)")),
                                                                                     ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.ddlme_lang = ConfigSelection(default="", choices=[("", _("default")),
                                                                                ("de", "de"),
                                                                                ("en", "en")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language"), config.plugins.iptvplayer.ddlme_lang))
    optionList.append(getConfigListEntry(_("Use proxy"), config.plugins.iptvplayer.ddlme_proxy))
    return optionList
###################################################


def gettytul():
    return 'http://ddl.me/'


class DDLMe(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'DDLMe', 'cookie': 'DDLMe.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://static.kino.de/wp-content/uploads/2018/06/DDLme.jpg'
        self.cacheLinks = {}
        self.cacheCats = []
        self.cacheSort = []

    def getRealUrl(self, url):
        if config.plugins.iptvplayer.ddlme_proxy.value == 'webproxy' and url != None and 'browse.php?u=' in url:
            url = urllib_unquote(self.cm.ph.getSearchGroups(url + '&', '''\?u=(http[^&]+?)&''')[0])
        return url

    def getFullUrl(self, url, baseUrl=None):
        url = self.getRealUrl(url)
        baseUrl = self.getRealUrl(baseUrl)
        if not self.cm.isValidUrl(url) and baseUrl != None:
            if url.startswith('/'):
                baseUrl = self.cm.getBaseUrl(baseUrl)
            else:
                baseUrl = baseUrl.rsplit('/', 1)[0] + '/'
        return CBaseHostClass.getFullUrl(self, url.replace('&#038;', '&'), baseUrl)

    def getMainUrl(self):
        lang = config.plugins.iptvplayer.ddlme_lang.value
        if lang == '':
            lang = GetDefaultLang()
        if lang not in ['en', 'de']:
            lang = 'en'
        return 'http://%s.ddl.me/' % lang

    def setMainUrl(self, url):
        CBaseHostClass.setMainUrl(self, self.getRealUrl(url))

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.ddlme_proxy.value
        if proxy == 'webproxy':
            addParams = dict(addParams)
            proxy = 'http://n-guyot.fr/exit/browse.php?u={0}&b=4'.format(urllib_quote(baseUrl, ''))
            addParams['header']['Referer'] = proxy + '&f=norefer'
            baseUrl = proxy
        elif proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})
        tries = 0
        while tries < 3:
            tries += 1
            sts, data = self.cm.getPage(baseUrl, addParams, post_data)
            if sts:
                if config.plugins.iptvplayer.ddlme_proxy.value == 'webproxy' and 'sslagree' in data:
                    sts, data = self.cm.getPage('http://n-guyot.fr/exit/includes/process.php?action=sslagree', addParams, post_data)
                    tries += 1
                    continue
                elif len(data) < 256 and 'warming' in data:
                    GetIPTVSleep().Sleep(2)
                    continue
            break
        return sts, data

    def getFullIconUrl(self, url, currUrl=None):
        url = self.getFullUrl(url, currUrl)
        proxy = config.plugins.iptvplayer.ddlme_proxy.value
        if proxy == 'webproxy':
            return url
        elif proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        return url

    def listMain(self, cItem):
        printDBG("DDLMe.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mainmenu'), ('</div', '>'), False)[1]
        for type in [('releases', 'release_tab'), ('top100', 'top100_tab'), ('moviez', 'cat_items'), ('episodez', 'cat_items'), ('tags', 'tags_tab')]:
            item = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', type[0]), ('</a', '>'))[1]
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0].replace('/cover/', '/serien/')
            item = re.compile('<span[^>]*?>').split(item, 1)
            title = self.cleanHtmlStr(item[0])
            desc = self.cleanHtmlStr(item[-1])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': type[1], 'title': title, 'url': url, 'desc': desc, 'f_type': type[0]})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def searchUrl(self, data):
        url = self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=([^>\s]+?)[>\s]''')[0]
        if url.startswith('"'):
            url = self.cm.ph.getSearchGroups(url, '"([^"]+?)"')[0]
        if url.startswith("'"):
            url = self.cm.ph.getSearchGroups(url, "'([^']+?)'")[0]
        return self.getFullUrl(url)

    def listSubTabs(self, cItem, nextCategory):
        printDBG("DDLMe.listSubTabs")
        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'catSwitch'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if '/movies' not in url and '/tv' not in url:
                continue
            title = self.cleanHtmlStr(item)
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            self.addDir(MergeDicts(cItem, {'title': title, 'url': url, 'category': nextCategory, 'desc': ''}))

        if len(self.currList) == 0:
            self.listTabItems(MergeDicts(cItem, {'category': nextCategory}), 'explore_item')

    def listTabs(self, cItem, nextCategory):
        printDBG("DDLMe.listTabs")
        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        list = []
        tabTypes = False
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'btabs'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if 'filme' in url:
                tabTypes = True
            title = self.cleanHtmlStr(item)
            if title == '' and 'all' in url:
                title = _('--All--')
            params = {'title': title, 'url': url}
            list.append(params)

        for item in list:
            if not tabTypes or 'filme' in item['url'] or 'serien' in item['url']:
                self.addDir(MergeDicts(cItem, item, {'category': nextCategory, 'desc': ''}))

    def listTags(self, cItem, nextCategory):
        printDBG("DDLMe.listTags")
        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'css3Tags'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            desc = self.cm.ph.getSearchGroups(item, '''/explore/([^/]+?)/''')[0].title()
            self.addDir(MergeDicts(cItem, {'title': title, 'url': url, 'category': nextCategory, 'desc': desc}))

    def listSortTags(self, cItem, nextCategory):
        printDBG("DDLMe.listSortTags")
        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'viewSwitch'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            self.addDir(MergeDicts(cItem, {'title': title, 'url': url, 'category': nextCategory, 'desc': ''}))

    def listCatItems(self, cItem, nextCategory):
        printDBG("DDLMe.listCatItems")
        self.cacheCats = []
        self.cacheSort = []

        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'select_content'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            cat = self.cm.ph.getSearchGroups(item, '''_([0-9]+)_''')[0]
            title = self.cleanHtmlStr(item)
            self.cacheCats.append({'title': title, 'f_cat': cat})

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'float:right'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            sort = self.cm.ph.getSearchGroups(item, '''_[0-9]+_([0-9]+)_''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            self.cacheSort.append({'title': title, 'f_sort': sort})

        self.listsTab(self.cacheCats, MergeDicts(cItem, {'category': nextCategory}))

    def listSortItems(self, cItem, nextCategory):
        printDBG("DDLMe.listSortItems")
        self.listsTab(self.cacheSort, MergeDicts(cItem, {'category': nextCategory}))

    def listSubItems(self, cItem):
        printDBG("DDLMe.listSubItems")
        self.currList = cItem['sub_items']

    def _listItems(self, cItem, nextCategory, data):
        printDBG("DDLMe._listItems [%s]" % nextCategory)
        cUrl = self.cm.meta['url']
        data = self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>', False)[1].split('</tr>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''rel=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(item) < 2:
                continue
            desc = []
            title = item[1].split('</span>', 1)
            desc.append(self.cleanHtmlStr(title[-1]))
            title = self.cleanHtmlStr(title[0])
            icon = self.getFullIconUrl(self.cm.ph.getDataBeetwenMarkers(item[0], 'url(', ')', False)[1].strip()).replace('_mini/', '/')
            for it in item[2:]:
                it = self.cleanHtmlStr(it)
                if it != '':
                    desc.append(it)
            desc = desc[::-1]

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'category': nextCategory, 'year': self.cleanHtmlStr(item[-1]), 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addDir(params)

    def listTagItems(self, cItem, nextCategory):
        printDBG("DDLMe.listTagItems [%s]" % cItem)

        page = cItem.get('page', 1)

        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        nextPage = self.cm.ph.getSearchGroups(data, '''<a([^>]+?fa\-arrow\-circle\-right[^>]+?)>''')[0]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0])

        cUrl = self.cm.meta['url']
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'item'), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
            item = item.split('</span>', 1)
            title = self.cleanHtmlStr(item[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item[-1], '''rel=['"]([^"^']+?)["']''', 1, True)[0]) + ' | ' + self.cleanHtmlStr(item[-1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'category': nextCategory, 'year': self.cleanHtmlStr(item[-1].split('#', 1)[0]), 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if nextPage and len(self.currList):
            try:
                tmp = int(self.cm.ph.getSearchGroups(nextPage, '''/([0-9]+)/?$''')[0])
                if tmp > page:
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': tmp})
                    self.addDir(params)
            except Exception:
                printExc()

    def listTabItems(self, cItem, nextCategory):
        printDBG("DDLMe.listTabItems [%s]" % cItem)

        page = cItem.get('page', 1)

        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        nextPage = self.cm.ph.getSearchGroups(data, '''<a([^>]+?fa\-arrow\-circle\-right[^>]+?)>''')[0]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0])

        self._listItems(cItem, nextCategory, data)

        if nextPage and len(self.currList):
            try:
                tmp = int(self.cm.ph.getSearchGroups(nextPage, '''/([0-9]+)/?$''')[0])
                if tmp > page:
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': tmp})
                    self.addDir(params)
            except Exception:
                printExc()

    def listItems(self, cItem, nextCategory):
        printDBG("DDLMe.listItems [%s]" % cItem)

        page = cItem.get('page', 1)
        url = '/%s_%s_%s_2_%s/' % (cItem['f_type'], cItem['f_cat'], cItem['f_sort'], page)
        sts, data = self.getPage(self.getFullUrl(url))
        if not sts:
            return

        if config.plugins.iptvplayer.ddlme_proxy.value == 'webproxy':
            nextPage = '_{0}%2'
        else:
            nextPage = '_{0}/'
        nextPage = nextPage.format(page + 1) in data

        self._listItems(cItem, nextCategory, data)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("DDLMe.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.getFullUrl(self.cm.meta['url'])

        #printDBG(data)

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'detailDesc'), ('</p', '>'), False)[1])

        trailer = self.cm.ph.getSearchGroups(data.rsplit('</ul>', 1)[0], '''<([^>]+?trailerbtn[^>]+?)>''')[0]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(trailer, '''rel=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
        if url != '':
            self.cacheLinks[url] = [{'name': 'trailer', 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1}]
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': cItem['title'] + ' - ' + _('trailer'), 'url': url, 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)

        tmp = ''
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
        for item in data:
            if 'subcats' in item:
                tmp = item
                break
        try:
            seasons = []
            episodes = {}

            playableItems = []

            jscode = tmp + '\n' + 'print(JSON.stringify(subcats));'
            ret = js_execute(jscode)
            if ret['sts'] and 0 == ret['code']:
                data = ret['data'].strip()
                data = byteify(json.loads(data))

                for key, dat in iterDictItems(data):
                    for name, item in iterDictItems(dat['links']):
                        for linkData in item:
                            pNum = int(linkData[0])
                            url = self.getFullUrl(linkData[3], cUrl)
                            if -1 == self.up.checkHostSupport(url):
                                continue

                            if 'info' in dat:
                                parts = 0
                                sNum = int(dat['info']['staffel'])
                                eNum = int(dat['info']['nr'])
                                #eId =  int(dat['info']['sid'])
                                #urlKey = '%s_%s_%s' % (str(sNum).zfill(4), str(eNum).zfill(4), str(pNum).zfill(4))
                                title = '%s: %sx%s %s' % (cItem['title'], str(sNum).zfill(2), str(eNum).zfill(2), self.cleanHtmlStr(dat['info']['name']))
                            else:
                                parts = int(dat['1'])
                                sNum = 0
                                eNum = 0
                                #urlKey = str(pNum).zfill(4)
                                title = cItem['title']

                            urlKey = '%s_%s_%s' % (str(sNum).zfill(4), str(eNum).zfill(4), str(pNum).zfill(4))

                            if pNum > 1 or parts > 1:
                                title += ' (Part %s)' % pNum

                            if sNum not in seasons:
                                seasons.append(sNum)
                                episodes[sNum] = []

                            if eNum not in episodes[sNum]:
                                episodes[sNum].append(eNum)

                            if urlKey not in self.cacheLinks:
                                self.cacheLinks[urlKey] = []
                                playableItems.append({'title': title, 'url': urlKey, 's_num': sNum, 'e_num': eNum, 'prev_url': cUrl})

                            self.cacheLinks[urlKey] .append({'name': name, 'url': url, 'need_resolve': 1})

                tmpList = []
                seasons.sort()
                for sNum in seasons:
                    subItems = []
                    episodes[sNum].sort()
                    for eNum in episodes[sNum]:
                        for item in playableItems:
                            if item['s_num'] == sNum and item['e_num'] == eNum:
                                subItems.append(MergeDicts(cItem, item, {'good_for_fav': False, 'type': 'video'}))
                    if len(subItems):
                        tmpList.append(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Season') + ' {0}'.format(sNum), 'category': 'sub_items', 'sub_items': subItems, 'prev_url': cUrl}))

            if len(tmpList) == 1:
                for item in tmpList[0]['sub_items']:
                    self.addVideo(item)
            else:
                self.currList.extend(tmpList)

            seasons.sort()
            printDBG('seasons: %s' % seasons)
            printDBG('episodes: %s' % episodes)
            printDBG('playableItems: %s' % playableItems)
            printDBG('cacheLinks: %s' % self.cacheLinks)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['category'] = 'list_items'
        cItem['url'] = self.getFullUrl('/search_99/?q=') + urllib_quote_plus(searchPattern)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'item'), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)["']''', 1, True)[0])
            item = item.split('</span>')
            title = self.cleanHtmlStr(item[0])
            desc = self.cleanHtmlStr(item[-1] + self.cm.ph.getSearchGroups(item[-1], '''rel=['"]([^"^']+?)["']''', 1, True)[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'category': 'explore_item', 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("DDLMe.getLinksForVideo [%s]" % cItem)
        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("DDLMe.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem)
        retTab = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'content'), ('', '>', 'stripe'), False)[1]

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h', '>', 'itemHeading'), ('</h', '>'), False)[1].split('<b', 1)[0])
        icon = self.cm.ph.getSearchGroups(data, '''<img([^>]+?detailCover[^>]+?)>''')[0]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''src=['"]([^"^']+?)["']''', 1, True)[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'detailDesc'), ('</p', '>'), False)[1])

        itemsList = []

        actor = []
        genre = []
        director = []
        mood = []
        praise = []
        othersTags = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'css3Tags'), ('</ul', '>'), False)
        for tmpItem in tmp:
            tmpItem = self.cm.ph.getAllItemsBeetwenMarkers(tmpItem, '<li', '</li>')
            for item in tmpItem:
                val = self.cleanHtmlStr(item.split('<span', 1)[0])
                if val != '':
                    if '/actor/' in item:
                        actor.append(val)
                    elif '/director/' in item:
                        director.append(val)
                    elif '/mood/' in item:
                        mood.append(val)
                    elif '/praise/' in item:
                        praise.append(val)
                    elif '/moviez_' in item:
                        genre.append(val)
                    else:
                        othersTags.append(val)

        try:
            year = str(int(cItem['year']))
        except Exception:
            year = self.cm.ph.getSearchGroups(title, '''\(\s*?([0-9]+?)\s*?\)$''')[0]
        if year != '':
            itemsList.append((_('Year:'), year))

        rating = self.cm.ph.getSearchGroups(data, '''<span([^>]+?ratingFill[^>]+?)>''')[0]
        try:
            rating = int(self.cm.ph.getSearchGroups(rating, '''width\s*?:\s*?([0-9]+)\%''')[0]) / 10.0
            itemsList.append((_('Rating:'), str(rating)))
        except Exception:
            printExc()

        if len(genre) == 1:
            itemsList.append((_('Genre:'), genre[0]))
        elif len(genre) > 1:
            itemsList.append((_('Genres:'), ', '.join(genre)))

        if len(director) == 1:
            itemsList.append((_('Director:'), director[0]))
        elif len(director) > 1:
            itemsList.append((_('Directors:'), ', '.join(director)))

        if len(mood) == 1:
            itemsList.append((_('Mood:'), mood[0]))
        elif len(mood) > 1:
            itemsList.append((_('Moods:'), ', '.join(mood)))

        if len(actor) == 1:
            itemsList.append((_('Actor:'), actor[0]))
        elif len(actor) > 1:
            itemsList.append((_('Actors:'), ', '.join(actor)))

        if len(praise) == 1:
            itemsList.append((_('Praise:'), praise[0]))
        elif len(praise) > 1:
            itemsList.append((_('Praises:'), ', '.join(praise)))

        if len(othersTags) > 1:
            itemsList.append((_('Others tags:'), ', '.join(othersTags)))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        printDBG('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        printDBG(itemsList)
        printDBG(icon)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': icon}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'})

        elif category == 'release_tab':
            self.listTabs(self.currItem, 'tab_items')

        elif category == 'top100_tab':
            self.listTabs(self.currItem, 'top100_subtab')
        elif category == 'top100_subtab':
            self.listSubTabs(self.currItem, 'tab_items')

        elif category == 'tab_items':
            self.listTabItems(self.currItem, 'explore_item')

        elif category == 'tags_tab':
            self.listTabs(self.currItem, 'tags')
        elif category == 'tags':
            self.listTags(self.currItem, 'sort_tags')
        elif category == 'sort_tags':
            self.listSortTags(self.currItem, 'tag_items')
        elif category == 'tag_items':
            self.listTagItems(self.currItem, 'explore_item')

        elif category == 'cat_items':
            self.listCatItems(self.currItem, 'sort_items')
        elif category == 'sort_items':
            self.listSortItems(self.currItem, 'list_items')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)
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
        CHostBase.__init__(self, DDLMe(), True, [])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
