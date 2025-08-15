# Embedded file name: /IPTVPlayer/hosts/hostmp3co.py
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
import urllib
import re
from time import time
from datetime import timedelta

def gettytul():
    return 'https://mp3co.info/'


class MP3COInfo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'mp3co.info',
         'cookie': 'mp3co.info.cookie'})
        self.MAIN_URL = 'https://mp3co.info/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/i/mp3cobiz.png')
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer': self.getMainUrl(),
         'Origin': self.getMainUrl()})
        self.AJAX_HEADER = MergeDicts(self.HTTP_HEADER, {'X-Requested-With': 'XMLHttpRequest',
         'Accept': '*/*'})
        self.defaultParams = {'use_cookie': True,
         'load_cookie': True,
         'save_cookie': True,
         'cookiefile': self.COOKIE_FILE}

    def getDefaultParams(self, forAjax = False):
        header = self.AJAX_HEADER if forAjax else self.HTTP_HEADER
        return MergeDicts(self.defaultParams, {'header': header})

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE,
         'User-Agent': self.HTTP_HEADER['User-Agent']}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG('MP3COInfo.listMain')
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            cUrl = self.cm.meta['url']
            self.getFullUrl(cUrl)
            data = ph.find(data, ('<div', '>', 'genres'), '</ul>', flags=0)[1]
            data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
            for idx in range(1, len(data), 2):
                url = self.getFullUrl(ph.search(data[idx - 1], ph.A)[1])
                title = ph.clean_html(data[idx])
                category = 'radio_genres' if '/radio/' in url else 'list_items'
                self.addDir(MergeDicts(cItem, {'category': category,
                 'url': url,
                 'title': title}))

        MAIN_CAT_TAB = [{'category': 'search',
          'title': _('Search'),
          'search_item': True}, {'category': 'search_history',
          'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG('MP3COInfo.listMoviesItems %s' % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']
        if page > 1:
            if not url.endswith('/'):
                url += '/'
            url += 'page/%s/' % page
        sts, data = self.getPage(url, self.getDefaultParams(True))
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        try:
            data = json_loads(data)
            for item in data['songs']:
                url = self.getFullUrl(item['url'])
                title = ph.clean_html('%s - %s' % (item['artist'], item['title']))
                desc = str(timedelta(seconds=item['duration']))
                if desc.startswith('0:'):
                    desc = desc[2:]
                self.addAudio(MergeDicts(cItem, {'good_for_fav': True,
                 'url': url,
                 'title': title,
                 'desc': desc}))

            if data['count'] > data['page'] * data['limit']:
                self.addDir(MergeDicts(cItem, {'title': _('Next page'),
                 'page': page + 1}))
        except Exception:
            printExc()

    def listRadioGenres(self, cItem, nextCategory):
        printDBG('MP3COInfo.listRadioGenres %s' % cItem)
        sts, data = self.getPage(cItem['url'], self.getDefaultParams(True))
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        try:
            data = json_loads(data)
            for item in data['genres']:
                url = self.getFullUrl(item['url'])
                title = ph.clean_html(item['name'])
                self.addDir(MergeDicts(cItem, {'good_for_fav': True,
                 'category': nextCategory,
                 'url': url,
                 'title': title}))

        except Exception:
            printExc()

    def listRadioItems(self, cItem):
        printDBG('MP3COInfo.listRadioItems %s' % cItem)
        sts, data = self.getPage(cItem['url'], self.getDefaultParams(True))
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        try:
            data = json_loads(data)
            for item in data['stations']:
                url = self.getFullUrl(item['url'])
                title = ph.clean_html(item['name'])
                icon = self.getFullIconUrl(item.get('img', ''))
                self.addAudio(MergeDicts(cItem, {'good_for_fav': True,
                 'url': url,
                 'title': title,
                 'icon': icon}))

        except Exception:
            printExc()

    def listSearch(self, cItem, searchPattern, searchType):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)
        url = self.getFullUrl('/s/%s/' % urllib.quote_plus(searchPattern))
        cItem = {'type': 'category',
         'name': 'category',
         'category': 'list_items',
         'title': '',
         'url': url}
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG('MP3COInfo.getLinksForVideo [%s]' % cItem)
        urlsTab = []
        tmp = cItem['url'].split('#', 1)
        if len(tmp) == 2:
            sts, data = self.getPage(tmp[0], self.getDefaultParams(True))
            if not sts:
                return
            cUrl = self.cm.meta['url']
            self.setMainUrl(cUrl)
            try:
                data = json_loads(data)
                for item in data['stations']:
                    if item['id'] != tmp[1]:
                        continue
                    url = self.getFullUrl(item['stream_url'])
                    name = ph.clean_html(item['name'])
                    urlsTab.append({'url': strwithmeta(url, {'Referer': cUrl}),
                     'name': name,
                     'need_resolve': 0})

            except Exception:
                printExc()

        else:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return urlsTab
            cUrl = self.cm.meta['url']
            data = ph.find(data, ('<div', '>', 'actions'), '</div>', flags=0)[1]
            data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
            for idx in range(1, len(data), 2):
                url = self.getFullUrl(ph.search(data[idx - 1], ph.A)[1])
                name = ph.clean_html(data[idx])
                urlsTab.append({'url': strwithmeta(url, {'Referer': cUrl}),
                 'name': name,
                 'need_resolve': 0})

        return urlsTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        category = self.currItem.get('category', '')
        printDBG('handleService: || category[%s] ' % category)
        self.currList = []
        if not category:
            self.listMain({'type': 'category',
             'name': 'category'})
        elif category == 'radio_genres':
            self.listRadioGenres(self.currItem, 'radio_items')
        elif category == 'radio_items':
            self.listRadioItems(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'search':
            self.listSearch(self.currItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history',
             'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MP3COInfo(), True, [])