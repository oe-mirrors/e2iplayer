# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
import urllib.parse
import string
import math
import random
from datetime import datetime
from hashlib import md5
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
config.plugins.iptvplayer.treetv_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.treetv_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail"), config.plugins.iptvplayer.treetv_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.treetv_password))
    return optionList
###################################################


def gettytul():
    return 'http://tree.tv/'


class TreeTv(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'TreeTv.tv', 'cookie': 'treetv.cookie'})
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items': {'mycook': md5(str(time.time())).hexdigest()}}

        self.MAIN_URL = 'http://tree.tv/'
        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/xplugin.video.tree.tv.dev.png.pagespeed.ic.bFRA1qn2nT.png'

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Movies'), 'url': self.getFullUrl('/films'), 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('/serials'), 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_items', 'title': _('Cartoons'), 'url': self.getFullUrl('/multfilms'), 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_items', 'title': _('Anime'), 'url': self.getFullUrl('/anime'), 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_items', 'title': _('TV Shows'), 'url': self.getFullUrl('/onlinetv'), 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_collections', 'title': _('Collections'), 'url': self.getFullUrl('/collection'), 'icon': self.DEFAULT_ICON_URL},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'search_history', 'title': _('Search history'), 'icon': self.DEFAULT_ICON_URL}
                            ]

        self.cacheFilters = {}
        self.filtersTab = []
        self.cacheLinks = []
        self.login = ''
        self.password = ''

    def getPage(self, url, params={}, post_data=None):
        sts, data = self.cm.getPage(url, params, post_data)
        if sts:
            if 'lawfilter' in self.cm.meta['url']:
                msg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'message'), ('</div', '>'), False)[1])
                if msg != '':
                    GetIPTVNotify().push(msg, 'info', 10)
        return sts, data

    def getStr(self, item, key):
        if key not in item:
            return ''
        if item[key] == None:
            return ''
        return str(item[key])

    def fillFilters(self, cItem):
        self.cacheFilters = {}
        self.filtersTab = []
        sts, data = self.getPage(cItem['url']) # it seems that series and movies have same filters
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        def addFilter(data, key, addAny, titleBase, type=0):
            self.cacheFilters[key] = []
            for item in data:
                if 0 == type:
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                elif 1 == type:
                    value = self.cm.ph.getSearchGroups(item, '''\{[^:]+?\s*:\s*['"]([^"^']+?)['"]''')[0]
                elif 2 == type:
                    value = self.cm.ph.getSearchGroups(item, '''data-rel=['"]([^'^"]+?)['"]''')[0]
                elif 3 == type:
                    value = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                self.cacheFilters[key].append({'title': titleBase + title, key: value})
            if addAny and len(self.cacheFilters[key]):
                self.cacheFilters[key].insert(0, {'title': _('Any')})

        # production -> production
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, 'production_links', '</div')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<a ', '</a>', withMarkers=True)
        addFilter(tmpData, 'production', True, '', 1)
        if len(self.cacheFilters.get('production', [])):
            self.filtersTab.append('production')

        # genres -> janrs
        sts, tmpData = self.getPage(self.getFullUrl('default/index/janrs?_=' + str(time.time())))
        if sts:
            tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<a ', '</a>', withMarkers=True)
            addFilter(tmpData, 'genres', True, '', 2)
        if len(self.cacheFilters.get('genres', [])):
            self.filtersTab.append('genres')

        # year
        self.cacheFilters['year'] = []
        year = datetime.now().year
        while year >= 1978:
            self.cacheFilters['year'].append({'title': _('Year: ') + str(year), 'year': year})
            year -= 1
        if len(self.cacheFilters['year']):
            self.cacheFilters['year'].insert(0, {'title': _('Year: ') + _('Any')})
            self.filtersTab.append('year')

        # quality -> quality
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<h2 class="main_janrs_title"', '<div class="apply_q"')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<div class="quality_item both">', '</a>', withMarkers=True)
        addFilter(tmpData, 'quality', True, '', 3)
        if len(self.cacheFilters.get('quality', [])):
            self.filtersTab.append('quality')

        # sortType
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="left_menu" id="left_menu">', '</div')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<a ', '</a>', withMarkers=True)
        addFilter(tmpData, 'sort', False, '', 1)
        if len(self.cacheFilters.get('sort', [])):
            self.filtersTab.append('sort')

    def listFilter(self, cItem, filters):
        params = dict(cItem)
        idx = params.get('f_idx', 0)
        params['f_idx'] = idx + 1

        if idx == 0:
            self.fillFilters(cItem)

        tab = self.cacheFilters.get(filters[idx], [])
        self.listsTab(tab, params)

    def listItems(self, cItem, nextCategory):
        printDBG("TreeTv.listItems")
        page = cItem.get('page', 1)
        baseUrl = cItem['url']

        if cItem.get('sort', '') not in ['']:
            baseUrl += '/sortType/{0}'.format(cItem['sort'])

        if page > 1:
            baseUrl += '/page/{0}'.format(page)

        if cItem.get('year', '') not in ['']:
            baseUrl += '/year/{0}'.format(cItem['year'])

        if cItem.get('production', '') not in ['']:
            baseUrl += '/production/{0}'.format(cItem['production'])

        if cItem.get('genres', '') not in ['']:
            baseUrl += '/janrs/{0}'.format(cItem['genres'])

        if cItem.get('quality', '') not in ['']:
            baseUrl += '/quality/{0}'.format(cItem['quality'])

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = self.MAIN_URL

        sts, data = self.getPage(self.getFullUrl(baseUrl), params)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        if 'class="next"' in data:
            nextPage = True
        else:
            nextPage = False

        #data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="preview">', '<div id="left_up">', withMarkers=True)[1]
        #data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="preview">', '<div class="clear">', withMarkers=True)
        m1 = '<div class="preview">'
        for m2 in ['<div class="navigation', '<div class="t_center">', '<div class="right']:
            if m2 in data:
                break
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, withMarkers=False)[1]
        data = data.split(m1)
        for item in data:
            tmp = self.cm.ph.rgetDataBeetwenMarkers2(item, '<div class="item_content">', '<a ')[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, 'alt="', '" ', withMarkers=False)[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2>', '</h2>', withMarkers=False)[1])
            desc = self.cleanHtmlStr(item)
            params = {'category': nextCategory, 'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("TreeTv.exploreItem")
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        data = re.sub("<!--[\s\S]*?-->", "", data)

        # trailer
        item = ph.find(data, ('<div ', '>', 'film_play_button'), '</div>')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(item)
        if self.cm.isValidUrl(url):
            self.addVideo({'good_for_fav': False, 'title': title, 'icon': cItem['icon'], 'urls': [{'name': '', 'url': url}]})

        printDBG(data)

        keyTab = []
        linksTab = {}
        marker = '<div class="accordion_item">'
        data = self.cm.ph.getDataBeetwenMarkers(data, marker, '<hr/>', withMarkers=False)[1]
        data = data.split(marker)
        for item in data:
            baseTitle = self.cleanHtmlStr(item.split('<div class="accordion_content')[0])
            linksTitle = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0]
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="quality">', '<div class="clear">', withMarkers=True)
            for tmp in tmpTab:
                title = baseTitle #+ ' - ' + self.cleanHtmlStr(tmp.split('<div class="film_actions">')[0])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''data-href=['"]([^'^"]+?)['"]''')[0])
                key = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<a ', '</a>', withMarkers=True)[1]).upper()
                if key not in keyTab:
                    keyTab.append(key)
                    linksTab[key] = {'urls': [], 'title': linksTitle}
                linksTab[key]['urls'].append({'name': title, 'url': url})

        for key in keyTab:
            self.addVideo({'good_for_fav': False, 'title': linksTab[key]['title'], 'desc': key, 'icon': cItem['icon'], 'urls': linksTab[key]['urls']})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TreeTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        baseUrl = self.getFullUrl('search?usersearch={0}&filter=name'.format(urllib.parse.quote_plus(searchPattern)))
        sts, data = self.getPage(baseUrl)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        cItem = dict(cItem)
        cItem['url'] = baseUrl

        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("TreeTv.getLinksForVideo [%s]" % cItem)
        urlTab = []

        # self.cacheLinks to links in item
        self.cacheLinks = cItem.get('urls', [])

        for item in self.cacheLinks:
            url = item['url']
            name = item['name']
            urlTab.append({'name': name, 'url': url, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("TreeTv.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        for idx in range(len(self.cacheLinks)):
            if videoUrl == self.cacheLinks[idx]['url']:
                if not self.cacheLinks[idx]['name'].startswith('*'):
                    self.cacheLinks[idx]['name'] = '*' + self.cacheLinks[idx]['name']
                break

        #sts, data = self.getPage('http://tree.tv/film/index/imprint', self.defaultParams, {'result':self.defaultParams['cookie_items']['mycook']})

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = str('http://tree.tv/')
        params['raw_post_data'] = True

        sts, data = self.getPage(self.getFullUrl('/film/index/imprint'), params, 'result=' + self.defaultParams['cookie_items']['mycook'] + '&components%5B0%5D%5Bkey%5D=user_agent&components%5B0%5D%5Bvalue%5D=Mozilla%2F5.0+(Windows+NT+6.1%3B+WOW64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+Chrome%2F52.0.2743.116+Safari%2F537.36&components%5B1%5D%5Bkey%5D=language&components%5B1%5D%5Bvalue%5D=&components%5B2%5D%5Bkey%5D=color_depth&components%5B2%5D%5Bvalue%5D=24&components%5B3%5D%5Bkey%5D=pixel_ratio&components%5B3%5D%5Bvalue%5D=1&components%5B4%5D%5Bkey%5D=hardware_concurrency&components%5B4%5D%5Bvalue%5D=unknown&components%5B5%5D%5Bkey%5D=resolution&components%5B5%5D%5Bvalue%5D%5B%5D=1920&components%5B5%5D%5Bvalue%5D%5B%5D=1080&components%5B6%5D%5Bkey%5D=available_resolution&components%5B6%5D%5Bvalue%5D%5B%5D=1920&components%5B6%5D%5Bvalue%5D%5B%5D=1040&components%5B7%5D%5Bkey%5D=timezone_offset&components%5B7%5D%5Bvalue%5D=-60&components%5B8%5D%5Bkey%5D=session_storage&components%5B8%5D%5Bvalue%5D=1&components%5B9%5D%5Bkey%5D=local_storage&components%5B9%5D%5Bvalue%5D=1&components%5B10%5D%5Bkey%5D=indexed_db&components%5B10%5D%5Bvalue%5D=1&components%5B11%5D%5Bkey%5D=cpu_class&components%5B11%5D%5Bvalue%5D=unknown&components%5B12%5D%5Bkey%5D=navigator_platform&components%5B12%5D%5Bvalue%5D=unknown&components%5B13%5D%5Bkey%5D=do_not_track&components%5B13%5D%5Bvalue%5D=1&components%5B14%5D%5Bkey%5D=regular_plugins&components%5B14%5D%5Bvalue%5D%5B%5D=&components%5B15%5D%5Bkey%5D=canvas&components%5B15%5D%5Bvalue%5D=&components%5B16%5D%5Bkey%5D=webgl&components%5B16%5D%5Bvalue%5D=&components%5B17%5D%5Bkey%5D=adblock&components%5B17%5D%5Bvalue%5D=false&components%5B18%5D%5Bkey%5D=has_lied_languages&components%5B18%5D%5Bvalue%5D=false&components%5B19%5D%5Bkey%5D=has_lied_resolution&components%5B19%5D%5Bvalue%5D=false&components%5B20%5D%5Bkey%5D=has_lied_os&components%5B20%5D%5Bvalue%5D=false&components%5B21%5D%5Bkey%5D=has_lied_browser&components%5B21%5D%5Bvalue%5D=true&components%5B22%5D%5Bkey%5D=touch_support&components%5B22%5D%5Bvalue%5D%5B%5D=0&components%5B22%5D%5Bvalue%5D%5B%5D=false&components%5B22%5D%5Bvalue%5D%5B%5D=false&components%5B23%5D%5Bkey%5D=js_fonts&components%5B23%5D%5Bvalue%5D%5B%5D=Arial')
        params['header']['Referer'] = str(videoUrl)
        sts, data = self.getPage(self.getFullUrl('/film/index/imprint'), params, 'result=' + self.defaultParams['cookie_items']['mycook'] + '&components%5B0%5D%5Bkey%5D=user_agent&components%5B0%5D%5Bvalue%5D=Mozilla%2F5.0+(Windows+NT+6.1%3B+WOW64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+Chrome%2F52.0.2743.116+Safari%2F537.36&components%5B1%5D%5Bkey%5D=language&components%5B1%5D%5Bvalue%5D=&components%5B2%5D%5Bkey%5D=color_depth&components%5B2%5D%5Bvalue%5D=24&components%5B3%5D%5Bkey%5D=pixel_ratio&components%5B3%5D%5Bvalue%5D=1&components%5B4%5D%5Bkey%5D=hardware_concurrency&components%5B4%5D%5Bvalue%5D=unknown&components%5B5%5D%5Bkey%5D=resolution&components%5B5%5D%5Bvalue%5D%5B%5D=1920&components%5B5%5D%5Bvalue%5D%5B%5D=1080&components%5B6%5D%5Bkey%5D=available_resolution&components%5B6%5D%5Bvalue%5D%5B%5D=1920&components%5B6%5D%5Bvalue%5D%5B%5D=1040&components%5B7%5D%5Bkey%5D=timezone_offset&components%5B7%5D%5Bvalue%5D=-60&components%5B8%5D%5Bkey%5D=session_storage&components%5B8%5D%5Bvalue%5D=1&components%5B9%5D%5Bkey%5D=local_storage&components%5B9%5D%5Bvalue%5D=1&components%5B10%5D%5Bkey%5D=indexed_db&components%5B10%5D%5Bvalue%5D=1&components%5B11%5D%5Bkey%5D=cpu_class&components%5B11%5D%5Bvalue%5D=unknown&components%5B12%5D%5Bkey%5D=navigator_platform&components%5B12%5D%5Bvalue%5D=unknown&components%5B13%5D%5Bkey%5D=do_not_track&components%5B13%5D%5Bvalue%5D=1&components%5B14%5D%5Bkey%5D=regular_plugins&components%5B14%5D%5Bvalue%5D%5B%5D=&components%5B15%5D%5Bkey%5D=canvas&components%5B15%5D%5Bvalue%5D=&components%5B16%5D%5Bkey%5D=webgl&components%5B16%5D%5Bvalue%5D=&components%5B17%5D%5Bkey%5D=adblock&components%5B17%5D%5Bvalue%5D=false&components%5B18%5D%5Bkey%5D=has_lied_languages&components%5B18%5D%5Bvalue%5D=false&components%5B19%5D%5Bkey%5D=has_lied_resolution&components%5B19%5D%5Bvalue%5D=false&components%5B20%5D%5Bkey%5D=has_lied_os&components%5B20%5D%5Bvalue%5D=false&components%5B21%5D%5Bkey%5D=has_lied_browser&components%5B21%5D%5Bvalue%5D=true&components%5B22%5D%5Bkey%5D=touch_support&components%5B22%5D%5Bvalue%5D%5B%5D=0&components%5B22%5D%5Bvalue%5D%5B%5D=false&components%5B22%5D%5Bvalue%5D%5B%5D=false&components%5B23%5D%5Bkey%5D=js_fonts&components%5B23%5D%5Bvalue%5D%5B%5D=Arial')
        if sts:
            self.setMainUrl(self.cm.meta['url'])

        sts, data = self.getPage(videoUrl, self.defaultParams)
        if not sts:
            return []
        data = re.sub("<!--[\s\S]*?-->", "", data)

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('\t', ''))

        if 1 == self.up.checkHostSupport(url):
            return self.up.getVideoLinkExt(url)

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = str(videoUrl)

        sts, data = self.getPage(url, params)
        if not sts:
            return []

        printDBG(data)

        sourceUrl = self.cm.ph.getSearchGroups(data, '''['"]?sourceUrl['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
        filmId = self.cm.ph.getSearchGroups(data, '''['"]?filmId['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
        fileId = self.cm.ph.getSearchGroups(data, '''['"]?fileId['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
        source = self.cm.ph.getSearchGroups(data, '''['"]?source['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]

        #if source == '': source = self.cm.ph.getSearchGroups(url+'|', '''source=([0-9]+?)[^0-9]''', 1, True)[0]
        #if fileId == '': fileId = self.cm.ph.getSearchGroups(url+'|', '''file=([0-9]+?)[^0-9]''', 1, True)[0]

        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = str(url)

        playerKeyParams = {'key': '', 'g': 2, 'p': 293}
        serverData = {'g': -1, 'p': -1, 's_key': ''}
        tmpurl = 'http://player.tree.tv/guard'
        tries = 0
        try:
            while tries < 5:
                if serverData['g'] != playerKeyParams['g'] or serverData['p'] != playerKeyParams['p']:
                    if tries > 0:
                        playerKeyParams['g'] = serverData['g']
                        playerKeyParams['p'] = serverData['p']

                    playerKeyParams['key'] = random.randrange(1, 8)
                    numClient = math.pow(playerKeyParams['g'], playerKeyParams['key'])
                    clientKey = math.fmod(numClient, playerKeyParams['p'])

                    post_data = {'key': int(clientKey)}
                    sts, data = self.getPage(tmpurl, params, post_data)
                    if not sts:
                        return []
                    printDBG("++++++++++++++")
                    printDBG(data)
                    printDBG("++++++++++++++")
                    serverData = json_loads(data)
                else:
                    break

                tries += 1

            if serverData['g'] != playerKeyParams['g'] or serverData['p'] != playerKeyParams['p']:
                printDBG("WRONG DATA")
                printDBG("serverData [%s]" % serverData)
                printDBG("playerKeyParams [%s]" % playerKeyParams)
                return []

            b = math.pow(serverData['s_key'], playerKeyParams['key'])
            skc = int(math.fmod(b, serverData['p']))
        except Exception:
            printExc()
            return []

        post_data = {'file': fileId, 'source': source, 'skc': skc}
        sts, data = self.getPage(sourceUrl, params, post_data)
        if not sts:
            return []

        printDBG('url[%s]' % url)
        printDBG('sourceUrl[%s]' % sourceUrl)
        printDBG('filmId[%s]' % filmId)
        printDBG('fileId[%s]' % fileId)
        printDBG('source[%s]' % source)

        printDBG(data)

        #uri = self.up.getDomain(sourceUrl, False) + 'm3u8/{0}.m3u8'.format(fileId)
        #return getDirectM3U8Playlist(uri, checkContent=True)

        # sometimes return string is not valid json
        try:
            name = self.cm.ph.getSearchGroups(data, '''['"]?name['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
            data = re.compile('''['"]?sources['"]?\s*\:\s*\[([^\]]+?)\]''').findall(data)
            for sources in data:
                sources = sources.split('}')
                for item in sources:
                    uri = self.cm.ph.getSearchGroups(item, '''['"]?src['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
                    if not self.cm.isValidUrl(uri):
                        continue
                    uri = strwithmeta(uri, {'User-Agent': params['header']['User-Agent'], 'Referer': params['header']['Referer'], 'Origin': 'http://player.tree.tv'})
                    point = self.cm.ph.getSearchGroups(item, '''['"]?point['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
                    label = self.cm.ph.getSearchGroups(item, '''['"]?label['"]?\s*:\s*['"]([^'^"]+?)['"]''', 1, True)[0]
                    if label == '':
                        label = name
                    if str(fileId) == str(point) or point == '':
                        if '/playlist/' in uri:
                            urlTab.extend(getDirectM3U8Playlist(uri, checkExt=False, cookieParams=params, checkContent=True))
                        elif source == '3':
                            urlTab.extend([{'name': label, 'url': uri}])
        except Exception:
            printExc()
        return urlTab

    def tryTologin(self, login, password):
        printDBG('tryTologin start')
        connFailed = _('Connection to server failed!')

        rm(self.COOKIE_FILE)
        params = dict(self.defaultParams)
        params['use_new_session'] = True

        sts, data = self.getPage(self.getMainUrl(), params)
        if not sts:
            return False, connFailed
        self.setMainUrl(self.cm.meta['url'])

        loginUrl = self.getFullUrl('users/index/auth')

        post_data = {"mail": login, "pass": password, "social": "0", 'from': 'def'}
        HEADER = dict(self.AJAX_HEADER)
        HEADER['Referer'] = self.cm.getBaseUrl(self.cm.meta['url'])
        HEADER['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        params.update({'header': HEADER})

        # login
        sts, data = self.getPage(loginUrl, params, post_data)
        if not sts:
            return False, connFailed

        # check if logged
        #sts, data = self.getPage(self.MAIN_URL, self.defaultParams)
        #if not sts: return False, connFailed

        if '"ok"' in data:
            return True, 'OK'
        else:
            return False, data

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        if self.login != config.plugins.iptvplayer.treetv_login.value and \
           self.password != config.plugins.iptvplayer.treetv_password.value and \
           '' != config.plugins.iptvplayer.treetv_login.value.strip() and \
           '' != config.plugins.iptvplayer.treetv_password.value.strip():
            loggedIn, msg = self.tryTologin(config.plugins.iptvplayer.treetv_login.value, config.plugins.iptvplayer.treetv_password.value)
            if not loggedIn:
                self.sessionEx.open(MessageBox, _('User login "%s" failed.') % config.plugins.iptvplayer.treetv_login.value, type=MessageBox.TYPE_INFO, timeout=10)
            else:
                self.login = config.plugins.iptvplayer.treetv_login.value
                self.password = config.plugins.iptvplayer.treetv_password.value
        elif config.plugins.iptvplayer.treetv_login.value.strip() == '' or  \
             config.plugins.iptvplayer.treetv_password.value.strip() == '':
            rm(self.COOKIE_FILE)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'list_items' == category:
            idx = self.currItem.get('f_idx', 0)
            if idx == 0:
                self.fillFilters({'name': 'category', 'url': self.getFullUrl('/films')})
            if idx < len(self.filtersTab):
                self.listFilter(self.currItem, self.filtersTab)
            else:
                self.listItems(self.currItem, 'explore_item')
        elif 'list_collections' == category:
            self.listItems(self.currItem, 'list_items2')
        elif 'list_items2' == category:
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
        CHostBase.__init__(self, TreeTv(), True, []) #[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]

    # end converItem
