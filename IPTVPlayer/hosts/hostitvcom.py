# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
###################################################
# FOREIGN import
###################################################
import re
import random
import base64
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.itv_use_x_forwarded_for = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Bypass geo-blocking for VODs (it may be illegal):"), config.plugins.iptvplayer.itv_use_x_forwarded_for))
    return optionList
###################################################


def gettytul():
    return 'https://www.itv.com/'


class ITV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'itv.com', 'cookie': 'itv.com.cookie'})
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/en/thumb/9/92/ITV_logo_2013.svg/800px-ITV_logo_2013.svg.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MOBILE_USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 6_0 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5376e Safari/8536.25'
        self.MAIN_URL = 'https://www.itv.com/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheShows = {}
        self.cacheShowsKeys = []
        self.cacheLive = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'channels', 'title': _('Channels'), 'url': self.getFullUrl('/hub/itv')},
                             {'category': 'shows', 'title': _('Shows'), 'url': self.getFullUrl('/hub/shows')},
                             {'category': 'categories', 'title': _('Categories'), 'url': self.getFullUrl('/hub/categories')},
                            ]
        self.forwardedIP = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, icon):
        icon = CBaseHostClass.getFullIconUrl(self, icon)
        return icon.replace('&amp;', '&')

    def getRandomGBIP(self):
        if not config.plugins.iptvplayer.itv_use_x_forwarded_for.value:
            return ''
        if self.forwardedIP == '':
            sts, data = self.cm.getPage('http://free-proxy-list.net/uk-proxy.html')
            if sts:
                data = re.compile('<tr><td>([^>]+?)</td><td>').findall(data)
                if len(data):
                    self.forwardedIP = random.choice(data)
        return self.forwardedIP

    def listMainMenu(self, cItem, nextCategory):
        printDBG("ITV.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listSubCategory(self, cItem, nextCategory):
        printDBG("ITV.listSubCategory")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'nav-secondary'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if '/hub/' not in url:
                continue
            title = self.cleanHtmlStr(item.split('<span', 1)[0])
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listShowsABC(self, cItem, nextCategory):
        printDBG("ITV.listShowsABC")
        self.cacheShows = {}
        self.cacheShowsKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        params = dict(cItem)
        params.update({'category': nextCategory, 'title': _('--All--')})
        self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'az-list'), ('</section', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<h2', '>', 'az__group-heading'), ('</ul', '>'))
        for item in data:
            letter = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<li', '>', 'grid-list__item'), ('</li', '>'))
            self.cacheShows[letter] = []
            self.cacheShowsKeys.append(letter)
            for it in item:
                it = it.split('</h3>', 1)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(it[0], '''href=['"]([^'^"]+?)['"]''')[0])
                if '/hub/' not in url:
                    continue
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(it[0], '''src=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(it[0])
                desc = self.cleanHtmlStr(it[1])
                self.cacheShows[letter].append({'title': title, 'url': url, 'icon': icon, 'desc': desc})
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': letter, 'f_letter': letter})
            self.addDir(params)

    def listShowsByLetter(self, cItem, nextCategory):
        printDBG("ITV.listShowsByLetter")
        letter = cItem.get('f_letter', '')
        if letter == '':
            letters = self.cacheShowsKeys
        else:
            letters = [letter]
        for letter in letters:
            for item in self.cacheShows[letter]:
                params = dict(cItem)
                params.update(item)
                params['category'] = nextCategory
                self.addDir(params)

    def listItems(self, cItem, nextCategory, addLive=False):
        printDBG("ITV.listItems [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'info__content grid__item'), ('</ul', '>'))[1]
        if 'data-video-id' in data and tmp != '':
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<header', '</header>')[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<p', '</p>')[1])
            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    descTab.append(t)
            desc = ' | '.join(descTab) + '[/br]' + desc

            params = dict(cItem)
            params.update({'title': title, 'desc': desc})
            self.addVideo(params)
        elif addLive:
            params = dict(cItem)
            params.update({'is_live': True})
            self.addVideo(params)

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<section', '>', 'episode-list'), ('</section', '>'))
        tmp.extend(self.cm.ph.getAllItemsBeetwenNodes(data, ('<section', '>', 'class="block'), ('</section', '>')))
        tmp.extend(self.cm.ph.getAllItemsBeetwenNodes(data, ('<aside', '>'), ('</aside', '>')))
        data = tmp
        for section in data:
            sTtile = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
            section = self.cm.ph.getAllItemsBeetwenNodes(section, ('<li', '>', 'grid-list__item'), ('</li', '>'))
            if 'Series' in sTtile or 'pisodes' in sTtile:
                title = '%s - %s' % (cItem['title'], sTtile)
            else:
                title = sTtile
            if title != '':
                self.addMarker({'title': title})

            for item in section:
                item = item.split('</h3>', 1)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item[0], '''href=['"]([^'^"]+?)['"]''')[0])
                if '/hub/' not in url:
                    continue
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item[0], '''src=['"]([^'^"]+?)['"]''')[0])
                if 'Series' in sTtile:
                    title = '%s - %s %s' % (cItem['title'], sTtile, self.cleanHtmlStr(item[0]))
                elif 'pisodes' in sTtile:
                    title = '%s - %s' % (cItem['title'], self.cleanHtmlStr(item[0]))
                else:
                    title = self.cleanHtmlStr(item[0])
                desc = self.cleanHtmlStr(item[-1])

                params = dict(cItem)
                params.update({'title': title, 'url': url, 'icon': icon, 'desc': desc})
                tmp = url.split('/')
                if 'Series' in sTtile or 'pisodes' in sTtile:
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("ITV.getLinksForVideo [%s]" % cItem)

        retTab = []
        forwardedIP = self.getRandomGBIP()
        if cItem.get('is_live', False):
            if self.cacheLive == {}:
                sts, data = self.getPage('http://textuploader.com/dlr3q')
                if not sts:
                    return []
                data = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<code', '>'), ('</code', '>'), False)[1])
                try:
                    data = base64.b64decode(data)
                    printDBG(data)
                    self.cacheLive = byteify(json.loads(data), '', True)
                except Exception:
                    printExc()
            videoUrl = self.cacheLive.get(cItem['url'].split('/')[-1], '')
            if forwardedIP != '':
                videoUrl = strwithmeta(videoUrl, {'X-Forwarded-For': forwardedIP})
            retTab = getDirectM3U8Playlist(videoUrl, checkContent=True)
        else:
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['User-Agent'] = self.MOBILE_USER_AGENT
            if forwardedIP != '':
                params['header']['X-Forwarded-For'] = forwardedIP

            sts, data = self.getPage(cItem['url'], params)
            if not sts:
                return []

            url = self.cm.ph.getSearchGroups(data, '''data\-video\-id=['"]([^'^"]+?)['"]''')[0]
            hmac = self.cm.ph.getSearchGroups(data, '''data\-video\-hmac=['"]([^'^"]+?)['"]''')[0]

            params['header'].update({'Content-Type': 'application/json', 'Accept': 'application/vnd.itv.vod.playlist.v2+json', 'Origin': self.getMainUrl(), 'Referer': cItem['url'], 'hmac': hmac})
            params['raw_post_data'] = True
            post_data = {"user": {"itvUserId": "", "entitlements": [], "token": ""}, "device": {"manufacturer": "Apple", "model": "iPhone", "os": {"name": "iPad OS", "version": "9.3", "type": "ios"}}, "client": {"version": "4.1", "id": "browser"}, "variantAvailability": {"featureset": {"min": ["hls", "aes"], "max": ["hls", "aes"]}, "platformTag": "mobile"}}
            try:
                sts, data = self.getPage(url, params, json.dumps(post_data))
                if not sts:
                    return []
                data = byteify(json.loads(data), '', True)['Playlist']['Video']
                videoUrl = data['Base'] + data['MediaFiles'][-1]['Href']
                retTab = getDirectM3U8Playlist(videoUrl, checkContent=True)
            except Exception:
                printExc()

        def __getLinkQuality(itemLink):
            try:
                return int(itemLink['bitrate'])
            except Exception:
                return 0

        retTab = CSelOneLink(retTab, __getLinkQuality, 99999999).getSortedLinks()
        return retTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('GB')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'channels':
            self.listSubCategory(self.currItem, 'explore_channel')
        elif category == 'categories':
            self.listSubCategory(self.currItem, 'list_items')
        elif category == 'shows':
            self.listShowsABC(self.currItem, 'list_shows_by_letter')
        elif category == 'list_shows_by_letter':
            self.listShowsByLetter(self.currItem, 'list_items')
        elif category == 'explore_channel':
            self.listItems(self.currItem, 'list_items', True)
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_items')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ITV(), True, [])
