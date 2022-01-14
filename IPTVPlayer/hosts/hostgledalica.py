# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
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
    return 'https://gledalica.com/'


class Gledalica(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'gledalica.com', 'cookie': 'gledalica.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www.filmoviplex.com/'
        self.DEFAULT_ICON_URL = 'http://cdn-thumbshot.pearltrees.com/ec/c9/ecc93fbd8a258ceb455d61382ffde798-pearlsquare.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.cacheSeriesLetter = []
        self.cacheSetiesByLetter = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

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

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Gledalica.listMainMenu")
        #sts, data = self.getPage(self.getMainUrl())
        #if not sts: return
        #self.setMainUrl(data.meta['url'])
        MAIN_CAT_TAB = [{'category': 'sort', 'title': 'FILMOVI', 'url': self.getFullUrl('/browse-all-videos-1.html')},
                        {'category': 'sort', 'title': 'SERIJE ', 'url': self.getFullUrl('/browse-series-videos-1.html')},
#                        {'category':'years',          'title': _('By years'),      'url':self.getMainUrl()},
#                        {'category':'cats',           'title': _('By category'),   'url':self.getMainUrl()},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCats(self, cItem, nextCategory1, nextCategory2):
        printDBG("Gledalica.listCats")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'list_cats'), ('</div', '>'), False)[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = nextCategory1
                    self.listCatItems(params, nextCategory2)
                except Exception:
                    printExc()

    def listCatItems(self, cItem, nextCategory):
        printDBG("Gledalica.listCatItems")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat']) #self.cm.ph.getDataBeetwenNodes(item['dat'], ('<div', '>', 'title'), ('</div', '>'))[1]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listTopMenu(self, cItem, nextCategory):
        printDBG("Gledalica.listTopMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<optgroup', '>'), ('</optgroup', '>'))
        for groupItem in data:
            subItems = []
            groupTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(groupItem, '''label=['"]([^"^']+?)['"]''')[0])
            groupItem = groupItem.split('<option')
            groupItem.append('')
            subSubItems = []
            prevItem = {'sub_items': []}
            for item in groupItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''value=['"](https?://[^"^']+?)['"]''')[0])
                title = self.cm.ph.getDataBeetwenMarkers(item, '>', '<', False)[1]
                if title == '':
                    title = _('--All--')
                if '&nbsp;&nbsp;&nbsp;' in title and url != '':
                    prevItem['sub_items'].append({'title': self.cleanHtmlStr(title).strip(), 'url': url})
                else:
                    if 'url' in prevItem:
                        subSubItems.append(prevItem)
                        prevItem = {'sub_items': []}
                    if url != '':
                        prevItem.update({'title': self.cleanHtmlStr(title).strip(), 'url': url})
            if len(subSubItems):
                params = dict(cItem)
                params.update({'title': groupTitle, 'category': nextCategory, 'sub_items': subSubItems})
                self.addDir(params)

    def listSubItems(self, cItem, nextCategory):
        printDBG("Gledalica.listSubItems")
        subList = cItem['sub_items']
        for item in subList:
            params = {'name': 'category', 'type': 'category', 'good_for_fav': True}
            params.update(item)
            if len(item.get('sub_items', [])):
                params['category'] = cItem['category']
            else:
                params['category'] = nextCategory
            self.addDir(params)

    def listTopItems(self, cItem, nextCategory):
        printDBG("Gledalica.listTopItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenMarkers(data, 'topvideos_results', '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')

            if len(item) < 5:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item[3], '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item[1], '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item[3])
            if title == '':
                title = self.cm.ph.rgetDataBeetwenMarkers2(url, '-video_', '/', False)[1].replace('-', ' ').title()
            desc = ' | '.join([self.cleanHtmlStr(item[0]), self.cleanHtmlStr(item[2]), self.cleanHtmlStr(item[4])])
            params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
            if '-video_' not in url:
                params['category'] = nextCategory
                self.addDir(params)
            else:
                self.addVideo(params)

    def listSort(self, cItem, nextCategory):
        printDBG("Gledalica.listSort")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sorting'), ('</ul', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            self.addDir({'category': nextCategory, 'url': url, 'title': title})

        if 0 == len(self.currList):
            params = dict(cItem)
            params['category'] = nextCategory
            self.listItems(params, 'sort', data)

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("Gledalica.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>\s*?{0}\s*?<'''.format(page + 1))[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'cbp-rfgrid'), '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data-original=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0])
            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': ' | '.join(desc), 'icon': icon}
            if 'SERIJA' in item:
                params['category'] = 'list_series'
                self.addDir(params)
            else:
                self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listYears(self, cItem, nextCategory):
        printDBG("Gledalica.listYears")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'index_new_videos'), ('</div', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            self.addDir({'category': nextCategory, 'url': url, 'title': title})

    def listSeries(self, cItem):
        printDBG("Gledalica.listSeries [%s]" % cItem)
        self.addDir({'category': 'a_z', 'url': cItem['url'], 'title': _('A-Z')})
        self.addDir({'category': 'sort', 'url': cItem['url'], 'title': _('Episodes')})

    def exploreItem(self, cItem):
        printDBG("Gledalica.exploreItem [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

#        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
#        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>\s*?{0}\s*?<'''.format(page + 1))[0])

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<script>', '</script>')
        for item in data:
            if 'seriesInfo(' in item:
                jsdata = item
                break
        baseUrl = self.cm.ph.getSearchGroups(jsdata, '''baseUrl\s=\s['"]([^"^']+?)['"]''')[0]
        apikey = self.cm.ph.getSearchGroups(jsdata, '''apikey\s=\s['"]([^"^']+?)['"]''')[0]
        id = self.cm.ph.getSearchGroups(jsdata, '''id\s=\s([^"^']+?),''')[0]
        test = self.cm.ph.getAllItemsBeetwenMarkers(jsdata, '$(".openload', '\n')
        printDBG("Gledalica.listSeries test[%s]" % test)
        sts, data = self.getPage(baseUrl + id + apikey)
        if not sts:
            return
        try:
            data = json_loads(data)
            seasons = data['number_of_seasons']
        except Exception:
            printExc()
        printDBG("Gledalica.listSeries seasons[%s]" % seasons)

        for x in range(1, seasons + 1):
            sts, data = self.getPage(baseUrl + id + '/season/' + str(x) + apikey)
            if not sts:
                return
            try:
                data = json_loads(data)
                data = data['episodes']
                y = 1
                for item in data:
                    links = test[x - 1].split('$(".openload')
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(links[y], '''src=['"]([^"^']+?)['"]''')[0])
                    y += 1
                    if url == '':
                        continue
                    title = 'S' + str(item['season_number']) + 'E' + str(item['episode_number']) + ' - ' + item['name']
                    desc = item['overview']
                    params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': cItem['icon']}
                    self.addVideo(params)
            except Exception:
                printExc()
            printDBG("Gledalica.listSeries episodes[%s]" % data)

#        desc = []
#        tmp =  self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
#        for t in tmp:
#            t = self.cleanHtmlStr(t)
#            if t != '': desc.append(t)
#        params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':' | '.join(desc), 'icon':icon}
#        if '>serija<' in item:
#            params['category'] = 'list_series'
#            self.addDir(params)
#        else: self.addVideo(params)

    def listAZ(self, cItem, nextCategory):
        printDBG("Gledalica.listAZ")
        if 0 == len(self.cacheSeriesLetter):
            self.cacheSeriesLetter = []
            self.cacheSetiesByLetter = {}

            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(data.meta['url'])

            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'list_subcats'), ('</table', '>'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                if url == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title == '':
                    continue
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                letter = title.decode('utf-8')[0].upper().encode('utf-8')
                if not letter.isalpha():
                    letter = '#'

                if letter not in self.cacheSeriesLetter:
                    self.cacheSeriesLetter.append(letter)
                    self.cacheSetiesByLetter[letter] = []
                self.cacheSetiesByLetter[letter].append({'title': title, 'url': url, 'desc': '', 'icon': icon})

        for letter in self.cacheSeriesLetter:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': letter, 'desc': '', 'f_letter': letter})
            self.addDir(params)

    def listByLetter(self, cItem, nextCategory):
        printDBG("Gledalica.listByLetter")
        letter = cItem['f_letter']
        tab = self.cacheSetiesByLetter[letter]
        cItem = dict(cItem)
        cItem.update({'good_for_fav': True, 'category': nextCategory, 'desc': ''})
        self.listsTab(tab, cItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Gledalica.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/search.php?keywords=%s&btn=Search') % urllib.quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params, 'sort')

    def getLinksForVideo(self, cItem):
        printDBG("Gledalica.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])

        cUrl = cItem['url']
        url = cItem['url']

        retTab = []
        params['header']['Referer'] = cUrl
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>', 'link.php'), ('</iframe', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
            sts, data = self.getPage(url, params)
            if not sts:
                return []
            playerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
            if 1 != self.up.checkHostSupport(playerUrl):
                continue
            retTab.append({'name': self.up.getHostName(playerUrl), 'url': strwithmeta(playerUrl, {'Referer': cUrl}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Gledalica.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        return self.up.getVideoLinkExt(baseUrl)

    def getArticleContent(self, cItem):
        printDBG("Gledalica.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'enclosed'), ('</div', '>'))[1])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'detail_page'), ('</table', '>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '<img[^>]+?src="([^"]+?\.(:?jpe?g|png)(:?\?[^"]+?)?)"')[0], cUrl)
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h', '>'), ('</h', '>'))[1])

        keysMap = {'kategorija:': 'genre',
                   'imdb rating:': 'imdb_rating',
                   'runtime:': 'duration',
                   'uloge:': 'actors',
                   'premijera': 'released',
                   'zemlja:': 'country',
                   'jezik:': 'language',
                   'reziser:': 'director',
                   'votes:': 'views'}

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>'), ('</span', '>'))
        printDBG(tmp)
        for idx in range(1, len(tmp)):
            val = self.cleanHtmlStr(tmp[idx])
            if val == '' or val.lower() == 'n/a':
                continue
            key = self.cleanHtmlStr(tmp[idx - 1]).decode('utf-8').lower().encode('utf-8')
            if key not in keysMap:
                continue
            otherInfo[keysMap[key]] = val

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None and category == '':
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'})
        elif category == 'topvideos':
            self.listTopMenu(self.currItem, 'sub_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem, 'top_items')
        elif category == 'top_items':
            self.listTopItems(self.currItem, 'list_items')

        elif category == 'cats':
            self.listCats(self.currItem, 'cat_items', 'sort')
        elif category == 'cat_items':
            self.listCatItems(self.currItem, 'sort')

        elif category == 'sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'sort')
        elif category == 'years':
            self.listYears(self.currItem, 'sort')

        elif category == 'list_series':
            self.exploreItem(self.currItem)
        elif category == 'a_z':
            self.listAZ(self.currItem, 'list_by_letter')
        elif category == 'list_by_letter':
            self.listByLetter(self.currItem, 'sort')

    #SECTIONS
        elif category == 'sections':
            self.listSections(self.currItem, 'list_sub_items', 'explore_item')
            if 1 == len(self.currList):
                self.listSubItems(self.currList[0])
        elif category == 'list_sub_items':
            self.listSubItems(self.currItem)
    #MOVIES
        elif category == 'movies':
            self.listMovies(self.currItem, 'list_filters')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
    #SERIES

    #RAITING
        elif category == 'raiting':
            self.listRaitingItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_sub_items')
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
        CHostBase.__init__(self, Gledalica(), True, [])

    def withArticleContent(self, cItem):
        if '-video_' in cItem.get('url', ''):
            return True
        else:
            return False
