# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
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
config.plugins.iptvplayer.losmovies_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                         ("proxy_1", _("Alternative proxy server (1)")),
                                                                                         ("proxy_2", _("Alternative proxy server (2)"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.losmovies_proxy))
    return optionList
###################################################


def gettytul():
    return 'http://losmovies.cx/'


class LosMovies(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'LosMovies.tv', 'cookie': 'LosMovies.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/xplugin.video.losmovies.png.pagespeed.ic.JtaWsQ6YWz.jpg'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'http://losmovies.cx/'
        self.cacheEpisodes = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_cats', 'mode': 'movie', 'title': 'Movies', 'url': self.getMainUrl()},
                             {'category': 'list_cats', 'mode': 'serie', 'title': 'TV Shows', 'url': self.getFullUrl('watch-popular-tv-shows')},
                             {'category': 'list_top_cats', 'mode': 'movie', 'title': 'Top Movie Lists', 'url': self.getFullUrl('top-movie-lists')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        self.MAIN_SUB_CATS_TAB = [{'category': 'list_abc', 'title': 'Alphabetically', },
                                  {'category': 'list_categories', 'title': 'Genres', 'url': self.getFullUrl('movie-genres')},
                                  {'category': 'list_categories', 'title': 'Countries', 'url': self.getFullUrl('countries')},
                                 ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.losmovies_proxy.value
        printDBG(">> " + proxy)
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HEADER['User-Agent']}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listCats(self, cItem, nextCategory):
        printDBG("LosMovies.listCats")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="btn-group">', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = {'category': nextCategory, 'title': title, 'url': url}
            self.addDir(params)

        params = dict(cItem)
        self.listsTab(self.MAIN_SUB_CATS_TAB, params)

    def listABC(self, cItem, nextCategory):
        printDBG("LosMovies.listABC")
        for letter in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': letter, 'letter': letter})
            self.addDir(params)

    def listCategories(self, cItem, nextCategory):
        printDBG("LosMovies.listCategories")

        if cItem['mode'] == 'movie':
            marker = 'movies'
        else:
            marker = 'shows'

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<h1 class="centerHeader">', '<footer>')[1]
        data = data.split('showEntityTeaser ')
        if len(data):
            del data[0]
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?{0})['"]'''.format(marker))[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<div[^>]+?showRowName'), re.compile('</div>'))[1])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url, 'icon': icon})
            self.addDir(params)

    def listItems(self, cItem, nextCategory=None):
        printDBG("LosMovies.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)
        letter = cItem.get('letter', '')

        getParams = []
        if page > 1:
            getParams.append("page=%d" % page)
        if letter != '':
            getParams.append("letter=%s" % letter)
        getParams = '&'.join(getParams)
        if '?' in url:
            url += '&' + getParams
        else:
            url += '?' + getParams

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'pagination', '</div>', False)[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'page=(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        if cItem['category'] in ['list_items', 'search', 'search_next_page']:
            marker = 'movie'
        else:
            marker = 'rubric'

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="' + marker, '</h4>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            desc = self.cleanHtmlStr(item)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])

            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'info_url': url, 'icon': icon}
            if 'class="movieTV"' not in item and '/movie-list/' not in item:
                self.addVideo(params)
            else:
                params['category'] = nextCategory
                params2 = dict(cItem)
                params2.update(params)
                self.addDir(params2)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listSeasons(self, cItem, nextCategory='list_episodes'):
        printDBG("LosMovies.listSeasons")

        self.cacheEpisodes = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        seasonsTitlesTab = {}
        seasonsData = self.cm.ph.getDataBeetwenMarkers(data, '<div id="seasons">', '</ul>')[1]
        seasonsData = self.cm.ph.getAllItemsBeetwenMarkers(seasonsData, '<a ', '</a>', withMarkers=True)
        for item in seasonsData:
            seasonTitle = self.cleanHtmlStr(item)
            seasonKey = self.cm.ph.getSearchGroups(item, '''href=['"]#tabs\-([^'^"]+?)['"]''')[0]
            seasonsTitlesTab[seasonKey] = seasonTitle

        marker = '<div id="tabs-'
        data = self.cm.ph.getDataBeetwenMarkers(data, marker, '<div class="adsPlaceHolder', False)[1]
        data = data.split(marker)
        for sItem in data:
            seasonKey = self.cm.ph.getSearchGroups(sItem, '''([0-9]+?)['"]''')[0]
            episodesTab = []
            episodesData = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<h3', '</tbody>', True)
            for eItem in episodesData:
                eTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(eItem, '<h3', '</h3>', True)[1])
                eFakeUrl = '#season%s_%s' % (seasonKey, urllib_quote(eTitle))
                linksTab = self.getLinksForVideo(cItem, eItem)
                if len(linksTab):
                    self.cacheLinks[eFakeUrl] = linksTab
                    episodesTab.append({'title': eTitle, 'url': eFakeUrl})
            if len(episodesTab):
                self.cacheEpisodes[seasonKey] = episodesTab
                sTitle = seasonsTitlesTab.get(seasonKey, 'Season ' + seasonKey)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 's_key': seasonKey})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("LosMovies.listEpisodes")

        sKey = cItem.get('s_key', '')
        tab = self.cacheEpisodes.get(sKey, [])

        params = dict(cItem)
        self.listsTab(tab, params, 'video')

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("LosMovies.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('search?type=movies&q=') + urllib_quote_plus(searchPattern)
        self.listItems(cItem, 'list_seasons')

    def getLinksForVideo(self, cItem, eItem=None):
        printDBG("LosMovies.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if eItem == None:
            urlTab = self.cacheLinks.get(cItem['url'], [])
            if len(urlTab):
                return urlTab

            url = cItem['url']
            sts, data = self.getPage(url, self.defaultParams)
            if not sts:
                return urlTab
        else:
            data = eItem

        linksData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr class="linkTr"', '</tr>', True)
        for item in linksData:
            url = self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<td[^>]+?linkHiddenUrl[^>]+?>'), re.compile('</td>'), False)[1].strip()
            if not self.cm.isValidUrl(url):
                continue
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>', True)
            nameTab = []
            nIdx = 0
            for nItem in tmp:
                nIdx += 1
                if nIdx in [3, 4]:
                    continue
                if nIdx > 6:
                    break
                nItem = self.cleanHtmlStr(nItem)
                if nItem == 'None':
                    continue
                nameTab.append(nItem)
            name = ' | '.join(nameTab)
            urlTab.append({'name': name, 'url': url, 'need_resolve': 1})

        if eItem == None:
            self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def unSecure(self, data):
        data = self.cm.ph.getSearchGroups(data, r'''=['"]([A-Za-z0-9+=\/]{40,})['"]''')[0]
        try:
            data = base64.b64decode(data).replace('\n', '').replace('location.reload();', '').replace('; ', '').replace(';document.cookie', '\ncookie ')
            data = data.replace('String.fromCharCode', 'chr')
            data = re.sub('\.charAt\((\s*[0-9]+?\s*)\)', lambda x: '[%s]' % x.group(1), data)
            data = re.sub('\.substr\(\s*([0-9]+?)\s*,\s*([0-9]+?)\s*\)', lambda x: '[%s:%s]' % (x.group(1), x.group(2)), data)
            data = re.sub('\.substr\(\s*([0-9]+?)\s*,\s*([0-9]+?)\s*\)', lambda x: '[%s:%s]' % (x.group(1), x.group(2)), data)
            data = re.sub('\.slice\(\s*([0-9]+?)\s*,\s*([0-9]+?)\s*\)', lambda x: '[%s:%s]' % (x.group(1), x.group(2)), data)
            data = data.replace('\n', '\n\t')
            data = 'def retA():\n\t' + data
            data += '\n\treturn cookie\n'
            data += 'iptv_param = retA()'
            printDBG('++++++++++++++++++++')
            printDBG(data)
            printDBG('++++++++++++++++++++')
            vGlobals = {"__builtins__": None, '__name__': __name__, 'str': str, 'chr': chr}
            vLocals = {'param': None}
            exec(data, vGlobals, vLocals)
            tmp = vLocals['iptv_param'].split(';')[0].split('=')
            return {tmp[0]: tmp[1]}
        except Exception:
            printExc()
        return None

    def getVideoLinks(self, videoUrl):
        printDBG("LosMovies.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        if not self.cm.isValidUrl(videoUrl):
            return []

        tab = self.up.getVideoLinkExt(videoUrl)
        if len(tab):
            return tab

        sts, data = self.getPage(videoUrl, self.defaultParams)
        if not sts:
            return []

        printDBG(data)

        if 'onlinemovietv' in self.up.getDomain(videoUrl) and 'You are being redirected' in data:
            cookie = self.unSecure(data)
            if cookie != None:
                params = dict(self.defaultParams)
                params['cookie_items'] = cookie
                sts, data = self.getPage(videoUrl, params)
                if not sts:
                    return []

        #printDBG(data)

        subTracks = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'sources', ']')[1]
        if tmp != '':
            tmp = tmp.split('}')
            urlAttrName = 'file'
            sp = ':'
        else:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>', withMarkers=True)
            urlAttrName = 'src'
            sp = '='

        for item in tmp:
            url = self.cm.ph.getSearchGroups(item.replace('\\/', '/'), r'''['"]?{0}['"]?\s*{1}\s*['"](https?://[^"^']+)['"]'''.format(urlAttrName, sp))[0]
            if not self.cm.isValidUrl(url):
                continue
            name = self.cm.ph.getSearchGroups(item, r'''['"]?label['"]?\s*{0}\s*['"]?([^"^'^,]+)[,'"]'''.format(sp))[0]

            printDBG('---------------------------')
            printDBG('url:  ' + url)
            printDBG('name: ' + name)
            printDBG('+++++++++++++++++++++++++++')
            printDBG(item)

            if 'mp4' in item:
                url = strwithmeta(self.cm.getFullUrl(url, self.cm.meta['url']), {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.cm.meta['url']})
                urlTab.append({'name': name, 'url': url})
            elif 'captions' in item:
                format = url[-3:]
                if format in ['srt', 'vtt']:
                    url = strwithmeta(self.cm.getFullUrl(url, self.cm.meta['url']), {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.cm.meta['url']})
                    subTracks.append({'title': name, 'url': url, 'lang': name, 'format': format})

        printDBG(subTracks)
        if len(subTracks):
            for idx in range(len(urlTab)):
                urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], {'external_sub_tracks': subTracks})

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("LosMovies.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem.get('url', ''))
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:title"[^>]+?content="([^"]+?)"')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('showRowDescription[^>]+?>'), re.compile('</div>'), False)[1])

        icon = self.cm.ph.getDataBeetwenMarkers(data, 'showRowImage">', '</div>')[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(icon, 'src="([^"]+?)"')[0])

        self.getFullUrl(self.cm.ph.getSearchGroups(data, '<meta property="og:image"[^>]+?content="([^"]+?)"')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            title = cItem['desc']
        if icon == '':
            title = cItem['icon']

        descKeys = [('ImdbRating', 'rated'),
                    ('Actors', 'actors'),
                    ('Directors', 'director'),
                    ('Countries', 'country'),
                    ('Release', 'released'),
                    ('Categories', 'genre'),
                    ('Duration', 'duration'),
                    ('Budget', 'budget')]

        otherInfo = {}
        for item in descKeys:
            val = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'showValue%s">' % item[0], '</div>', False)[1])
            if val != '' and item[1] != '':
                try:
                    otherInfo[item[1]] = val.replace(' , ', ', ')
                except Exception:
                    continue

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        printDBG('LosMovies.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'desc': cItem['desc'], 'icon': cItem['icon']}
        return json.dumps(params)

    def getLinksForFavourite(self, fav_data):
        printDBG('LosMovies.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('LosMovies.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

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
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_cats':
            self.listCats(self.currItem, 'list_items')
        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_items')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_top_cats':
            self.listItems(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, LosMovies(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'list_seasons':
            return False
        return True
