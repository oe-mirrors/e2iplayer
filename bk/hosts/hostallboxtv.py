# -*- coding: utf-8 -*-

#
#
# @Codermik release, based on @Samsamsam's E2iPlayer public.
# Released with kind permission of Samsamsam.
# All code developed by Samsamsam is the property of the Samsamsam and the E2iPlayer project,  
# all other work is ? E2iStream Team, aka Codermik.  TSiPlayer is ? Rgysoft, his group can be
# found here:  https://www.facebook.com/E2TSIPlayer/
#
# https://www.facebook.com/e2iStream/
#
#

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads

import urlparse, urllib, base64, re
from Components.config import config, ConfigText, getConfigListEntry
from Screens.MessageBox import MessageBox
config.plugins.iptvplayer.allboxtv_login = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.allboxtv_password = ConfigText(default='', fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('e-mail') + ':', config.plugins.iptvplayer.allboxtv_login))
    optionList.append(getConfigListEntry(_('password') + ':', config.plugins.iptvplayer.allboxtv_password))
    return optionList


def gettytul():
    return 'https://allbox.tv/'


class AllBoxTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'allbox.tv', 'cookie': 'allbox.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://allbox.tv/'
        self.DEFAULT_ICON_URL = 'https://allbox.tv/static/img/seriale_brak_foto.jpg?v=1'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
        self.cacheSearch = {}
        self.cacheEpisodes = {}
        self.cacheSeriesLetter = []
        self.cacheSetiesByLetter = {}
        self.cacheCartoonsLetter = []
        self.cacheCartoonsByLetter = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Movies'), 'url': self.getFullUrl('/filmy-online,wszystkie')}, {'category': 'list_items', 'title': _('Premieres'), 'url': self.getFullUrl('/premiery')}, {'category': 'list_series_az', 'title': _('TV series'), 'url': self.getFullUrl('/seriale-online')}, {'category': 'list_cartoons_az', 'title': _('Cartoons'), 'url': self.getFullUrl('/bajki-online')}, {'category': 'list_filters', 'title': _('Ranking'), 'url': self.getFullUrl('/filmy-online,wszystkie,top')}, {'category': 'search', 'title': _('Search'), 'search_item': True}, {'category': 'search_history', 'title': _('Search history')}]
        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.loginMessage = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def base64Decode(self, data):
        missing_padding = len(data) % 4
        if missing_padding != 0:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data)

    def getFullUrl(self, url):
        return CBaseHostClass.getFullUrl(self, url.split('#', 1)[0])

    def listMainMenu(self, cItem, nextCategory):
        printDBG('AllBoxTV.listMainMenu')
        cItem = dict(cItem)
        cItem['desc'] = self.loginMessage
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listLetters(self, cItem, nextCategory, cacheLetter, cacheByLetter):
        printDBG('AllBoxTV.listLetters')
        if 0 == len(cacheLetter):
            del cacheLetter[:]
            cacheByLetter.clear()
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'movie cat'), ('</a','>'))
            for item in data:
                letter = self.cm.ph.getSearchGroups(item, 'cat\\-([^\'^"]+?)[\'"]')[0]
                if letter == '':
                    continue
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0])
                if url == '':
                    continue
                title = ph.clean_html(item)
                if letter not in cacheLetter:
                    cacheLetter.append(letter)
                    cacheByLetter[letter] = []
                cacheByLetter[letter].append({'title': title, 'url': url, 'desc': '', 'icon': url + '?fake=need_resolve.jpeg'})

        for letter in cacheLetter:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': letter, 'desc': '', 'f_letter': letter})
            self.addDir(params)

    def listByLetter(self, cItem, nextCategory, cacheByLetter):
        printDBG('AllBoxTV.listByLetter')
        letter = cItem['f_letter']
        tab = cacheByLetter[letter]
        cItem = dict(cItem)
        cItem.update({'good_for_fav': True, 'category': nextCategory, 'desc': ''})
        self.listsTab(tab, cItem)

    def listSort(self, cItem, nextCategory):
        printDBG('AllBoxTV.listSort')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.getFullUrl(self.cm.meta['url'])
        data = ph.find(data, ('<li', '>', 'presentation'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            url = self.getFullUrl(ph.getattr(data[(idx - 1)], 'href'))
            title = ph.clean_html(data[idx])
            self.addDir(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'url': url}))

    def listSortMode(self, cItem, nextCategory):
        printDBG('AllBoxTV.listSortMode')
        sts, pageData = self.getPage(cItem['url'])
        if not sts:
            return
        self.getFullUrl(self.cm.meta['url'])
        data = ph.find(pageData, ('<button', '>', 'btnFilters'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            url = self.getFullUrl(ph.getattr(data[(idx - 1)], 'href'))
            title = ph.clean_html(data[idx])
            self.addDir(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'url': url}))

        if not self.currList:
            self.listFilters(MergeDicts(cItem, {'category': nextCategory}), 'list_items', 'explore_item', pageData)

    def listFilters(self, cItem, nextCategory, nextNextCategory, data=None):
        printDBG('AllBoxTV.listFilters')
        cItem = dict(cItem)
        f_idx = cItem.get('f_idx', 0)
        if not data:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
        data = ph.findall(data, ('<ul', '>', ph.check(ph.any, ('moviesVersions', 'moviesCategories', 'moviesYears', 'moviesCountries'))), '</ul>', flags=ph.START_S)
        
        if data and 'moviesYears' in data[(-2)] and 'moviesYearsRating' not in data[(-2)]:
            del data[-2:]
            
        if len(data) / 2 > f_idx:
            tmp = ph.findall(data[(f_idx * 2 + 1)], ('<a', '>'), '</a>', flags=ph.START_S)
            f_idx += 1
            for idx in range(1, len(tmp), 2):
                url = self.getFullUrl(ph.search(tmp[(idx - 1)], ph.A)[1])
                if not url:
                    continue
                title = ph.clean_html(tmp[idx])
                if 'wszystkie' in title.lower():
                    url = cItem['url']
                if 'ranking-filmow-online-allbox' in url:
                    category = 'rank_table' if 1 else cItem['category']
                    self.addDir(MergeDicts(cItem, {'category': category, 'title': title, 'url': url, 'f_idx': f_idx, 'desc': ''}))
        else:
            self.listItems(MergeDicts(cItem, {'category': nextCategory}), nextNextCategory)

    def _listItems(self, data):
        retTab = []
        data = ph.rfindall(data, '</div>', ('<div', '>', 'box_movie'))
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            if not url:
                continue
            title = ph.clean_html(ph.rfind(item, '</div>', '</div>', flags=0)[1])
            if not title:
                title = ph.clean_html(ph.rfind(item, '</a>', ('<div', '>'), flags=0)[1])
            if not title:
                title = ph.clean_html(ph.getattr(item, 'alt'))
            icon = self.getFullIconUrl(ph.getattr(item, 'data-src'))
            if icon == '':
                icon = self.getFullIconUrl(ph.search(item, '\\surl\\(([^\\)]+?)\\)')[0].strip())
            desc = []
            tmp = ph.find(item, ('<div', '>', 'cats'), '</div>', flags=0)[1]
            tmp = ph.findall(tmp, ('<a', '>'), '</a>')
            for t in tmp:
                t = ph.clean_html(t)
                if t != '':
                    desc.append(t)
            if desc:
                desc = [(', ').join(desc)]
            tmp = ph.findall(item, ('<', '>', 'badge-small'), ('</', '>', 'a'))
            for t in tmp:
                t = ph.clean_html(t)
                if t != '':
                    desc.append(t)

            desc = (' | ').join(desc)
            desc += '[/br]' + ph.clean_html(ph.find(item, ('<p', '>'), '</p>')[1])
            retTab.append({'title': title, 'url': url, 'icon': icon, 'desc': desc})
        return retTab

    def listItems(self, cItem, nextCategory):
        printDBG('AllBoxTV.listItems [%s]' % cItem)
        page = cItem.get('page', 0)
        moviesCount = cItem.get('movies_count', 0)
        url = '%s?load=1&moviesCount=%s' % (cItem['url'], moviesCount)
        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        sts, data = self.getPage(url, params, post_data={'page': page})
        if not sts:
            return
        nextPage = False
        try:
            data = json_loads(data, '')
            if not data.get('lastPage', True):
                try:
                    moviesCount = int(data['moviesCount'])
                    nextPage = True
                except Exception:
                    printExc()
            itemsTab = self._listItems(data['html'])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory})
            self.listsTab(itemsTab, params)
            if nextPage:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'movies_count': moviesCount})
                self.addDir(params)
        except Exception:
            printExc()

    def listRankRableItems(self, cItem, nextCategory):
        printDBG('AllBoxTV.listRankRableItems [%s]' % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        data = ph.find(data, ('<div', '>', 'clear:both'), ('<div', '>', 'clear:both'), flags=0)[1]
        data = ph.rfindall(data, '</div>', ('<div', '>', 'col-md'), flags=0)
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            if not url:
                continue
            title = ph.clean_html(ph.find(item, ('<a', '>'), '</a>', flags=0)[1])
            icon = self.getFullIconUrl(ph.search(item, ph.IMG)[1])
            desc = [ph.clean_html(ph.find(item, ('<span', '>', 'ranking-position'), '</span>', flags=0)[1])]
            tt = ph.find(item, ('<div', '>', 'mboxes'), '</div>', flags=0)[1]
            tt = ph.rfindall(tt, '</span>', ('<span', '>', 'data-original-title'), flags=ph.END_S)
            for i in range(1, len(tt), 2):
                desc.append('%s: %s' % (ph.clean_html(ph.getattr(tt[(i - 1)], 'data-original-title')), ph.clean_html(tt[i])))
            desc.append(ph.clean_html(ph.find(item, ('<p', '>'), '</p>', flags=0)[1]))
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': ('[/br]').join(desc)}))

    def listItems2(self, cItem, nextCategory):
        printDBG('AllBoxTV.listItems2 [%s]' % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = ph.findall(data, ('<div', '>', 'box_fable'), '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '\\shref=[\'"]([^\'^"]+?)[\'"]')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'url\\(([^"^\\)]+?\\.(:?jpe?g|png)(:?\\?[^"^\\)]+?)?)\\);')[0].strip())
            title = ph.clean_html(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon})
            if nextCategory == 'video':
                self.addVideo(params)
            else:
                params['category'] = nextCategory
                self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG('AllBoxTV.exploreItem')
        self.cacheEpisodes = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<img', '>', '"image"'), ('<','>'))[1]
        icon = self.cm.ph.getSearchGroups(icon, '<img[^>]+?src="([^"]+?\\.(:?jpe?g|png)(:?\\?[^"]+?)?)"')[0]
        seriesTitle = ph.clean_html(self.cm.ph.getDataBeetwenNodes(data, ('<', '>','movie-name'), ('<','>'))[1])
        if seriesTitle == '':
            seriesTitle = cItem['title']
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'modal-trailer'), ('<div','>','row'))
        printDBG(tmp)
        num = 1
        for item in tmp:
            direct = False
            url = self.getFullUrl(ph.search(item, ph.IFRAME)[1])
            if not url:
                url = ph.find(item, '<iframe', '>', flags=0)[1]
                url = self.getFullUrl(ph.getattr(url, 'data-source'))
            if not url:
                type = ph.search(item, '[\'"]?type[\'"]?\\s*:\\s*[\'"]([^"^\']+?)[\'"]', flags=ph.I)[0]
                url = self.getFullUrl(ph.search(item, '[\'"]?file[\'"]?\\s*:\\s*[\'"]([^"^\']+?)[\'"]', flags=ph.I)[0])
                if 'mp4' not in type.lower() and not url.split('?', 1)[0].lower().endswith('mp4'):
                    continue
                direct = True
            if not self.cm.isValidUrl(url):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': url, 'direct_link': direct, 'title': '%s - %s %s' % (seriesTitle, _('trailer'), num), 'icon': icon})
            self.addVideo(params)
            num += 1
        seasonsTab = []
        data = ph.findall(data, ('<div', '</div>', 'seasonHead'), '</div>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            sTitle = ph.clean_html(data[(idx - 1)].split('<span', 1)[0])
            sItem = ph.findall(data[idx], '<a', '</a>')
            for item in sItem:
                url = self.getFullUrl(ph.search(item, ph.A)[1])
                title = ph.clean_html(item)
                tmp = ph.search(title, 'S([0-9]+?)E([0-9]+?)[^0-9]', flags=ph.I)
                title = '%s - %s' % (seriesTitle, title)
                if tmp[0] not in self.cacheEpisodes:
                    self.cacheEpisodes[tmp[0]] = []
                    seasonsTab.append({'good_for_fav': False, 'category': nextCategory, 's_num': tmp[0], 'title': _('Season %s') % tmp[0]})
                self.cacheEpisodes[tmp[0]].append({'good_for_fav': False, 'url': url, 'title': title, 'icon': url + '?fake=need_resolve.jpeg'})

        if len(seasonsTab) == 1:
            params = dict(cItem)
            params.update(seasonsTab[0])
            self.listEpisodes(params)
        elif len(seasonsTab) > 0:
            self.listsTab(seasonsTab, cItem)
        elif '/film' in cItem['url']:
            params = dict(cItem)
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG('AllBoxTV.listEpisodes')
        episodesTable = self.cacheEpisodes[cItem['s_num']]
        params = dict(cItem)
        params.update({'good_for_fav': False})
        self.listsTab(episodesTable, params, 'video')

    def _getM3uIcon(self, item, cItem):
        icon = item.get('tvg-logo', '')
        if not self.cm.isValidUrl(icon):
            icon = item.get('logo', '')
        if not self.cm.isValidUrl(icon):
            icon = item.get('art', '')
        if not self.cm.isValidUrl(icon):
            icon = cItem.get('icon', '')
        return icon

    def _getM3uPlayableUrl(self, baseUrl, url, item):
        need_resolve = 1
        if url.startswith('/'):
            if baseUrl == '':
                url = 'file://' + url
                need_resolve = 0
            elif url.startswith('//'):
                url = 'http:' + url
            else:
                url = self.cm.getBaseUrl(baseUrl) + url[1:]
        if '' != item.get('program-id', ''):
            url = strwithmeta(url, {'PROGRAM-ID': item['program-id']})
        return (need_resolve, url)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('AllBoxTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]' % (cItem, searchPattern, searchType))
        self.cacheSearch = {}
        url = self.getFullUrl('/szukaj?query=') + urllib.quote_plus(searchPattern)
        sts, data = self.getPage(url)
        if not sts:
            return
        nameMap = {'movies': _('Movies'), 'serials': _('TV series')}
        data = ph.find(data, ('<div', '>', 'tab-content'), ('<div', '>', 'sidebarTitle'))[1]
        data = re.compile('<div([^>]+?tabpanel[^>]+?)>').split(data)
        for idx in range(2, len(data), 2):
            name = ph.getattr(data[(idx - 1)], 'id')
            if name not in ('movies', 'serials'):
                printDBG('SKIP search group %s' % name)
                continue
            itemsTab = self._listItems(data[idx])
            if not itemsTab:
                continue
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': 'list_search_items', 'f_search_type': name, 'desc': '', 'title': '%s (%s)' % (nameMap[name], len(itemsTab))})
            self.addDir(params)
            self.cacheSearch[name] = itemsTab

    def listSearchItems(self, cItem, nextCategory):
        printDBG('AllBoxTV.listSearchItems')
        itemsTab = self.cacheSearch[cItem['f_search_type']]
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(itemsTab, params)

    def getLinksForVideo(self, cItem):
        printDBG('AllBoxTV.getLinksForVideo [%s]' % cItem)
        self.tryTologin()
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)
        if cItem.get('direct_link') == True:
            return [{'name': 'trailer', 'url': cItem['url'], 'need_resolve': 0}]
        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab
        self.cacheLinks = {}
        retTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'id="sources"'), ('</table','>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href=[\'"]([^"^\']+?)[\'"]')[0].replace('&amp;', '&'))
            if not self.cm.isValidUrl(url):
                continue
            name = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')[0:-1]
            for t in tmp:
                t = ph.clean_html(t.split('<b>', 1)[(-1)])
                if t != '':
                    name.append(t)
            name = (' | ').join(name)
            retTab.append({'name': name, 'url': self.getFullUrl(url), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        else:
            retTab.append({'name': 'one', 'url': cItem['url'], 'need_resolve': 1})
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG('AllBoxTV.getVideoLinks [%s]' % baseUrl)
        videoUrl = strwithmeta(baseUrl)
        urlTab = []
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        if 1 != self.up.checkHostSupport(videoUrl):
            sts, data = self.getPage(videoUrl)
            if not sts:
                return []
            SetIPTVPlayerLastHostError(ph.clean_html(ph.find(data, ('<div', '>', 'infoMsg'), '</div>', flags=0)[1]))
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<iframe', '>', 'video-player'), ('</iframe','>'))[1]
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '<iframe[^>]+?src=[\'"]([^"^\']+?)[\'"]', 1, True)[0])
            if '' == videoUrl:
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '<iframe[^>]+?data\\-source=[\'"]([^"^\']+?)[\'"]', 1, True)[0])
            if '' == videoUrl:
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '[\'"](https?://[^"^\']+?)[\'"]', 1, True)[0])
            videoUrl = videoUrl.replace('&amp;', '&')
            if videoUrl == '':
                dataKey = self.cm.ph.getSearchGroups(data, 'data\\-key=[\'"]([^\'^"]+?)[\'"]')[0]
                if dataKey != '':
                    try:
                        dataKey = json_loads(self.base64Decode(dataKey[2:]))
                        printDBG('++++++++++++++++++++++++++> %s' % dataKey)
                        params = dict(self.defaultParams)
                        params['header'] = dict(params['header'])
                        params['header']['Referer'] = baseUrl
                        params['max_data_size'] = 0
                        self.getPage(self.getFullUrl(dataKey['url']), params)
                        url = self.cm.meta['url']
                        printDBG('++++++++++++++++++++++++++> ' + url)
                        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
                        return [{'name': '', 'url': strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT}), 'need_resolve': 0}]
                    except Exception:
                        printExc()

                tmp = self.cm.ph.getDataBeetwenMarkers(data, 'setup(', '});')[1]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '[\'"]?file[\'"]?\\s*:\\s*[\'"]([^\'^"]+?)[\'"]')[0])
                if 'mp4' in tmp and self.cm.isValidUrl(url):
                    cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
                    return [{'name': '', 'url': strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT}), 'Referer': baseUrl, 'need_resolve': 0}]
        if 1 == self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    def tryTologin(self):
        printDBG('tryTologin start')
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.allboxtv_login.value or self.password != config.plugins.iptvplayer.allboxtv_password.value:
            self.login = config.plugins.iptvplayer.allboxtv_login.value
            self.password = config.plugins.iptvplayer.allboxtv_password.value
            rm(self.COOKIE_FILE)
            self.loggedIn = False
            self.loginMessage = ''
            if '' == self.login.strip() or '' == self.password.strip():
                msg = _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl())
                GetIPTVNotify().push(msg, 'info', 10)
                return False
            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return False
            url = self.getFullUrl('/logowanie')
            sts, data = self.getPage(url)
            if not sts:
                return False
            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'loginForm'), ('</form','>'))
            if not sts:
                return False
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'action=[\'"]([^\'^"]+?)[\'"]')[0])
            if actionUrl == '':
                actionUrl = url
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            post_data = {}
            for item in data:
                name = self.cm.ph.getSearchGroups(item, 'name=[\'"]([^\'^"]+?)[\'"]')[0]
                value = self.cm.ph.getSearchGroups(item, 'value=[\'"]([^\'^"]+?)[\'"]')[0]
                post_data[name] = value

            post_data.update({'email': self.login, 'password': self.password, 'form_login_rememberme': 'on'})
            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = url
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and '/wyloguj' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
                data = self.cm.ph.getDataBeetwenNodes(data, ('<', '>', 'mobile-header'), ('</ul','>'))[1]
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
                self.loginMessage = []
                for item in data:
                    item = ph.clean_html(item)
                    if item == '':
                        continue
                    self.loginMessage.append(item)
                self.loginMessage = ('[/br]').join(self.loginMessage)
            else:
                if sts:
                    errMsg = []
                    tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>', 'required'), ('</span','>'), False)
                    for it in tmp:
                        errMsg.append(ph.clean_html(it))
                else:
                    errMsg = [
                     _('Connection error.')]
                self.sessionEx.open(MessageBox, _('Login failed.') + '\n' + ('\n').join(errMsg), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
                
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        mode = self.currItem.get('mode', '')
        printDBG('handleService: |||| name[%s], category[%s] ' % (name, category))
        self.currList = []
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_sort_mode')
        elif category == 'list_sort_mode':
            self.listSortMode(self.currItem, 'list_filters')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items', 'explore_item')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'rank_table':
            self.listRankRableItems(self.currItem, 'explore_item')
        elif category == 'list_items_2':
            self.listItems2(self.currItem, 'video')
        elif category == 'list_series_az':
            self.listLetters(self.currItem, 'list_series_letter', self.cacheSeriesLetter, self.cacheSetiesByLetter)
        elif category == 'list_series_letter':
            self.listByLetter(self.currItem, 'explore_item', self.cacheSetiesByLetter)
        elif category == 'list_cartoons_az':
            self.listLetters(self.currItem, 'list_cartoons_letter', self.cacheCartoonsLetter, self.cacheCartoonsByLetter)
        elif category == 'list_cartoons_letter':
            self.listByLetter(self.currItem, 'list_items_2', self.cacheCartoonsByLetter)
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category == 'm3u':
            self.listM3u(self.currItem, 'list_m3u_groups')
        elif category in ('search','search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'list_search_items':
            self.listSearchItems(self.currItem, 'explore_item')
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)
        return


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, AllBoxTV(), True, [])


