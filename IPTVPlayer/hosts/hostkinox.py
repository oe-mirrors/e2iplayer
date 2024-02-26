# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kinox_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                     ("proxy_1", _("Alternative proxy server (1)")),
                                                                                     ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.kinox_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kinox_proxy))
    if config.plugins.iptvplayer.kinox_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.kinox_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://kinox.to/'


class Kinox(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kinox.to', 'cookie': 'kinox.to.com.cookie'})
        self.DEFAULT_ICON_URL = 'https://www.medienrecht-urheberrecht.de/images/Urteil_streaming-plattform.PNG'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.cacheSubCategories = []
        self.cacheLangFlags = {'list': [], 'map': {}}
        self.cacheLinks = {}
        self.cacheSeasons = {}
        self.cacheNewTab = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items': {'ListMode': 'cover', 'CinemaMode': 'cover'}}

    def selectDomain(self):
        domains = ['https://kinoz.to/', 'https://kinox.bz/', 'http://kinox.ag/', 'http://kinox.me/', 'https://kinox.am/', 'http://kinox.nu/', 'http://kinox.pe/', 'http://kinox.sg/', 'http://kinox.to/', 'http://kinox.tv/']
        domain = config.plugins.iptvplayer.kinox_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        confirmedDomain = None
        for domain in domains:
            self.MAIN_URL = domain
            for i in range(2):
                sts, data = self.getPage(domain)
                if sts:
                    if '/Wizard.html' in data:
                        confirmedDomain = domain
                        break
                    else:
                        continue
                break

            if confirmedDomain != None:
                break

        if confirmedDomain == None:
            self.MAIN_URL = 'https://kinox.to/'

        self.MAIN_CAT_TAB = [{'category': 'news', 'title': _('News'), 'url': self.getMainUrl()},
                             {'category': 'list_langs', 'title': _('Cinema movies'), 'url': self.getFullUrl('/Kino-filme.html'), 'get_list_mode': 'direct'},
                             {'category': 'list_sub_cats', 'title': _('Movies'), 'url': self.getMainUrl(), 'f_type': 'movie', 'sub_idx': 2},
                             {'category': 'list_sub_cats', 'title': _('Documentaries'), 'url': self.getMainUrl(), 'f_type': 'documentation', 'sub_idx': 3},
                             {'category': 'list_sub_cats', 'title': _('Series'), 'url': self.getMainUrl(), 'f_type': 'series', 'sub_idx': 4},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        proxy = config.plugins.iptvplayer.kinox_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def fillCacheFilters(self, cItem):
        printDBG("Kinox.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # add letter
        key = 'f_letter'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="LetterExtension"', '</div>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        tab = []
        for item in tmp:
            letter = self.cleanHtmlStr(item)
            params = {'title': letter}
            if len(letter) == 1:
                params[key] = letter
            tab.append(params)

        if len(tab):
            self.cacheFilters[key] = tab
            self.cacheFiltersKeys.append(key)

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title in ['Összes']:
                    addAll = False
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="search_option">', '</div>')
        for tmp in data:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            if key not in ['genre', 'country']:
                continue
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            addFilter(tmp, 'value', key, True)

        printDBG(self.cacheFilters)

    def listNewsCats(self, cItem, nextCategory):
        printDBG("Kinox.listNewsCats")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<ul[^>]+?id=['"]pmNews['"][^>]*?>'''), re.compile('</ul>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue

            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listNewTab(self, cItem, nextCategory):
        printDBG("Kinox.listNewTab")

        self.cacheNewTab = {}

        langsMap = self.getLangFlags().get('map', {})
        langsList = self.getLangFlags().get('list', {})
        lang = cItem.get('f_lang', '')
        if lang == '':
            self.defaultParams['cookie_items'].pop('ListNeededLanguage', None)
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['ListNeededLanguage'])
        else:
            notNeededLanguages = list(langsList)
            if lang in notNeededLanguages:
                notNeededLanguages.remove(lang)
            self.defaultParams['cookie_items']['ListNeededLanguage'] = ','.join(notNeededLanguages)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.rgetAllItemsBeetwenMarkers(data, '</table>', '<div class="ModuleHead mHead">')
        for tab in data:
            tTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tab, '<h1', '</h1>')[1])
            tHead = self.cm.ph.getDataBeetwenMarkers(tab, '<thead', '</thead>')[1]
            tHead = self.cm.ph.getAllItemsBeetwenMarkers(tab, '<th', '</th>')

            printDBG('TITLE [%s]' % tTitle)
            self.cacheNewTab[tTitle] = []
            tab = self.cm.ph.getAllItemsBeetwenMarkers(tab, '<tr', '</tr>')
            for item in tab:
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
                if len(item) < 6:
                    continue

                url = self.getFullUrl(self.cm.ph.getSearchGroups(item[1], '''href=['"]([^'^"]+?\.html)''')[0])
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item[1], 'title="([^"]+?)"')[0])
                if title == '':
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item[1], "title='([^']+?)'")[0])
                langId = self.cm.ph.getSearchGroups(item[0], '''/lng/([0-9]+?)\.png''')[0]
                desc = _('Language') + ': ' + langsMap.get(langId, _('Unknown')) + ' | ' + _('Rating') + ': ' + self.cleanHtmlStr(item[5])
                desc = self.cleanHtmlStr(item[1]) + '[/br]' + desc
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item[1], '''rel=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
                self.cacheNewTab[tTitle].append({'url': url, 'title': title, 'icon': icon, 'desc': desc})

            if len(self.cacheNewTab[tTitle]):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'news_tab_key': tTitle, 'category': nextCategory, 'title': tTitle})
                self.addDir(params)

    def listNewsItems(self, cItem, nextCategory):
        printDBG("Kinox.listNewsItems")
        key = cItem.get('news_tab_key', '')
        tab = self.cacheNewTab.get(key, [])

        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': True, 'category': nextCategory})
            self.addDir(params)

    def listFilters(self, cItem, nextCategory):
        printDBG("Kinox.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if 0 == len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def getLangFlags(self):
        if 0 == len(self.cacheLangFlags.get('list', [])):
            langList = []
            langMap = {}
            sts, data = self.getPage(self.getFullUrl('/Options.html'))
            if sts:
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<button class="InOptBtn"', '</button>')
                for item in data:
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0])
                    langId = self.cm.ph.getSearchGroups(item, '''/lng/([0-9]+?)\.png''')[0]
                    langList.append(langId)
                    langMap[langId] = title

            self.cacheLangFlags = {'list': langList, 'map': langMap}
        printDBG(self.cacheLangFlags)
        return self.cacheLangFlags

    def listsLangFilter(self, cItem, nextCategory):
        printDBG("Kinox.listsLangFilter [%s]" % cItem)

        langsMap = dict(self.getLangFlags().get('map', {}))
        langsList = list(self.getLangFlags().get('list', {}))
        langsList.insert(0, '')
        langsMap[''] = _('All')
        for lang in langsList:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': langsMap.get(lang, lang)})
            if lang != '':
                params['f_lang'] = lang
            self.addDir(params)

    def listsSubCategories(self, cItem, nextCategory):
        printDBG("Kinox.listsSubCategories [%s]" % cItem)

        subIdx = cItem.get('sub_idx')
        if subIdx == None:
            return

        if subIdx >= len(self.cacheSubCategories):
            self.cacheSubCategories = []

            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="sub"', '<li class="space"')
            for item in data:
                subCats = []
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
                for it in item:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''href=['"]([^'^"]+?)['"]''')[0])
                    if not self.cm.isValidUrl(url):
                        continue
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(it, '<a', '</a>')[1])
                    if 0 == len(subCats):
                        mode = 'post_mode'
                    else:
                        mode = 'direct'

                    subCats.append({'url': url, 'title': title, 'get_list_mode': mode})
                self.cacheSubCategories.append(subCats)

        if subIdx >= len(self.cacheSubCategories):
            return

        subCats = self.cacheSubCategories[subIdx]
        for item in subCats:
            params = dict(cItem)
            params.update(item)
            params['category'] = nextCategory
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("Kinox.listItems [%s]" % cItem)
        ITEMS_PER_PAGE = 30
        page = cItem.get('page', 0)
        url = cItem['url']

        langsMap = self.getLangFlags().get('map', {})
        langsList = self.getLangFlags().get('list', {})
        lang = cItem.get('f_lang', '')
        if lang == '':
            self.defaultParams['cookie_items'].pop('ListNeededLanguage', None)
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['ListNeededLanguage'])
        else:
            notNeededLanguages = list(langsList)
            if lang in notNeededLanguages:
                notNeededLanguages.remove(lang)
            self.defaultParams['cookie_items']['ListNeededLanguage'] = ','.join(notNeededLanguages)

        nextPage = False
        listMode = cItem.get('get_list_mode', 'direct')
        if listMode == 'direct':
            url = cItem['url']

            query = {}
            if 'f_lang' in cItem:
                query['language'] = cItem['f_lang']
            if 'f_genre' in cItem:
                query['genre'] = cItem['f_genre']
            if 'f_country' in cItem:
                query['country'] = cItem['f_country']
            if query != {}:
                query.update({'q': '', 'actors': '', 'imdbop': '', 'imdbrating': '', 'year': '', 'extended_search': 1})
            query = urllib_urlencode(query)
            if query != '':
                url += '?' + query

            sts, data = self.getPage(url)
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="ModuleHead', '/Contact.html')[1]
        else:
            lettersMap = {'#': 1}
            additionalParams = {"Length": ITEMS_PER_PAGE, "Search": "", "Subtitle": "", "iDisplayStart": page * ITEMS_PER_PAGE, "iDisplayLength": ITEMS_PER_PAGE}
            if 'f_type' in cItem:
                additionalParams['fType'] = cItem['f_type']
            if 'f_letter' in cItem:
                additionalParams['fLetter'] = lettersMap.get(cItem['f_letter'], cItem['f_letter'])
            if 'f_genre' in cItem:
                additionalParams['fGenre'] = cItem['f_genre']
            if 'f_country' in cItem:
                additionalParams['fCountry'] = cItem['f_country']
            if 'f_lang' in cItem:
                additionalParams['onlyLanguage'] = cItem['f_lang']

            post_data = {'Page': page, 'Per_Page': ITEMS_PER_PAGE, 'per_page': ITEMS_PER_PAGE, 'dir': 'desc', 'sort': 'title', 'ListMode': 'cover', 'additional': ensure_str(json.dumps(additionalParams))}
            sts, data = self.getPage(self.getFullUrl('/aGET/List/'), post_data=post_data)
            if not sts:
                return

            try:
                data = byteify(json.loads(data))
                if ((page + 1) * ITEMS_PER_PAGE) < data['Total']:
                   nextPage = True
                data = data['Content']
            except Exception:
                printExc()
                return

        data = self.cm.ph.rgetAllItemsBeetwenMarkers(data, '<div class="ModuleFooter">', '<div class="ModuleHead')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            langId = self.cm.ph.getSearchGroups(item, '''/lng/([0-9]+?)\.png''')[0]
            desc = _('Language') + ': ' + langsMap.get(langId, _('Unknown')) + ' | ' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<div[^>]*?class="Genre"[^>]*?>'), re.compile('<div class="clearboth">'))[1].replace('<div class="floatright">', '|')).replace(' , ', ', ')
            desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<div[^>]*?class="Descriptor"[^>]*?>'), re.compile('</div>'))[1])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory=''):
        printDBG("Kinox.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<select[^>]+?id=['"]SeasonSelection['"][^>]*?>'''), re.compile('''</select>'''))[1]
        if data != '':
            sKey = 0
            self.cacheSeasons = {}

            baseEpisodeUrl = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<select[^>]+?rel=['"]([^'^"]+?)['"]''')[0])
            if baseEpisodeUrl == "":
                return

            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
            for sItem in data:
                sTtile = self.cleanHtmlStr(sItem)
                sNum = self.cleanHtmlStr(self.cm.ph.getSearchGroups(sItem, '''value=['"]([0-9]+?)['"]''')[0])

                episodesList = []
                sItem = self.cm.ph.getSearchGroups(sItem, '''rel=['"]([^'^"]+?)['"]''')[0].split(',')
                for item in sItem:
                    try:
                        eNum = str(int(item))
                    except Exception:
                        continue
                        printExc()

                    url = self.getFullUrl('/aGET/MirrorByEpisode/%s&Season=%s&Episode=%s' % (baseEpisodeUrl, sNum, eNum))
                    url = strwithmeta(url, {'Referer': cItem['url']})

                    title = '%s s%se%s' % (cItem['title'], sNum.zfill(2), eNum.zfill(2))
                    params = {'title': title, 'url': url, 'prev_url': cItem['url']}
                    episodesList.append(params)

                if len(episodesList):
                    self.cacheSeasons[sKey] = episodesList

                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTtile, 's_key': sKey})
                    self.addDir(params)
                    sKey += 1
        else:
            params = dict(cItem)
            params.update({'good_for_fav': True})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("Kinox.listEpisodes")

        sKey = cItem.get('s_key', -1)
        episodesList = self.cacheSeasons.get(sKey, [])

        for item in episodesList:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': False})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Kinox.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['get_list_mode'] = 'direct'
        cItem['url'] = self.getFullUrl('/Search.html?q=' + urllib_quote_plus(searchPattern))
        self.listsLangFilter(cItem, 'list_items')

    def getLinksForVideo(self, cItem):
        printDBG("Kinox.getLinksForVideo [%s]" % cItem)
        retTab = []
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheTab = self.cacheLinks.get(cItem['url'], [])
        if len(cacheTab):
            return cacheTab

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return retTab

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<ul[^>]+?id=['"]HosterList['"]'''), re.compile('</ul>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''rel=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            name = self.cleanHtmlStr(item)

            url = self.getFullUrl('/aGET/Mirror/' + url)
            if self.cm.isValidUrl(url):
                retTab.append({'name': name, 'url': url, 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cItem['url']] = retTab

        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("Kinox.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []
        orginUrl = str(videoUrl)

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        sts, data = self.getPage(videoUrl)
        if not sts:
            return []

        try:
            data = byteify(json.loads(data))
            if 'Stream' in data:
                data = data['Stream']
                videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
                if videoUrl == '':
                    videoUrl = self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^"^']+?)['"]''', 1, True)[0]
                printDBG(">>>>>> [%s]" % videoUrl)
                if videoUrl.startswith('//'):
                    videoUrl = 'https:' + videoUrl
                if not self.cm.isValidUrl(videoUrl):
                    url = videoUrl.split('?s=', 1)[1]
                    if videoUrl.startswith('//'):
                        videoUrl = 'https:' + videoUrl
        except Exception:
            printExc()
            return []

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("Kinox.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem.get('prev_url', '')
        if url == '':
            url = cItem.get('url', '')

        sts, data = self.getPage(url)
        if not sts:
            return retTab

        data1 = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?class=['"]Grahpics["']'''), re.compile('''<div[^>]+?class=['"]ModuleFooter['"][^>]*?>'''))[1]
        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<table[^>]+?class=['"]CommonModuleTable["']'''), re.compile('''</table>'''))[1]

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data1, '''alt=['"]([^'^"]+?)['"]''')[0])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data1, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data1, re.compile('''<div[^>]+?class="Descriptore"[^>]*?>'''), re.compile('</div>'))[1])

        mapDesc = {'director': 'director', 'country': 'country', 'runtime': 'duration', 'genre': 'genres', 'views': 'views'}
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data1, '<li', '</li>')
        for item in tmp:
            marker = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0].lower()
            value = self.cleanHtmlStr(item)
            key = mapDesc.get(marker, '')
            if key == '':
                continue
            if value != '':
                otherInfo[key] = value

        mapDesc = {'fsk:': 'age_limit', 'imdb wertung:': 'imdb_rating', 'genre:': 'genres', 'schauspieler:': 'actors'}
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in tmp:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(item) < 2:
                continue

            marker = self.cleanHtmlStr(item[0]).lower()

            value = self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<a', '</a>')
            if len(value) > 1:
                value = ', '.join([self.cleanHtmlStr(x) for x in value])
            else:
                value = self.cleanHtmlStr(item[1])

            key = mapDesc.get(marker, '')
            if key == '':
                continue
            if value != '':
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
            self.selectDomain()
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        if category == 'news':
            self.listNewsCats(self.currItem, 'list_news_tabs')
        elif category == 'list_news_tabs':
            self.listNewTab(self.currItem, 'list_news_items')
        elif category == 'list_news_items':
            self.listNewsItems(self.currItem, 'explore_item')
        elif category == 'list_langs':
            self.listsLangFilter(self.currItem, 'list_items')
        elif category == 'list_sub_cats':
            self.listsSubCategories(self.currItem, 'list_filters')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_langs')
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
        CHostBase.__init__(self, Kinox(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] == 'video' or cItem.get('category') in ['explore_item', 'list_episodes']:
            return True
        return False
