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
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://gamatotv.me/'


class GamatoTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'gamatotv.me', 'cookie': 'gamatotv.me.cookie'})
        self.DEFAULT_ICON_URL = 'http://se5revolution.s3.amazonaws.com/uploads/10101/4200d40a-fb00-4534-ab3c-9aabaab7d4ab.jpeg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'http://gamatotv.co/'
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
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

    def listMainMenu(self, cItem, nextCategory1, nextCategory2, nextCategory3):
        printDBG("listMainMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'id="xg_navigation"', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if '/notes/' in url:
                break
            if len(url) < 2 or '/authorization/' in url:
                continue
            if url.endswith('/category'):
                category = nextCategory3
            elif url.endswith('/listFeatured'):
                category = nextCategory2
            else:
                category = nextCategory1
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': category, 'title': title, 'url': self.getFullIconUrl(url)})
            self.addDir(params)

        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listSortFilters(self, cItem, nextCategory):
        printDBG("listSortFilters")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<select onchange', '</select>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&'))
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

        if 0 == len(self.currList):
            self.listItems(cItem, 'explore_item')

    def listFilters(self, cItem, nextCategory):
        printDBG("listFilters")
        self.cacheFilters = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<strong><span class="font-size-4">', '<div class="addthis_sharing_toolbox">')[1]
        data = data.split('<span><span class="font-size-4">')
        for item in data:
            key = self.cleanHtmlStr(item.split('</span>', 1)[0])
            self.cacheFilters[key] = []
            item = item.split(',')
            for it in item:
                it = self.cm.ph.getDataBeetwenMarkers(it, '<a', '</a>')[1]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''href=['"]([^"^']+?)['"]''')[0])
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cleanHtmlStr(it)
                self.cacheFilters[key].append({'title': title, 'url': url})

            if len(self.cacheFilters[key]):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': key, 'f_key': key})
                self.addDir(params)

    def listSubFilters(self, cItem, nextCategory):
        printDBG("listSubFilters")
        key = cItem.get('f_key', '')
        tab = self.cacheFilters.get(key, [])
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']

        if page > 1:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'page=%s' % page

        sts, data = self.getPage(url)
        if not sts:
            return

        if '›</a>' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, 'xg_list_groups_main', '</ul></div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])

            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            desc = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)

            params = dict(cItem)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': '[/br]'.join(desc), 'icon': icon}
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory=''):
        printDBG("exploreItem")

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        trailer = None
        mainDesc = []
        linksTab = []
        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div[^>]+?class="xg_module_body nopad"[^>]*?>'), re.compile('<div[^>]+?like[^>]+?>'))[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in items:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0]
            name = self.cleanHtmlStr(item)
            url = url.replace('youtu.be/', 'youtube.com/watch?v=')
            if 1 == self.up.checkHostSupport(url):
                if 'youtube' in url or 'trailer' in name.lower():
                    trailer = {'name': name, 'url': url, 'need_resolve': 1}
                else:
                    linksTab.append({'name': '%s - %s' % (name, self.up.getHostName(url)), 'url': url, 'need_resolve': 1})

        items = re.sub('''<a[^>]+?>[^>]*?</a>''', "", tmp)
        items = self.cm.ph.getAllItemsBeetwenMarkers(items, '<p', '</p>')
        for item in items:
            item = self.cleanHtmlStr(item)
            if item != '':
                mainDesc.append(item)

        mainDesc.append(self.cleanHtmlStr(tmp.split('<span id="groups121">', 1)[-1]))
        mainDesc = '[/br]'.join(mainDesc)

        # trailer
        if trailer != None:
            title = '%s - %s' % (cItem['title'], _('TRAILER'))
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': trailer['url'], 'desc': trailer['name']})
            self.addVideo(params)

        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab
            params = dict(cItem)
            params.update({'good_for_fav': False, 'desc': mainDesc})
            self.addVideo(params)
        else:
            self.cacheSeasons = {}
            data = self.cm.ph.getDataBeetwenMarkers(data, 'html_module module_text', '<div class="xg_module">')[1].split('<p>', 1)[-1]

            tmp = re.compile('''>(Season[^<]*?)<''', re.IGNORECASE).split(data)
            if len(tmp) > 1:
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SEASON %s" % len(tmp[0]))
                for idx in range(2, len(tmp), 2):
                    sTitle = self.cleanHtmlStr(tmp[idx - 1])
                    sNum = self.cm.ph.getSearchGroups(sTitle, '[^0-9]([0-9]+)')[0]

                    episodesList = []
                    episodesLinks = {}

                    sItem = self.cm.ph.getAllItemsBeetwenMarkers(tmp[idx], '<a', '</a>')
                    for item in sItem:
                        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                        if 1 != self.up.checkHostSupport(url):
                            continue
                        title = self.cleanHtmlStr(item)

                        if title not in episodesList:
                            episodesList.append(title)
                            episodesLinks[title] = []
                        episodesLinks[title].append({'name': self.up.getHostName(url), 'url': url, 'need_resolve': 1})

                    if len(episodesList):
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'series_title': cItem['title'], 's_num': sNum, 'title': sTitle, 'e_list': episodesList, 'e_links': episodesLinks, 'desc': mainDesc})
                        self.addDir(params)

                return

            tmp = re.split('''(<img[^>]+?\.jpg[^>]+?>)''', data)
            if len(data) > 1: # collection
                for idx in range(1, len(tmp), 1):
                    printDBG("++++++++++++++++++++++++++++++++++++++++")
                    item = tmp[idx]
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<span[^>]+?style="text-decoration: underline;"[^>]*?>'), re.compile('</span>'))[1])
                    if title == '':
                        title = self.cleanHtmlStr(self.cm.ph.rgetDataBeetwenMarkers2(item, '</a>', '<a')[1])
                    if title == '':
                        title = self.cleanHtmlStr(item)
                    icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tmp[idx - 1], '''src=['"]([^'^"]+?)['"]''')[0])
                    if icon == '':
                        icon = cItem.get('icon', '')
                    linksTab = []
                    item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
                    for it in item:
                        url = self.cm.ph.getSearchGroups(it, '''href=['"]([^"^']+?)['"]''')[0]
                        printDBG(">>> [%s]" % url)
                        url = re.split('''(https?://)''', url)
                        if len(url) > 1:
                            url = url[-2] + url[-1]
                        else:
                            continue
                        name = self.cleanHtmlStr(it)
                        if 0 == len(linksTab) and 'gamato' in url and '/group/' in url:
                            url = self.getFullUrl('/group/' + url.split('/group/')[-1])
                            params = dict(cItem)
                            params.update({'good_for_fav': True, 'url': url, 'title': title, 'icon': icon, 'desc': mainDesc})
                            self.addDir(params)
                            break
                        elif 1 == self.up.checkHostSupport(url):
                            linksTab.append({'name': self.up.getHostName(url), 'url': url, 'need_resolve': 1})

                    if len(linksTab):
                        url = cItem['url'] + '&title=' + title
                        self.cacheLinks[url] = linksTab
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'url': url, 'title': title, 'icon': icon, 'desc': mainDesc})
                        self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("listEpisodes")

        cItem = dict(cItem)
        sNum = cItem.pop('s_num', '')
        sTitle = cItem.pop('series_title', '')
        episodesList = cItem.pop('e_list', [])
        episodesLinks = cItem.pop('e_links', {})

        for eNum in episodesList:
            title = '%s s%se%s' % (sTitle, sNum.zfill(2), eNum.zfill(2))
            url = cItem['url'] + '&sNum=%s&eNum=%s' % (sNum.zfill(2), eNum.zfill(2))
            self.cacheLinks[url] = episodesLinks[eNum]

            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': url})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/groups/group/search?ie=UTF-8&sa=Search&q=' + urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("getLinksForVideo [%s]" % cItem)
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            return self.up.getVideoLinkExt(cItem['url'])

        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("getVideoLinks [%s]" % videoUrl)
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

        if 1 != self.up.checkHostSupport(videoUrl):
            httpParams = dict(self.defaultParams)
            httpParams['max_data_size'] = 0
            self.cm.getPage(url, httpParams, post_data)
            if 'url' in self.cm.meta:
                videoUrl = self.cm.meta['url']
            else:
                return []

            if self.up.getDomain(self.getMainUrl()) in videoUrl or self.up.getDomain(videoUrl) == self.up.getDomain(orginUrl):
                sts, data = self.getPage(videoUrl)
                if not sts:
                    return []

                found = False
                printDBG(data)
                tmp = re.compile('''<iframe[^>]+?src=['"]([^"^']+?)['"]''', re.IGNORECASE).findall(data)
                for url in tmp:
                    if 1 == self.up.checkHostSupport(url):
                        videoUrl = url
                        found = True
                        break
                if not found or 'flashx' in videoUrl:
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, 'embedFrame', '</a>')
                    for urlItem in tmp:
                        url = self.cm.ph.getSearchGroups(urlItem, '''href=['"](https?://[^'^"]+?)['"]''')[0]
                        if 1 == self.up.checkHostSupport(url):
                            videoUrl = url
                            found = True
                            break

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem.get('prev_url', '')
        if url == '':
            url = cItem.get('url', '')

        sts, data = self.getPage(url)
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<meta[^>]+?itemprop="name"[^>]+?content="([^"]+?)"''')[0])
        icon = self.cm.ph.getDataBeetwenMarkers(data, '<div id="poster"', '</div>')[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div[^>]+?class="wp-content"[^>]*?>'), re.compile('</div>'))[1])

        mapDesc = {'Original title': 'alternate_title', 'IMDb Rating': 'imdb_rating', 'TMDb Rating': 'tmdb_rating', 'Status': 'status',
                   'Firt air date': 'first_air_date', 'Last air date': 'last_air_date', 'Seasons': 'seasons', 'Episodes': 'episodes'}
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="custom_fields">', '</div>')
        for item in tmp:
            item = item.split('<span class="valor">')
            if len(item) < 2:
                continue
            marker = self.cleanHtmlStr(item[0])
            key = mapDesc.get(marker, '')
            if key == '':
                continue
            value = self.cleanHtmlStr(item[1])
            if value != '':
                otherInfo[key] = value

        mapDesc = {'Director': 'directors', 'Cast': 'cast', 'Creator': 'creators'}

        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div id="cast"[^>]+?>'), re.compile('fixidtab'))[1]
        tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(tmp, '</div>', '<h2>')
        for item in tmp:
            marker = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            key = mapDesc.get(marker, '')
            if key == '':
                continue
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="name">', '</div>')
            value = []
            for t in item:
                t = self.cleanHtmlStr(t)
                if t != '':
                    value.append(t)
            if len(value):
                otherInfo[key] = ', '.join(value)

        key = 'genres'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sgeneros">', '</div>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        value = []
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                value.append(t)
        if len(value):
            otherInfo[key] = ', '.join(value)

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="starstruck-rating">', '</div>')[1])
        if tmp != '':
            otherInfo['rating'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="qualityx">', '</span>')[1])
        if tmp != '':
            otherInfo['quality'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="country">', '</span>')[1])
        if tmp != '':
            otherInfo['country'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="runtime">', '</span>')[1])
        if tmp != '':
            otherInfo['duration'] = tmp

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
            self.listMainMenu({'name': 'category', 'url': self.getFullUrl('groups')}, 'list_sort_filters', 'list_items', 'list_filters')
        elif category == 'list_sort_filters':
            self.listSortFilters(self.currItem, 'list_items')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_sub_filters')
        elif category == 'list_sub_filters':
            self.listSubFilters(self.currItem, 'list_sort_filters')
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
        CHostBase.__init__(self, GamatoTV(), True, [])

    def withArticleContent(self, cItem):
        return False
        if (cItem['type'] == 'video' and '/episodes/' not in cItem['url']) or cItem['category'] == 'explore_item':
            return True
        return False
