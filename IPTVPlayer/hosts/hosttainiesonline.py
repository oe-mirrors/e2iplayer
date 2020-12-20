# Embedded file name: /usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/hosts/hosttainiesonline.py
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json

from Components.config import config, ConfigSelection
config.plugins.iptvplayer.movieshdco_sortby = ConfigSelection(default='date', choices=[('date', _('Lastest')),
 ('views', _('Most viewed')),
 ('duree', _('Longest')),
 ('rate', _('Top rated')),
 ('random', _('Random'))])

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'https://tainiesonline.pro'


class tainiesonline(CBaseHostClass):
    HEADER = {'User-Agent': 'Mozilla/5.0',
     'Accept': 'text/html'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
    MAIN_URL = 'https://tainiesonline.pro'
    SEARCH_SUFFIX = '?s='
    MAIN_CAT_TAB = [{'category': 'movies',
      'mode': 'movies',
      'title': '\xce\xa4\xce\xb1\xce\xb9\xce\xbd\xce\xaf\xce\xb5\xcf\x82',
      'url': '',
      'icon': ''},
     {'category': 'list_items',
      'mode': 'series',
      'title': '\xce\x9e\xce\xad\xce\xbd\xce\xb5\xcf\x82 \xcf\x83\xce\xb5\xce\xb9\xcf\x81\xce\xad\xcf\x82',
      'url': 'https://tainiesonline.pro/katigoria/seires',
      'icon': ''},
     {'category': 'list_items',
      'mode': 'collection',
      'title': '\xce\xa3\xcf\x85\xce\xbb\xce\xbb\xce\xbf\xce\xb3\xce\xad\xcf\x82',
      'url': 'https://tainiesonline.pro/katigoria/collection',
      'icon': ''},
     {'category': 'search',
      'title': _('Search'),
      'search_item': True},
     {'category': 'search_history',
      'title': _('Search history')}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tainiesonline.tv',
         'cookie': 'tainiesonline.cookie'})
        self.DEFAULT_ICON_URL = 'https://img.tainiesonline.pro/wp-content/uploads/2019/03/tainiesonLOGO.png'
        self.defaultParams = {'use_cookie': True,
         'load_cookie': True,
         'save_cookie': True,
         'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheLinks = {}

    def _getFullUrl(self, url):
        if 0 < len(url) and not url.startswith('http'):
            url = self.MAIN_URL + url
        if not self.MAIN_URL.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type = 'dir'):
        printDBG('tainiesonline.listsTab')
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def fillCategories(self):
        printDBG('tainiesonline.fillCategories')
        self.cacheFilters = {}
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts:
            return
        moviesTab = [{'title': '2020',
          'url':('https://tainiesonline.pro/katigoria/tainiesonline/2020')},
         {'title': '2019',
          'url':('https://tainiesonline.pro/katigoria/tainiesonline/2019')},
         {'title': '2018',
          'url':('https://tainiesonline.pro/katigoria/tainiesonline/2018')},
         {'title': '2017',
          'url':('https://tainiesonline.pro/katigoria/tainiesonline/2017')},
         {'title': '2016',
          'url':('https://tainiesonline.pro/katigoria/2016')},
         {'title': '2013-2015',
          'url':('https://tainiesonline.peo/katigoria/new-good')},
         {'title': '\xce\x95\xce\xbb\xce\xbb\xce\xb7\xce\xbd\xce\xb9\xce\xba\xce\xad\xcf\x82 \xce\xa4\xce\xb1\xce\xb9\xce\xbd\xce\xaf\xce\xb5\xcf\x82',
          'url': self._getFullUrl('category/\xce\xb5\xce\xbb\xce\xbb-\xcf\x84\xce\xb1\xce\xb9\xce\xbd\xce\xaf\xce\xb5\xcf\x82/')}]
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '>\xce\xa4\xce\xb1\xce\xb9\xce\xbd\xce\xb9\xce\xb5\xcf\x82<', '</ul>', False)[1]
        tmp = re.compile('a[^>]*?href=(.+?)>*?>([^<]+?)<').findall(tmp)
        for item in tmp:
            if item[0].endswith('collection/'):
                continue
            if item[0].endswith('\xcf\x80\xcf\x81\xce\xbf\xcf\x83\xce\xb5\xcf\x87\xcf\x8e\xcf\x82/'):
                continue
            moviesTab.append({'title': self.cleanHtmlStr(item[1]),
             'url': self._getFullUrl(item[0])})

        moviesTab.append({'title': '\xce\x9a\xce\xb9\xce\xbd\xce\xbf\xcf\x8d\xce\xbc\xce\xb5\xce\xbd\xce\xb1 \xce\xa3\xcf\x87\xce\xad\xce\xb4\xce\xb9\xce\xb1 (\xce\xbc\xce\xb5 \xce\xbc\xce\xb5\xcf\x84\xce\xac\xcf\x86\xcf\x81\xce\xb1\xcf\x83\xce\xb7)',
         'url': self._getFullUrl('katigoria/\xce\xba\xce\xb9\xce\xbd-\xcf\x83\xcf\x87\xce\xad\xce\xb4\xce\xb9\xce\xb1/')})
        moviesTab.append({'title': '\xce\x9a\xce\xb9\xce\xbd\xce\xbf\xcf\x8d\xce\xbc\xce\xb5\xce\xbd\xce\xb1 \xce\xa3\xcf\x87\xce\xad\xce\xb4\xce\xb9\xce\xb1 (\xce\xbc\xce\xb5 \xcf\x85\xcf\x80\xcf\x8c\xcf\x84\xce\xb9\xcf\x84\xce\xbb\xce\xbf\xcf\x85\xcf\x82)',
         'url': self._getFullUrl('katigoria/\xce\xba\xce\xb9\xce\xbd-\xcf\x83\xcf\x87\xce\xad\xce\xb4\xce\xb9\xce\xb1-subs/')})
        moviesTab.append({'title': 'Anime Movies',
         'url': self._getFullUrl('katigoria/animemovies/')})
        self.cacheFilters['movies'] = moviesTab

    def listMoviesCategory(self, cItem, nextCategory):
        printDBG('tainiesonline.listMoviesCategory')
        if {} == self.cacheFilters:
            self.fillCategories()
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get('movies', []), cItem)

    def listItems(self, cItem, nextCategory = 'explore_item'):
        printDBG('tainiesonline.listItems')
        page = cItem.get('page', 1)
        url = cItem['url']
        if page > 1:
            url += '/page/' + str(page)
        if 'url_suffix' in cItem:
            url += cItem['url_suffix']
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('class=pages'), re.compile('</div>'), False)[1]
        if 'rel=next' in nextPage:
            nextPage = True
        else:
            nextPage = False
        data = self.cm.ph.getDataBeetwenMarkers(data, '<h1 class=', 'class=filmborder>', False)[1]
        data = data.split('class=moviefilm>')
        for item in data:
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, 'a[^>]*?href=(.+?)>*?>')[0])
            icon = self._getFullUrl(self.cm.ph.getSearchGroups(item, 'src=(.+?)>*?alt')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])
            if url.startswith('http'):
                params = dict(cItem)
                params.update({'category': nextCategory,
                 'good_for_fav': True,
                 'title': title,
                 'url': url,
                 'icon': icon})
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'),
             'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG('tainiesonline.exploreItem cItem')
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        else:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<strong><em>(.+?)</em></strong>')[0])
            if desc == '':
                desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<b>\xce\xa0\xce\x95\xce\xa1\xce\x99\xce\x9b\xce\x97\xce\xa8\xce\x97</b>(.+?)<blockquote')[0])
            if desc == '':
                desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '</p><div style="text-align: center;">(.+?)</div><p>')[0])
            if desc == '':
                desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<div\\s*class=separator\\s*style="clear: both;\\s*text-align:\\s*center;">([^<]+?)<')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]*?property=og:title[^>]*?content="([^"]+?)Tainies')[0])
            iconA = self._getFullUrl(self.cm.ph.getSearchGroups(data, 'og:image content=(.+?)>')[0])
            if '' == title:
                title = cItem['title']
            trailerMarker = '/trailer'
            sts, trailer = self.cm.ph.getDataBeetwenMarkers(data, trailerMarker, '</iframe>', False, False)
            if sts:
                trailer = self.cm.ph.getSearchGroups(trailer, '<iframe[^>]+?src=(.+?)width', 1, ignoreCase=True)[0]
                if trailer.startswith('//'):
                    trailer = 'http:' + trailer
                if trailer.startswith('http'):
                    params = dict(cItem)
                    params['title'] = 'TRAILER'
                    params['mode'] = 'trailer'
                    params['links'] = [{'name': 'TRAILER',
                      'url': trailer,
                      'need_resolve': 1}]
                    params['desc'] = desc
                    params.update({'icon': iconA})
                    self.addVideo(params)
            ms1 = '<b>\xce\xa0\xce\x95\xce\xa1\xce\x99\xce\x9b\xce\x97\xce\xa8\xce\x97</b>'
            if ms1 in data:
                m1 = ms1
            elif trailerMarker in data:
                m1 = trailerMarker
            else:
                m1 = '<!-- END TAG -->'
            sts, linksData = self.cm.ph.getDataBeetwenMarkers(data, m1, 'facebok', False, False)
            if not sts:
                return
            mode = cItem.get('mode', 'unknown')
            eLinks = {}
            episodes = []
            collectionID = ['-collection',
             '-trilogy',
             '-pentalogy',
             '-\xce\xb2\xce\xb4\xce\xbf\xce\xbc',
             '-\xcf\x83\xcf\x85\xce\xbb\xce\xbb\xce\xbf',
             '-\xce\xba\xce\xb1\xce\xbb\xcf\x8d\xcf\x84\xce\xb5\xcf\x81\xce\xb5\xcf\x82',
             '-\xce\xba\xce\xbf\xcf\x81\xcf\x85\xcf\x86\xce\xb1\xce\xaf\xce\xb5\xcf\x82']
            if any((idx in cItem['url'] for idx in collectionID)):
                mode = 'collect_item'
                spTab = [re.compile('<b>'), re.compile('<div\\s*class=separator\\s*style="clear: both;\\s*text-align:\\s*center;">'), re.compile('<div\\s+style="text-align\\:\\s+center;">')]
                for sp in spTab:
                    if None != sp.search(linksData):
                        break

                collectionItems = sp.split(linksData)
                if len(collectionItems) > 0:
                    del collectionItems[0]
                linksData = ''
                for item in collectionItems:
                    itemTitle = item.find('<')
                    if itemTitle < 0:
                        continue
                    itemTitle = self.cleanHtmlStr(item[:itemTitle])
                    linksData = re.compile('<a[^>]*?href=(.+?)target=').findall(item)
                    links = []
                    for itemUrl in linksData:
                        if itemUrl.startswith('/'):
                            itemUrl = self._getFullUrl(itemUrl)
                        if 1 != self.up.checkHostSupport(itemUrl):
                            continue
                        links.append({'name': self.up.getHostName(itemUrl),
                         'url': itemUrl,
                         'need_resolve': 1})

                    if len(links):
                        params = dict(cItem)
                        params.update({'title': itemTitle,
                         'mode': mode,
                         'links': links,
                         'desc': desc})
                        self.addVideo(params)

            elif '>Season' in linksData or '>\xce\xa3\xce\xb5\xce\xb6\xcf\x8c\xce\xbd' in linksData:
                if '>Season' in linksData:
                    seasonMarker = '>Season'
                else:
                    seasonMarker = '>\xce\xa3\xce\xb5\xce\xb6\xcf\x8c\xce\xbd'
                mode = 'episode'
                seasons = linksData.split(seasonMarker)
                if len(seasons) > 0:
                    del seasons[0]
                for item in seasons:
                    seasonID = item.find('<')
                    if seasonID < 0:
                        continue
                    seasonID = item[:seasonID + 1]
                    seasonID = self.cm.ph.getSearchGroups(seasonID, '([0-9]+?)[^0-9]')[0]
                    if '' == seasonID:
                        continue
                    episodesData = re.compile('<a[^>]*?href=(.+?)\\s.+?>([^<]+?)<\\/a>').findall(item)
                    for eItem in episodesData:
                        eUrl = eItem[0]
                        eID = eItem[1].strip()
                        if eUrl.startswith('//'):
                            eUrl += 'http'
                        if 1 != self.up.checkHostSupport(eUrl):
                            continue
                        linksID = '-S{0}E{1}'.format(seasonID, eID)
                        if linksID not in eLinks:
                            eLinks[linksID] = []
                            episodes.append({'linksID': linksID,
                             'episode': eID,
                             'season': seasonID})
                        eLinks[linksID].append({'name': self.up.getHostName(eUrl),
                         'url': eUrl,
                         'need_resolve': 1})

                for item in episodes:
                    linksID = item['linksID']
                    if len(eLinks[linksID]):
                        params = dict(cItem)
                        params.update({'title': title + linksID,
                         'mode': mode,
                         'episode': item['episode'],
                         'season': item['season'],
                         'links': eLinks[linksID],
                         'desc': desc})
                        self.addVideo(params)

            else:
                links = self.getLinksForMovie(linksData)
                if len(links):
                    params = dict(cItem)
                    params['mode'] = 'movie'
                    params['links'] = links
                    params['desc'] = desc
                    params.update({'icon': iconA})
                    self.addVideo(params)
            return

    def getLinksForMovie(self, data):
        printDBG('tainiesonline.getLinksForMovie---------------->')
        Btitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'title="(.+?)tainies')[0])
        if '' == Btitle:
            Btitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'alt="(.+?)\xcf\x84\xce\xb1\xce\xb9\xce\xbd\xce\xb9\xce\xb5\xcf\x82')[0])
        printDBG('Btitle--------------->' + Btitle)
        urlTab = []
        splitTab = [re.compile('\xcf\x80\xce\xb1\xcf\x81\xcf\x8c\xcf\x87\xce\xbf\xcf\x85\xcf\x82'), re.compile('\xcf\x80\xce\xac\xcf\x81\xce\xbf\xcf\x87\xce\xbf\xcf\x85\xcf\x82'), re.compile('<div\\s*class=separator\\s*style="clear: both;\\s*text-align:\\s*center;">')]
        for sp in splitTab:
            if None != sp.search(data):
                break

        DataItems = sp.split(data)
        if len(DataItems) > 0:
            del DataItems[0]
        for Item in DataItems:
            linksData = re.compile('href=(http[s]?:[^">\\s]*)').findall(Item)
            for item in linksData:
                url = item
                title = Btitle
                if url.startswith('/'):
                    url += 'http'
                if 1 != self.up.checkHostSupport(url):
                    continue
                name = self.up.getHostName(url)
                if url.startswith('//'):
                    url += 'http'
                if url.startswith('http'):
                    urlTab.append({'name': title + ': ' + name,
                     'url': url,
                     'need_resolve': 1})

        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('tainiesonline.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]' % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.MAIN_URL
        cItem['url_suffix'] = self.SEARCH_SUFFIX + urllib.quote_plus(searchPattern)
        cItem['mode'] = 'search'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG('tainiesonline.getLinksForVideo [%s]' % cItem)
        idx = cItem['mode'] + cItem['url'] + cItem.get('season', '') + cItem.get('episode', '')
        urlTab = self.cacheLinks.get(idx, [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}
        urlTab = cItem.get('links', [])
        self.cacheLinks[idx] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG('tainiesonline.getVideoLinks [%s]' % videoUrl)
        urlTab = []
        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG('tainiesonline.getArticleContent [%s]' % cItem)
        retTab = []
        if 'movie' == cItem.get('mode') or 'explore_item' == cItem.get('category'):
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return retTab
            sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<b>\xce\xa0\xce\x95\xce\xa1\xce\x99\xce\x9b\xce\x97\xce\xa8\xce\x97</b>', 'facebok')
            if not sts:
                return retTab
            title = self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:title"[^>]*?content="([^"]+?)"')[0]
            desc = self.cm.ph.getSearchGroups(data, '<strong><em>(.+?)</em></strong>')[0]
            if desc == '':
                desc = self.cm.ph.getSearchGroups(data, '</p><div style="text-align: center;">(.+?)</div><p>')[0]
            return [{'title': self.cleanHtmlStr(title),
              'text': self.cleanHtmlStr(desc),
              'images': [{'title': '',
                          'url': self._getFullUrl(icon)}],
              'other_info': {}}]
        else:
            return retTab

    def getFavouriteData(self, cItem):
        printDBG('tainiesonline.getFavouriteData')
        params = {'type': cItem['type'],
         'category': cItem.get('category', ''),
         'title': cItem['title'],
         'url': cItem['url'],
         'desc': cItem.get('desc', ''),
         'icon': cItem['icon']}
        return json.dumps(params)

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('tainiesonline.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()

        self.addDir(params)
        return True

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        mode = self.currItem.get('mode', '')
        printDBG('handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] ' % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'movies':
            self.listMoviesCategory(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False,
             'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history',
             'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)
        return


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, tainiesonline(), True, favouriteTypes=[])