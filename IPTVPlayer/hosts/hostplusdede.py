# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm, GetTmpDir, GetDefaultLang, WriteTextFile, ReadTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from datetime import datetime
from hashlib import md5
from copy import deepcopy
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.plusdede_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.plusdede_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.plusdede_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.plusdede_password))
    return optionList
###################################################


def gettytul():
    return 'https://megadede.com/'


class PlusDEDE(CBaseHostClass):
    login = None
    password = None

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'plusdede.com', 'cookie': 'plusdede.com.cookie'})
        self.DEFAULT_ICON_URL = 'https://img15.androidappsapk.co/300/f/d/3/com.joramun.plusdede.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www.megadede.com/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.cacheEpisodes = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': 'Series', 'url': self.getFullUrl('/series')},
                             {'category': 'list_filters', 'title': 'Pelis', 'url': self.getFullUrl('/pelis')},
                             {'category': 'list_lists', 'title': 'Listas', 'url': self.getFullUrl('/listas')},


                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.loggedIn = None
        self.LOGIN_MARKER_FILE = self.COOKIE_FILE + '.mark'

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def calcLoginMarker(self, login, password):
        printDBG("PlusDEDE.calcLoginMarker")
        marker = md5(login + '<-------------->' + password).hexdigest()
        printDBG("marker[%s]" % marker)
        return marker

    def saveLoginMarker(self):
        printDBG("PlusDEDE.saveLoginMarker")
        marker = self.calcLoginMarker(PlusDEDE.login, PlusDEDE.password)
        printDBG("marker[%s]" % marker)
        return WriteTextFile(self.LOGIN_MARKER_FILE, marker)

    def readLoginMarker(self):
        printDBG("PlusDEDE.saveLoginMarker")
        sts, marker = ReadTextFile(self.LOGIN_MARKER_FILE)
        if not sts:
            marker = ''
        printDBG("marker[%s]" % marker)
        return marker

    def fillCacheFilters(self, cItem):
        printDBG("PlusDEDE.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = re.sub("<!--[\s\S]*?-->", "", data)

        def addFilter(data, itemMarker, valMarker, key, allTitle=None):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, valMarker + '''="([^"]+?)"''')[0]
                title = self.cm.ph.rgetDataBeetwenMarkers2(item, '</%s>' % itemMarker, '>', False)[1]
                title = self.cleanHtmlStr(title)
                if value == '':
                    if allTitle == None:
                        allTitle = title
                    continue
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if allTitle != None:
                    self.cacheFilters[key].insert(0, {'title': allTitle, key: ''})
                self.cacheFiltersKeys.append(key)

        # get sub categories
        tmpTab = []
        key = 'f_sub_cats'
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'filters'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            title = re.sub("&[^;]+?;", "", title).strip()
            tmpTab.append({'title': title, 'url': url})
        if len(tmpTab):
            self.cacheFilters[key] = tmpTab
            self.cacheFiltersKeys.append(key)

        sp = 'filter-container'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, 'medialist-filtered', False)[1].split(sp)
        for idx in range(len(data)):
            key = 'f_%s' % self.cm.ph.getSearchGroups(data[idx], '''[^>]+?name=['"]([^'^"]+?)['"]''')[0]
            if key in ['f_year']:
                #val = self.cm.ph.getSearchGroups(data[idx], '''[^>]+?value=['"]([^'^"]+?)['"]''')[0].split(';')
                #if 2 != len(val): continue
                try:
                    start = datetime.now().year #int(val[1])
                    end = 1900 #int(val[0])
                    self.cacheFilters[key] = []
                    for val in range(start, end - 1, -1):
                        self.cacheFilters[key].append({'title': str(val), key: '%s;%s' % (val, val)})
                    if len(self.cacheFilters[key]):
                        self.cacheFilters[key].insert(0, {'title': _('--Any--'), key: '%s;%s' % (end, start)})
                        self.cacheFiltersKeys.append(key)
                except Exception:
                    printExc()
            else:
                if key in ['f_quality']:
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<input', '</label>')
                    addFilter(tmp, 'label', 'value', key)
                else:
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<option', '</option>')
                    addFilter(tmp, 'option', 'value', key, _('--Any--'))

            if [] != self.cacheFilters.get(key, []):
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data[idx], '<label', '</label>')[1])
                if len(title):
                    self.cacheFilters[key].insert(0, {'title': title, 'type': 'marker'})

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("PlusDEDE.listFilters")
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
        printDBG("PlusDEDE.listMainMenu")
        if not self.loggedIn:
            return
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listLists(self, cItem, nextCategory):
        printDBG("PlusDEDE.listLists [%s]" % cItem)
        page = cItem.get('page', 0)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'load-more'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''data\-url=['"]([^'^"]+?)['"]''')[0])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'lista model'), ('<div', '>', 'media-container'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item.split('<button', 1)[0])

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', 'lista-stat'), ('</div', '>'))
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            desc = ' | '.join(desc)
            desc += '[/br]' + self.cleanHtmlStr(item.split('</h4>', 1)[-1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("PlusDEDE.listItems [%s]" % cItem)
        page = cItem.get('page', 0)

        url = cItem['url']
        if not url.endswith('/'):
            url += '/'

        if page == 0:
            if '/lista/' in url:
                url = url
            elif 'f_search_query' not in cItem:
                query = {}
                for key in self.cacheFiltersKeys:
                    if key in cItem:
                        query[key[2:]] = cItem[key]

                query = urllib.urlencode(query)
                if '?' in url:
                    url += '&' + query
                else:
                    url += '?' + query
            else:
                url += urllib.quote(cItem['f_search_query'])

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'load-more'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''data\-url=['"]([^'^"]+?)['"]''')[0])
        data = re.compile('''<div[^>]+?media\-container[^>]+?>''').split(data)
        if len(data):
            del data[0]
        reSeriesTitle = re.compile('^[0-9]+?x[0-9]+?\s')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''[\s\-]src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'media-title'), ('</div', '>'), False)[1])
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'year'), ('</div', '>'), False)[1])
            val = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<i', '>', 'star'), ('</div', '>'), False)[1])
            desc = [year, val]
            if self.cm.isValidUrl(url) and title != '':
                if '/serie/' in url:
                    desc.append(title)
                    title = reSeriesTitle.sub('', title)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
                self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("PlusDEDE.exploreItem")

        self.cacheEpisodes = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<button', '>', 'data-youtube'), ('</button', '>'))[1]
        url = self.cm.ph.getSearchGroups(tmp, '''data\-youtube=['"]([^'^"]+?)['"]''')[0]
        if url != '':
            title = '%s - %s' % (cItem['title'], self.cleanHtmlStr(tmp))
            url = 'https://www.youtube.com/watch?v=' + url
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': url})
            self.addVideo(params)

        # movie <button class="show-close-footer btn btn-primary" data-modal-class="modal-lg" data-toggle="modal" data-target="#myModal" data-href="/aportes/4/58254">ver enlaces</button>
        if 'season-links' in data:
            seasonsTitle = {}
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'season-links'), ('</ul', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            for item in tmp:
                title = self.cleanHtmlStr(item)
                sNum = self.cm.ph.getSearchGroups(item, '''data-season=['"]([^'^"]+?)['"]''')[0]
                seasonsTitle[sNum] = title
            sData = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'episode-container'), ('</ul', '>'))
            for season in sData:
                sNum = self.cm.ph.getSearchGroups(season, '''data-season=['"]([^'^"]+?)['"]''')[0]
                sTitle = seasonsTitle.get(sNum, _('Season %s') % sNum)
                episodesTab = []
                eData = self.cm.ph.getAllItemsBeetwenNodes(season, ('<a', '>', 'episode'), ('</li', '>'))
                for item in eData:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data\-href=['"]([^'^"]+?)['"]''')[0])
                    if not self.cm.isValidUrl(url):
                        continue

                    tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'name'), ('</div', '>'))[1].split('</span>', 1)
                    eNum = self.cleanHtmlStr(tmp[0])
                    eTitle = self.cleanHtmlStr(tmp[-1])
                    title = ('%s - s%se%s %s' % (cItem['title'], sNum.zfill(2), eNum.zfill(2), eTitle)).strip()
                    desc = []
                    tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'date'), ('</div', '>'))[1])
                    if tmp != '':
                        desc.append(_('Date: %s') % tmp)
                    tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<i', '>', 'wifi'), ('</div', '>'))[1])
                    if tmp != '':
                        desc.append(_('Views: %s') % tmp)
                    tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<i', '>', 'download'), ('</div', '>'))[1])
                    if tmp != '':
                        desc.append(_('Downloads: %s') % tmp)
                    tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<i', '>', 'comment'), ('</div', '>'))[1])
                    if tmp != '':
                        desc.append(_('Comments: %s') % tmp)
                    episodesTab.append({'title': title, 'url': url, 'desc': '[/br]'.join(desc)})
                if len(episodesTab):
                    self.cacheEpisodes[sNum] = episodesTab
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 's_num': sNum})
                    self.addDir(params)
        else:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<button', '>', 'show-close'), ('</button', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''data\-href=['"]([^'^"]+?)['"]''')[0])
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'url': url, 'prev_url': cItem['url']})
                self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("PlusDEDE.listEpisodes")

        sNum = cItem.get('s_num', '')
        tab = self.cacheEpisodes.get(sNum, [])
        for item in tab:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'prev_url': cItem['url']})
            params.update(item)
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("PlusDEDE.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 0 == cItem.get('page', 0):
            cItem['f_search_query'] = searchPattern
            cItem['url'] = self.getFullUrl('/search/')
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("PlusDEDE.getLinksForVideo [%s]" % cItem)
        self.tryTologin()

        retTab = []
        dwnTab = []
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

        data = data.split('<div id="download"', 1)
        for idx in range(len(data)):
            dataItem = data[idx]
            dataItem = self.cm.ph.getAllItemsBeetwenNodes(dataItem, ('<a', '>', 'data-v'), ('</a', '>'))
            for item in dataItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url):
                    printDBG("No url in link item: [%s]" % item)
                    continue
                host = self.cm.ph.getSearchGroups(item, '''src=['"][^'^"]*?/hosts/([^'^"^\.]+?)['"\.]''')[0]
                lang = self.cm.ph.getSearchGroups(item, '''src=['"][^'^"]*?/flags/([^'^"^\.]+?)['"\.]''')[0]
                #dataV = self.cm.ph.getSearchGroups(item, '''data\-v=['"]([^'^"]+?)['"]''')[0]
                #dataId = self.cm.ph.getSearchGroups(item, '''data\-id=['"]([^'^"]+?)['"]''')[0]
                titleTab = [host, lang]
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div', '</div>')
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        titleTab.append(t)
                if idx == 0:
                    retTab.append({'name': '%s' % (' | '.join(titleTab)), 'url': self.getFullUrl(url), 'need_resolve': 1})
                else:
                    dwnTab.append({'name': '%s' % (' | '.join(titleTab)), 'url': self.getFullUrl(url), 'need_resolve': 1})

        #retTab.extend(dwnTab)
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("PlusDEDE.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        sts, data = self.getPage(videoUrl)
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'visit-buttons'), ('</div', '>'))[1]
        videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]+?)['"]''')[0])
        if self.cm.isValidUrl(videoUrl):
            params = dict(self.defaultParams)
            params['max_data_size'] = 0
            self.getPage(videoUrl, params)
            videoUrl = self.cm.meta.get('url', videoUrl)
        printDBG(">> videoUrl[%s]" % videoUrl)
        urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem, data=None):
        printDBG("PlusDEDE.getArticleContent [%s]" % cItem)
        self.tryTologin()

        retTab = []

        otherInfo = {}

        if data == None:
            sts, data = self.getPage(cItem.get('prev_url', cItem['url']))
            if not sts:
                return []

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'plot'), ('</div', '>'), False)[1])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h1', '>', 'big-title'), ('</h1', '>'), False)[1])
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'avatar-container'), ('</div', '>'), False)[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''\ssrc=['"]([^'^"]+?)['"]''')[0])

        otherInfo['rating'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'item-vote'), ('</div', '>'), False)[1].split('</span>', 1)[-1])
        otherInfo['released'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<strong', '</strong>', 'Fecha'), ('</div', '>'), False)[1])
        otherInfo['duration'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<strong', '</strong>', 'Duración'), ('</div', '>'), False)[1])
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<strong', '</strong>', 'Género'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        tmpTab = []
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                tmpTab.append(t)
        otherInfo['genres'] = ', '.join(tmpTab)

        objRe = re.compile('<div[^>]+?text\-sub[^>]+?>')
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'star-container'), ('</li', '>'), False)
        stars = []
        directors = []
        for t in tmp:
            t = objRe.split(t, 1)
            t[0] = self.cleanHtmlStr(t[0])
            if t[0] == '':
                continue
            if 2 == len(t):
                t[1] = self.cleanHtmlStr(t[1])
                if t[1] == 'Director':
                    directors.append(t[0])
                    continue
            stars.append(t[0])
        if len(directors):
            otherInfo['director'] = ', '.join(directors)
        if len(stars):
            otherInfo['stars'] = ', '.join(stars)

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def tryTologin(self):
        printDBG('tryTologin start')

        if PlusDEDE.login == None and PlusDEDE.password == None:
            if self.readLoginMarker() == self.calcLoginMarker(config.plugins.iptvplayer.plusdede_login.value, config.plugins.iptvplayer.plusdede_password.value):
                PlusDEDE.login = config.plugins.iptvplayer.plusdede_login.value
                PlusDEDE.password = config.plugins.iptvplayer.plusdede_password.value
            else:
                PlusDEDE.password = ''
                PlusDEDE.login = ''
                rm(self.COOKIE_FILE)

        if True != self.loggedIn or PlusDEDE.login != config.plugins.iptvplayer.plusdede_login.value or\
            PlusDEDE.password != config.plugins.iptvplayer.plusdede_password.value:

            if True != self.loggedIn and PlusDEDE.login == config.plugins.iptvplayer.plusdede_login.value and\
                PlusDEDE.password == config.plugins.iptvplayer.plusdede_password.value:
                sts, data = self.getPage(self.getMainUrl())
                if sts:
                    token = self.cm.ph.getSearchGroups(data, '''(<meta[^>]+?_token[^>]+?/>)''')[0]
                    token = self.cm.ph.getSearchGroups(token, '''content=['"]([^"^']+?)['"]''')[0]
                    if '' != token and '/logout' in data:
                        self.HTTP_HEADER['X-CSRF-TOKEN'] = token
                        self.AJAX_HEADER['X-CSRF-TOKEN'] = token
                        self.loggedIn = True
                        return True

            PlusDEDE.login = config.plugins.iptvplayer.plusdede_login.value
            PlusDEDE.password = config.plugins.iptvplayer.plusdede_password.value
            self.saveLoginMarker()

            rm(self.COOKIE_FILE)

            self.loggedIn = False

            if '' == PlusDEDE.login.strip() or '' == PlusDEDE.password.strip():
                self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl()), type=MessageBox.TYPE_ERROR, timeout=10)
                return False

            url = self.getFullUrl('/login?popup=1')
            sts, data = self.getPage(url)
            if not sts:
                return False

            sts, tmp = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
            if not sts:
                return False

            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''action=['"]([^'^"]+?)['"]''')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<input', '>')
            post_data = {}
            for item in tmp:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value

            post_data.update({'email': PlusDEDE.login, 'password': PlusDEDE.password})

            # fill captcha
            #############################################################################################
            imgUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
            if self.cm.isValidUrl(imgUrl):
                header = dict(self.HTTP_HEADER)
                header['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
                params = dict(self.defaultParams)
                params.update({'maintype': 'image', 'subtypes': ['jpeg', 'png'], 'check_first_bytes': ['\xFF\xD8', '\xFF\xD9', '\x89\x50\x4E\x47'], 'header': header})
                filePath = GetTmpDir('.iptvplayer_captcha.jpg')
                ret = self.cm.saveWebFile(filePath, imgUrl.replace('&amp;', '&'), params)
                if not ret.get('sts'):
                    SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                    return False

                params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
                params['accep_label'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<button', '>', 'submit'), ('</button', '>'))[1])

                params['title'] = _('Captcha')
                params['status_text'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<label', '>', 'captcha'), ('</label', '>'))[1])
                params['with_accept_button'] = True
                params['list'] = []
                item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
                item['label_size'] = (300, 80)
                item['input_size'] = (480, 25)
                item['icon_path'] = filePath
                item['title'] = _('Answer')
                item['input']['text'] = ''
                params['list'].append(item)

                ret = 0
                retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
                printDBG(retArg)
                if retArg and len(retArg) and retArg[0]:
                    printDBG(retArg[0])
                    name = self.cm.ph.getDataBeetwenNodes(data, ('<input', '>', 'captcha'), ('</input', '>'))[1]
                    printDBG(name)
                    name = self.cm.ph.getSearchGroups(name, '''name=['"]([^"^']+?)['"]''')[0]
                    printDBG(name)
                    post_data['captcha'] = retArg[0][0]
            #############################################################################################

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(self.AJAX_HEADER)
            httpParams['header']['Referer'] = url
            httpParams['header']['X-CSRF-TOKEN'] = self.cm.ph.getSearchGroups(data, '''(<meta[^>]+?_token[^>]+?/>)''')[0]
            httpParams['header']['X-CSRF-TOKEN'] = self.cm.ph.getSearchGroups(httpParams['header']['X-CSRF-TOKEN'], '''content=['"]([^"^']+?)['"]''')[0]
            error = ''
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            try:
                tmp = json_loads(data)['content']
                printDBG(tmp)
                tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<div', '>', 'alert'), ('</div', '>'))
                tab = []
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t == '':
                        continue
                    tab.append(t)
                error = ', '.join(tab)
            except Exception:
                printExc()

            sts, data = self.getPage(self.getMainUrl())
            if sts and '/logout' in data:
                self.HTTP_HEADER['X-CSRF-TOKEN'] = httpParams['header']['X-CSRF-TOKEN']
                self.AJAX_HEADER['X-CSRF-TOKEN'] = httpParams['header']['X-CSRF-TOKEN']
                self.loggedIn = True
            else:
                if error == '':
                    error = _('Login failed.')
                SetIPTVPlayerLastHostError(error)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

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
        elif category == 'list_lists':
            self.listLists(self.currItem, 'list_items')
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
        CHostBase.__init__(self, PlusDEDE(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('good_for_fav', False)
