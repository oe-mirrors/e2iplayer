# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetCookieDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from binascii import hexlify
from hashlib import md5
import re
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.vidcorn_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.vidcorn_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail"), config.plugins.iptvplayer.vidcorn_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.vidcorn_password))
    return optionList
###################################################


def gettytul():
    return 'https://vidcorn.tv/'


class VidCorn(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'vidcorn.com', 'cookie': 'vidcorn.com.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://vidcorn.org/'
        self.DEFAULT_ICON_URL = 'https://www.trackalytics.com/assets/thumbnails/vidcorn.com.jpg'

        self.filters = []
        self.cacheLinks = {}
        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG("VidCorn.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'navegacion'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            if 'dropdown' in item:
                continue
            url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
            category = url.rsplit('/', 1)[-1]
            if category not in ['series', 'peliculas', 'listas', 'gente']:
                continue
            title = self.cleanHtmlStr(item)
            params = MergeDicts(cItem, {'category': category, 'f_type': category, 'title': title, 'url': self.getFullUrl(url)})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listFilters(self, cItem, nextCategory):
        printDBG("VidCorn.listFilters")
        idx = cItem.get('f_idx', 0)
        if idx == 0:
            self.filters = []
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>', 'filter-value'), ('</ul', '>'))
            for filterData in data:
                filtersTab = []
                filterData = filterData.split('</span>', 1)
                title = self.cleanHtmlStr(filterData[0])
                if 'data-filter' in filterData[0]:
                    key = 'f_filter'
                    val = self.cm.ph.getSearchGroups(filterData[0], '''data\-filter=['"]([^'^"]+?)['"]''')[0]
                    filtersTab.append({'title': title, key: val})
                elif 'data-order-by' in filterData[0]:
                    key = 'f_order'
                    val = self.cm.ph.getSearchGroups(filterData[0], '''data\-order\-by=['"]([^'^"]+?)['"]''')[0]
                else:
                    continue

                filterData = self.cm.ph.getAllItemsBeetwenMarkers(filterData[-1], '<li', '</li>')
                for item in filterData:
                    title = self.cleanHtmlStr(item)
                    val = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                    filtersTab.append({'title': title, key: val})

                self.filters.append(filtersTab)

        if idx < len(self.filters):
            cItem = dict(cItem)
            if idx + 1 == len(self.filters):
                cItem['category'] = nextCategory
            cItem['f_idx'] = idx + 1
            self.listsTab(self.filters[idx], cItem)

    def _listItems(self, cItem, data):
        retList = []
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'data-type'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''original=['"]([^"^']+?)['"]''')[0])
            if icon == '':
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'info-'), ('</div', '>'), False)[1])
            type = self.cm.ph.getSearchGroups(item, '''data\-type=['"]([^"^']+?)['"]''')[0]

            descTab = []
            item = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'details'), ('</div', '>'), False)[1]
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in item:
                t = self.cleanHtmlStr(t)
                if t:
                    descTab.append(t)
            if type in ['series', 'peliculas']: # , 'listas', 'gente'
                nextCategory = 'explore_item'
            elif type == 'actores':
                nextCategory = 'list_actor_items'
            params = MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'f_type': type, 'icon': icon, 'desc': ' | '.join(descTab)})
            retList.append(params)
        return retList

    def listItems(self, cItem):
        printDBG("VidCorn.listItems")
        post_data = {}
        page = cItem.get('page', 0)
        post_data['page'] = str(page)
        post_data['data_type'] = cItem['f_type']
        post_data['filter_by'] = cItem.get('f_filter', 'all')
        post_data['order_by'] = cItem.get('f_order', '8')
        post_data['keyword'] = cItem.get('f_keyword', '0')
        post_data['optradio'] = cItem.get('f_optradio', '0')

        url = self.getFullUrl('/services/fetch_pages')

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return

        nextPage = True if "$('#load_more_button').show();" in data else False
        self.currList.extend(self._listItems(cItem, data))

        if nextPage:
            params = MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def _listLists(self, cItem, nextCategory, data):
        printDBG("VidCorn._listLists")
        retList = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'data-list'), ('<div', '>', 'list-content'))
        for item in data:
            listId = self.cm.ph.getSearchGroups(item, '''data\-list=['"]([^"^']+?)['"]''')[0]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])

            descTab = []
            item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<span', '>'), ('</span', '>'), False)
            for it in item:
                it = self.cleanHtmlStr(it)
                if it:
                    descTab.append(it)

            params = MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'list_id': listId, 'f_type': 'listas', 'icon': icon, 'desc': '[/br]'.join(descTab)})
            retList.append(params)
        return retList

    def listLists(self, cItem, nextCategory):
        printDBG("VidCorn.listLists")
        post_data = {}
        page = cItem.get('page', 0)
        post_data['page'] = str(page)
        post_data['order_by'] = cItem.get('f_order', '1')
        post_data['keyword'] = cItem.get('f_keyword', '0')

        url = self.getFullUrl('/services/fetch_lists')

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return

        nextPage = True if "$('#load_more_button').show();" in data else False
        self.currList.extend(self._listLists(cItem, nextCategory, data))

        if nextPage:
            params = MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listListItems(self, cItem, nextCategory):
        printDBG("VidCorn.listListItems")
        post_data = {}
        page = cItem.get('page', 0)
        post_data['page'] = str(page)
        post_data['list'] = cItem.get('list_id', '0')

        url = self.getFullUrl('/services/fetch_list_content')

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return

        nextPage = True if "$('#load_more_button').show();" in data else False
        self.currList.extend(self._listItems(cItem, data))

        if nextPage:
            params = MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listPeoples(self, cItem):
        printDBG("VidCorn.listPeoples")
        post_data = {}
        page = cItem.get('page', 0)
        post_data['page'] = str(page)
        post_data['filter_by'] = cItem.get('f_filter', '0')
        post_data['keyword'] = cItem.get('f_keyword', '0')

        url = self.getFullUrl('/services/fetch_people')

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return

        nextPage = True if "$('#load_more_button').show();" in data else False
        self.currList.extend(self._listItems(cItem, data))

        if nextPage:
            params = MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listActorItems(self, cItem):
        printDBG("VidCorn.listActorItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        printDBG(data)
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'data-type'), ('<div', '>', 'padding-top'))[1]
        self.currList.extend(self._listItems(cItem, data))

    def listSubItems(self, cItem):
        printDBG("VidCorn.listSubItems")
        self.currList = cItem['sub_items']

    def _getLinks(self, cUrl, data):
        msg = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'alert-warning'), ('</div', '>'), False)
        for t in tmp:
            t = self.cleanHtmlStr(t)
            msg.append(t)
        SetIPTVPlayerLastHostError(' '.join(msg))

        reObj = re.compile('<div[^>]+?link\-option\-head[^>]+?>')
        data = reObj.split(data)
        del data[0]

        uniqueLinks = set()
        linksTab = []
        for linksData in data:
            linksType = self.cleanHtmlStr(linksData[:linksData.find('<')]).replace(':', '')
            linksData = self.cm.ph.getAllItemsBeetwenMarkers(linksData, '<a', '</a>')
            for item in linksData:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
                if not url:
                    continue
                if url in uniqueLinks:
                    continue
                uniqueLinks.add(url)
                title = []
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
                for it in item:
                    t = ''
                    if 'link-img' not in it:
                        t = self.cleanHtmlStr(self.cm.ph.getSearchGroups(it, '''title=['"]([^"^']+?)["']''', 1, True)[0]).split(': ', 1)[-1]
                    if not t:
                        t = self.cleanHtmlStr(it)
                    if t:
                        title.append(t)
                title = '[%s] %s' % (linksType, ' | '.join(title))
                linksTab.append({'name': title, 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})
        return linksTab

    def exploreItem(self, cItem):
        printDBG("VidCorn.exploreItem")
        self.cacheLinks = {}

        if not self.loggedIn:
            self.sessionEx.open(MessageBox, 'Debes iniciar sesión para ver los enlaces.', type=MessageBox.TYPE_ERROR, timeout=10)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.getFullUrl(self.cm.meta['url'])
        self.setMainUrl(cUrl)

        desc = []
        descObj = self.getArticleContent(cItem, data)[0]
        for item in descObj['other_info']['custom_items_list']:
            desc.append(item[1])
        desc = ' | '.join(desc) + '[/br]' + descObj['text']

        trailer = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'trailer'), ('<button', '>', 'onclick'), False)[1]
        printDBG(trailer)
        title = self.cleanHtmlStr(trailer)
        trailer = self.getFullUrl(self.cm.ph.getSearchGroups(trailer, '''<iframe[^>]+?src=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
        if trailer:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': strwithmeta(trailer, {'Referer': cUrl}), 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)

        movieId = self.cm.ph.getSearchGroups(data, '''data\-movie\-id=['"]([^"^']+?)["']''', 1, True)[0]
        if not movieId:
            return

        url = self.getFullUrl('/services/fetch_links')
        sts, data = self.getPage(url, post_data={'movie': movieId, 'data_type': cItem['f_type']})
        if not sts:
            return

        linksTab = self._getLinks(cUrl, data)
        if len(linksTab):
            self.cacheLinks[cUrl] = linksTab
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': cUrl, 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)
        else:
            data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<a', '>', 'data-season'))
            for seasonData in data:
                episodes = []
                sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(seasonData, '<h4', '</h4>')[1])
                sNum = self.cm.ph.getSearchGroups(seasonData, '''data\-season=['"]([^"^']+?)["']''', 1, True)[0]

                seasonData = self.cm.ph.getAllItemsBeetwenNodes(seasonData.split('panel-body', 1)[-1], ('<a', '>', '#temporada'), ('</a', '>'))
                for item in seasonData:
                    episodeId = self.cm.ph.getSearchGroups(item, '''data\-episodio=['"]([^"^']+?)["']''', 1, True)[0]
                    url = cItem['url'] + self.cm.ph.getSearchGroups(item, '''href=['"](#[^"^']+?)["']''', 1, True)[0]

                    tab = []
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
                    for t in tmp:
                        t = self.cleanHtmlStr(t)
                        if t:
                            tab.append(t)
                    if len(tab):
                        eNum = tab[0]
                    else:
                        eNum = url.rsplit('-', 1)[-1]

                    if len(tab) > 1:
                        title = tab[1]
                    else:
                        title = ''
                    #desc = ' | '.join(tab[2:])
                    tab = []
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<small', '</small>')
                    for t in tmp:
                        t = self.cleanHtmlStr(t)
                        if t:
                            tab.append(t)
                    #desc += '[/br]' + ' | '.join(tab)
                    title = '%s: s%se%s %s' % (cItem['title'], sNum.zfill(2), eNum.zfill(2), title)
                    params = MergeDicts(cItem, {'good_for_fav': False, 'type': 'video', 'title': title, 'url': url, 'episode_id': episodeId, 'desc': desc, 'prev_url': cUrl})
                    episodes.append(params)

                if len(episodes):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': 'sub_items', 'title': sTitle, 'sub_items': episodes, 'prev_url': cUrl, 'desc': desc})
                    self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        self.tryTologin()

        url = self.getFullUrl('/buscar/') + urllib_quote_plus(searchPattern)
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        headersTitles = []
        headerData = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'search-menu'), ('</ul', '>'), False)[1]
        headerData = self.cm.ph.getAllItemsBeetwenMarkers(headerData, '<li', '</li>')
        for item in headerData:
            headersTitles.append(self.cleanHtmlStr(item))

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'search-item'), ('<div', '>', 'dialog'), False)[1]
        data = re.compile('<div[^>]+?search\-item[^>]+?>').split(data)
        for idx in range(len(data)):
            itemData = data[idx]
            if idx == 1:
                subItem = self._listLists(cItem, 'list_list_items', itemData)
            else:
                subItem = self._listItems(cItem, itemData)

            if len(subItem):
                params = MergeDicts(cItem, {'good_for_fav': False, 'category': 'sub_items', 'title': headersTitles[idx], 'sub_items': subItem})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        self.tryTologin()

        if 0 != self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        linksTab = self.cacheLinks.get(cItem['url'], [])
        if linksTab:
            return linksTab

        if cItem.get('episode_id'):
            url = self.getFullUrl('/services/fetch_links_from_episode')
            sts, data = self.getPage(url, post_data={'episode': cItem['episode_id']})
            if not sts:
                return linksTab

            printDBG(data)

            linksTab = self._getLinks(cItem['url'], data)

            if len(linksTab):
                self.cacheLinks[cItem['url']] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("VidCorn.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        linksTab = []
        urlParams = dict(self.defaultParams)
        urlParams['header'] = MergeDicts(urlParams['header'], {'Referer': videoUrl.meta['Referer']})

        sts, data = self.getPage(videoUrl, urlParams)
        if not sts:
            linksTab

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'go-link-container'), ('</div', '>'), False)[1]
        videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^"^']+?)["']''', 1, True)[0], self.cm.meta['url'])

        if 0 == self.up.checkHostSupport(videoUrl):
            urlParams['header']['Referer'] = self.cm.meta['url']
            urlParams['max_data_size'] = 0
            sts, data = self.getPage(videoUrl, urlParams)
            if sts:
                videoUrl = strwithmeta(self.cm.meta['url'], {'Referer': urlParams['header']['Referer']})
        else:
            videoUrl = strwithmeta(videoUrl, {'Referer': self.cm.meta['url']})

        if 1 == self.up.checkHostSupport(videoUrl):
            linksTab = self.up.getVideoLinkExt(videoUrl)
        return linksTab

    def getArticleContent(self, cItem, data=None):
        printDBG("HDFull.getArticleContent [%s]" % cItem)
        retTab = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            self.tryTologin()
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        data = data.split('page-content', 1)[-1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])

        tmp = data.split('titulo', 1)[-1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp, ('<h1', '>'), ('</h1', '>'), False)[1])
        title1 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp, ('<h3', '>'), ('</h3', '>'), False)[1])
        if title1:
            title = '%s (%s)' % (title, title1)

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp, ('<div', '>', 'description'), ('</div', '>'), False)[1])

        itemsList = []

        val = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'tv-status'), ('</span', '>'), False)[1])
        if val:
            itemsList.append((_('TV status'), val))

        val = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'año'), ('</span', '>'), False)[1])
        if val:
            itemsList.append((_('Year'), val))

        val = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<i', '>', 'fa-star'), ('</b', '>'), False)[1])
        if val:
            itemsList.append((_('IMDb rating'), val))

        val = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'ratingValue'), ('</div', '>'), False)[1])
        val1 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'total-item-rates'), ('</span', '>'), False)[1])
        if val1:
            val = '%s (%s)' % (val, val1)
        if val:
            itemsList.append((_('Rating'), val))

        val = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'generos'), ('</div', '>'), False)[1].split('</span>')
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t:
                val.append(t)
        if val:
            itemsList.append((_('Genres'), ', '.join(val)))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.vidcorn_login.value or\
            self.password != config.plugins.iptvplayer.vidcorn_password.value:

            loginCookie = GetCookieDir('vidcorn.com.login')
            self.login = config.plugins.iptvplayer.vidcorn_login.value
            self.password = config.plugins.iptvplayer.vidcorn_password.value

            sts, data = self.getPage(self.getMainUrl())
            if sts:
                self.setMainUrl(self.cm.meta['url'])

            freshSession = False
            if sts and '/logout' in data:
                printDBG("Check hash")
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                prevHash = ReadTextFile(loginCookie)[1].strip()

                printDBG("$hash[%s] $prevHash[%s]" % (hash, prevHash))
                if hash == prevHash:
                    self.loggedIn = True
                    return
                else:
                    freshSession = True

            rm(loginCookie)
            rm(self.COOKIE_FILE)
            if freshSession:
                sts, data = self.getPage(self.getMainUrl(), MergeDicts(self.defaultParams, {'use_new_session': True}))

            self.loggedIn = False
            if '' == self.login.strip() or '' == self.password.strip():
                return False

            if sts:
                data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login-form'), ('</form', '>'), True, False)[1]

                actionUrl = self.getFullUrl('/services/login')
                post_data = {'username': self.login, 'password': self.password}

                sitekey = self.cm.ph.getSearchGroups(data, '''sitekey=['"]([^'^"]+?)['"]''')[0]
                if sitekey != '':
                    token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'])
                    if token == '':
                        return False
                    post_data['g-recaptcha-response'] = token

                httpParams = dict(self.defaultParams)
                httpParams['header'] = MergeDicts(httpParams['header'], {'Referer': self.cm.meta['url'], 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

                sts, data = self.getPage(actionUrl, httpParams, post_data)

            if sts and data.strip() == 'success':
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                if sts:
                    data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'error-modal', ');')
                    for item in data:
                        item = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '(', ')', False)[1].strip()[1:-1])
                        if item != '':
                            msgTab.append(item)
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')

            if self.loggedIn:
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                WriteTextFile(loginCookie, hash)

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

        self.tryTologin()

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'})
        elif category in ['series', 'peliculas']:
            self.listFilters(self.currItem, 'list_items')
        elif category == 'listas':
            self.listFilters(self.currItem, 'list_list')
        elif category == 'gente':
            self.listPeoples(self.currItem)
        elif category == 'list_actor_items':
            self.listActorItems(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)

        elif category == 'list_list':
            self.listLists(self.currItem, 'list_list_items')
        elif category == 'list_list_items':
            self.listListItems(self.currItem, 'explore_item')

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
        CHostBase.__init__(self, VidCorn(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('f_type', '') in ['series', 'peliculas']:
            return True
        else:
            return False
