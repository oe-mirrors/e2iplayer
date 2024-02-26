# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import time
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
config.plugins.iptvplayer.filmeonlineto_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                        ("proxy_1", _("Alternative proxy server (1)")),
                                                                                        ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.filmeonlineto_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.filmeonlineto_proxy))
    if config.plugins.iptvplayer.filmeonlineto_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.filmeonlineto_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://filme-online.to/'


class FilmeOnlineTo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filme-online.to.tv', 'cookie': 'filme-online.to.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://filme-online.to/assets/images/filme-online-logo4e.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*'})
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.filmeonlineto_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})
        return self.cm.getPage(url, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.filmeonlineto_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        return url

    def selectDomain(self):
        domains = ['https://filme-online.to/']
        domain = config.plugins.iptvplayer.filmeonlineto_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        addParams = dict(self.defaultParams)
        addParams['with_metadata'] = True
        for domain in domains:
            for i in range(2):
                sts, data = self.getPage(domain, addParams)
                if sts:
                    if '/genul/action/' in data:
                        self.MAIN_URL = self.cm.getBaseUrl(data.meta['url'])
                        break
                    else:
                        continue
                break

            if self.MAIN_URL != None:
                break

        if self.MAIN_URL == None:
            self.MAIN_URL = domains[-1]

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Movies'), 'url': self.getFullUrl('/filter'), 'f_tip': 'film'},
                             {'category': 'list_filters', 'title': _('TV-Series'), 'url': self.getFullUrl('/filter'), 'f_tip': 'tv'},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]

    def fillCacheFilters(self, cItem):
        printDBG("FilmeOnlineTo.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                if ('name="%s"' % baseKey) not in item:
                    continue
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title.lower() in ['all', 'default', 'any']:
                    addAll = False
                if value in ['all', 'default', 'any']:
                    addAll = False
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        filtersData = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', '-list'), ('</ul', '>'))
        for tmp in filtersData:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            if key in ['', 'type']:
                continue
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            addFilter(tmp, 'value', key)

        key = 'f_sort'
        self.cacheFilters[key] = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '</li>', 'sortby'), ('</ul', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            value = self.cm.ph.getSearchGroups(item, '''sortby\(\s*?['"]([^'^"]+?)['"]''')[0]
            self.cacheFilters[key].append({key: value, 'title': self.cleanHtmlStr(item)})
        if len(self.cacheFilters[key]):
            self.cacheFiltersKeys.append(key)

        printDBG(self.cacheFilters)
        printDBG("++++++")
        printDBG(self.cacheFiltersKeys)
        printDBG("++++++")

    def listFilters(self, cItem, nextCategory):
        printDBG("FilmeOnlineTo.listFilters")
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

    def listItems(self, cItem, nextCategory):
        printDBG("FilmeOnlineTo.listItems")
        page = cItem.get('page', 1)
        nextPage = False
        if page == 1:
            valsTab = []
            if 'f_search' not in cItem:
                for key in ['f_tip', 'f_genres[]', 'f_year', 'f_quality', 'f_subbed', 'f_sort']:
                    valsTab.append(urllib_quote(cItem.get(key, 'all')))
                url = self.getFullUrl('tip/' + '/'.join(valsTab))
            else:
                url = self.getFullUrl('search/' + urllib_quote_plus(cItem['f_search']))
            sts, data = self.getPage(url)
            if not sts:
                return

            if 'var offset' in data:
                nextPage = True
        else:
            post_data = {}
            post_data['offset'] = page * 48
            if 'f_search' not in cItem:
                filterList = ['f_tip']
                filterList.extend(self.cacheFiltersKeys)
            else:
                filterList = ['f_search']
            for key in filterList:
                baseKey = key[2:].replace('[]', '') # "f_"
                if key in cItem:
                    post_data[baseKey] = cItem.get(key, 'all')

            params = dict(self.defaultParams)
            params['header'] = dict(self.AJAX_HEADER)
            params['header']['Referer'] = self.getMainUrl()
            url = self.getFullUrl('/ajax/filtru.php')
            sts, data = self.getPage(url, params, post_data)
            if not sts:
                return

            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<script', '</script>', False)[1]
            if 'offset' in tmp:
                nextPage = True

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'data-movie-id'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data\-original=['"]([^"^']+?)['"]''')[0])
            tmp = item.split('<h2>', 1)
            title = self.cleanHtmlStr(tmp[-1])
            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp[0], '<span', '</span>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)

            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])
            movieId = self.cm.ph.getSearchGroups(item, '''data\-movie\-id=['"]([^"^']+?)['"]''')[0]
            params = {'good_for_fav': True, 'name': 'category', 'category': nextCategory, 'title': title, 'url': url, 'movie_id': movieId, 'desc': ' | '.join(desc), 'info_url': url, 'icon': icon}
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("FilmeOnlineTo.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('var\s*?movie\s*?\=\s*?\{'), re.compile('}'))[1]
        ret = js_execute(data + '; print(JSON.stringify(movie));')
        try:
            printDBG(ret['data'])
            movieData = byteify(json.loads(ret['data']), '', True)
            url = movieData.get('trailer', '')
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'title': '%s %s' % (_('[trailer]'), self.cleanHtmlStr(movieData['name'])), 'url': url})
                self.addVideo(params)

            params = dict(self.defaultParams)
            params['header'] = dict(self.AJAX_HEADER)
            params['header']['Referer'] = cItem['url']
            url = self.getFullUrl('/ajax/mep.php?id=%s' % movieData['id'])
            sts, data = self.getPage(url, params)
            if not sts:
                return

            data = byteify(json.loads(data), '', True)
            printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            printDBG(data['html'])
            printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

            serverData = re.compile('''<div[^>]+?clearfix[^>]+?>''').split(data['html'])
            if len(serverData):
                del serverData[-1]

            linksKeys = []
            linksLinks = {}
            linksTiles = {}

            reParamsObj = re.compile('''\s*?data\-([^\=^\s]+?)\s*?=['"]([^'^"]+?)['"]''')
            for serverItem in serverData:
                sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(serverItem, '<strong', '</strong>')[1])
                serverItem = self.cm.ph.getAllItemsBeetwenMarkers(serverItem, '<a', '</a>')
                for item in serverItem:
                    title = self.cleanHtmlStr(item)
                    if cItem['title'] not in title:
                        title = '%s %s' % (cItem['title'], title)
                    params = dict(reParamsObj.findall(item))
                    try:
                        key = int(params['epNr'])
                    except Exception:
                        key = params.get('epNr', title)
                    if key not in linksKeys:
                        linksKeys.append(key)
                        linksLinks[key] = []
                        linksTiles[key] = title
                    url = '%s?ep=%s' % (cItem['url'], params.get('id', str(key) + title))
                    url = strwithmeta(url, {'params': params})
                    linksLinks[key].append({'name': sTitle, 'title': title, 'url': url, 'need_resolve': 1})

            if movieData.get('type', '') == 'tv':
                linksKeys.sort()
                for key in linksKeys:
                    url = '%s#ep=%s' % (cItem['url'], key)
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': linksTiles[key], 'url': url})
                    self.addVideo(params)
                    self.cacheLinks[url] = linksLinks[key]
            else:
                url = cItem['url']
                self.cacheLinks[url] = []
                for key in linksKeys:
                    for item in linksLinks[key]:
                        item.update({'name': '%s - %s' % (item['name'], item['title'])})
                        self.cacheLinks[url].append(item)
                if len(self.cacheLinks[url]):
                    params = dict(cItem)
                    params.update({'good_for_fav': False})
                    self.addVideo(params)
        except Exception:
            printExc()
            return

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmeOnlineTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getMainUrl()
        cItem['category'] = 'list_items'
        cItem['f_search'] = searchPattern
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("FilmeOnlineTo.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("FilmeOnlineTo.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        subTracks = []

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
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('var\s*?movie\s*?\=\s*?\{'), re.compile('}'))[1]
        ret = js_execute(data + '; print(JSON.stringify(movie));')
        try:
            movieData = byteify(json.loads(ret['data']), '', True)
            urlParams = dict(self.defaultParams)
            urlParams['header'] = dict(self.AJAX_HEADER)
            urlParams['header']['Referer'] = str(videoUrl)
            url = self.getFullUrl('/ajax/mep.php?id=%s' % movieData['id'])
            sts, data = self.getPage(url, urlParams)
            if not sts:
                return
            data = byteify(json.loads(data), '', True)

            params = dict(videoUrl.meta.get('params', {}))
            if params.get('tip', '') == 'embed':
                url = '/ajax/movie_embed.php?eid=%s&lid=undefined&ts=%s&up=0&mid=%s&gid=%s&epNr=%s&type=%s&server=%s&epIndex=%s&so=%s&srvr=%s' % (params['id'], data.get('ts', ''), movieData['id'], movieData['gid'], params['epNr'], movieData['type'], params.get('server', 'NaN'), params['index'], params['so'], params.get('srvr', 'NaN'))
                sts, data = self.getPage(self.getFullUrl(url), urlParams)
                if not sts:
                    return
                data = byteify(json.loads(data), '', True)
                url = data['src'].replace('&amp;', '&')
                urlParams = {'Referer': str(videoUrl), 'User-Agent': self.HEADER['User-Agent']}
                subsLinks = re.compile('''c([0-9]+?)_file=(https?://[^&^$]+?\.srt)[&$]''').findall(url)
                subsLabels = dict(re.compile('''c([0-9]+?)_label=([^&^/]+?)[&/]''').findall(url + '&'))
                for item in subsLinks:
                    label = subsLabels.get(item[0], 'unk')
                    subTracks.append({'title': label, 'url': strwithmeta(item[1], urlParams), 'lang': label, 'format': 'srt'})
                urlTab = self.up.getVideoLinkExt(url)
            elif params.get('tip', '') == 'vip':
                url = '/ajax/mtoken.php?eid=%s&mid=%s&so=%s&server=NaN&epNr=%s&srvr=NaN&_=%s' % (params['id'], movieData['id'], params['so'], params['epNr'], int(time.time() * 1000))
                sts, data = self.getPage(self.getFullUrl(url), urlParams)
                if not sts:
                    return
                data = dict(re.compile('''_([a-z]+?)\s*?=\s*['"]([^'^"]+?)['"]''').findall(data))
                url = '/ajax/msources.php?eid=%s&x=%s&y=%s&z=%s&ip=%s&mid=%s&gid=%s&lang=rum&epIndex=%s&server=NaN&so=%s&epNr=%s&srvr=NaN' % (params['id'], data['x'], data['y'], data['z'], data['ip'], movieData['id'], movieData['gid'], params['index'], params['so'], params['epNr'])
                sts, data = self.getPage(self.getFullUrl(url), urlParams)
                if not sts:
                    return

                urlParams = {'Referer': str(videoUrl), 'User-Agent': self.HEADER['User-Agent']}
                data = byteify(json.loads(data), '', True)
                url = self.getFullUrl(data['playlist'][0]['sources']['file'])
                if 'mp4' in data['playlist'][0]['sources']['type'].lower():
                    urlTab.append({'name': 'mp4', 'url': strwithmeta(url, urlParams), 'need_resolve': 0})
                for item in data['playlist'][0]['tracks']:
                    if item.get('kind', '').lower() != 'captions':
                        continue
                    url = self.getFullUrl(item['file'])
                    label = self.cleanHtmlStr(item['label'])
                    subTracks.append({'title': label, 'url': strwithmeta(url, urlParams), 'lang': label, 'format': 'srt'})
                printDBG(data)
        except Exception:
            printExc()

        urlParams = {'Referer': str(videoUrl), 'User-Agent': self.HEADER['User-Agent']}
        if len(subTracks):
            urlParams.update({'external_sub_tracks': subTracks})

        for idx in range(len(urlTab)):
            urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], urlParams)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("FilmeOnlineTo.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem.get('info_url', ''))
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:title"[^>]+?content="([^"]+?)"')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:description"[^>]+?content="([^"]+?)"')[0])
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<meta property="og:image"[^>]+?content="([^"]+?)"')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', '')

        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="mvic-info">', '<div class="clearfix">', False)[1]
        descData = self.cm.ph.getAllItemsBeetwenMarkers(descData, '<p', '</p>')
        descTabMap = {"Director": "director",
                      "Actor": "actors",
                      "Genre": "genre",
                      "Country": "country",
                      "Release": "released",
                      "Duration": "duration",
                      "Quality": "quality",
                      "IMDb": "rated",

                      "Genul": "genre",
                      "Actori": "actors",
                      "Director": "director",
                      "Tara": "Country",
                      "Durata": "duration",
                      "Anul": "year",
                      "Calitate": "quality"}

        otherInfo = {}
        for item in descData:
            item = item.split('</strong>')
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            val = self.cleanHtmlStr(item[1]).replace(' , ', ', ')
            if val.endswith(','):
                val = val[:-1]
            if key == 'IMDb':
                val += ' IMDb'
            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = val
                except Exception:
                    continue

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, FilmeOnlineTo(), True, [])

    def withArticleContent(self, cItem):
        if 'info_url' in cItem:
            return True
        return False
