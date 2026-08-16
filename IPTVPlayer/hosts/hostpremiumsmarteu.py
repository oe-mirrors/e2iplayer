# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://premiumsmart.eu/'


class Premiumsmarteu(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'premiumsmart.eu', 'cookie': 'premiumsmart.eu.cookie'})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.API_URL = self.getFullUrl('api/v1/')
        self.DEFAULT_ICON_URL = self.getFullUrl('storage/branding_media/9a5b1890-53ce-4052-9a83-862d97a6b285.png')
        self.itemsPerPage = 50
        self.MENU = [
            {'category': 'list_sort', 'title': 'Filmy', 'url': self.API_URL + 'channel/filmy?perPage=%d' % self.itemsPerPage},
            {'category': 'list_sort', 'title': 'Seriale', 'url': self.API_URL + 'channel/seriale?perPage=%d' % self.itemsPerPage},
            {'category': 'search', 'title': _('Search'), 'search_item': True},
            {'category': 'search_history', 'title': _('Search history')},
        ]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("Premiumsmarteu.listMainMenu")
        self.listsTab(self.MENU, cItem)

    def listSort(self, cItem):
        printDBG("Premiumsmarteu.listSort")
        SORT_TAB = [
            {'category': 'list_items', 'title': 'Data dodania', 'url': cItem['url'] + '&order=created_at:desc'},
            {'category': 'list_items', 'title': 'Popularność', 'url': cItem['url'] + '&order=popularity:desc'},
            {'category': 'list_items', 'title': 'Data wydania', 'url': cItem['url'] + '&order=release_date:desc'},
            {'category': 'list_items', 'title': 'Ocena użytkowników', 'url': cItem['url'] + '&order=rating:desc'},
            {'category': 'list_items', 'title': 'Dochód', 'url': cItem['url'] + '&order=revenue:desc'},
            {'category': 'list_items', 'title': 'Budżet', 'url': cItem['url'] + '&order=budget:desc'},
        ]
        self.listsTab(SORT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("Premiumsmarteu.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']
        if page > 1:
            url = url + '&page={0}'.format(page)

        sts, data = self.getPage(url)
        if not sts:
            return

        try:
            if '/search/' in url:
                data = json_loads(data)['results']
                nextPage = False
            else:
                data = json_loads(data)['channel']['content']
                nextPage = data.get('next_page', False)
                data = data['data']
        except Exception:
            printExc()
            return

        for item in data:
            title = item.get('name', '')
            desc = item.get('description', '')
            icon = self.getFullIconUrl(item.get('poster', '')).replace('/original/', '/w500/')
            if item.get('is_series'):
                url = self.getFullUrl(self.API_URL + 'titles/%d/seasons' % item['id'])
                params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addDir(params)
            else:
                try:
                    url = self.getFullUrl(self.API_URL + 'watch/%d' % item['primary_video']['id'])
                except (KeyError, TypeError):
                    continue
                params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Premiumsmarteu.listSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        try:
            data = json_loads(data)
        except Exception:
            return

        for sItem in data.get('pagination', {}).get('data', []):
            sts, sdata = self.getPage(self.getFullUrl(cItem['url'] + '/%d/episodes' % sItem['number']))
            if not sts:
                continue
            sTitle = 'Sezon %d' % sItem['number']
            try:
                sdata = json_loads(sdata)
            except Exception:
                continue

            episodes = []
            for item in sdata.get('pagination', {}).get('data', []):
                try:
                    url = self.getFullUrl(self.API_URL + 'watch/%d' % item['primary_video']['id'])
                except Exception:
                    continue
                icon = self.getFullIconUrl(item.get('poster', ' ')).replace('/original/', '/w500/')
                episodes.append({'url': url, 'title': item.get('name', ''), 'desc': item.get('description', ''), 'icon': icon})
            if episodes:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': 'list_episodes', 'title': sTitle, 'episodes': episodes, 'icon': cItem.get('icon', ''), 'desc': ''})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Premiumsmarteu.listEpisodes")
        for item in cItem.get('episodes', []):
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Premiumsmarteu.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl(self.API_URL + 'search/%s?limit=20') % urllib_quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Premiumsmarteu.getLinksForVideo [%s]" % cItem)
        urltab = []
        url = cItem['url']

        sts, data = self.getPage(url)
        if not sts:
            return []

        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []

        for item in data.get('alternative_videos', []):
            playerUrl = item.get('src', '')
            if not playerUrl:
                continue
            name = item.get('name', '') + ' - ' + self.up.getHostName(playerUrl)
            if item.get('category') == 'trailer':
                name = '[trailer] ' + name
            urltab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': self.MAIN_URL}), 'need_resolve': 1})

        return urltab

    def getVideoLinks(self, url):
        printDBG("Premiumsmarteu.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def getArticleContent(self, cItem):
        printDBG("Premiumsmarteu.getArticleContent [%s]" % cItem)
        otherInfo = {}
        title = cItem.get("title", "")
        desc = cItem.get("desc", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": title, "text": desc, "images": [{"url": icon}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_sort':
            self.listSort(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_seasons':
            self.listSeasons(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Premiumsmarteu(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
