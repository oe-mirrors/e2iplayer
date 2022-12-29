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
###################################################
# FOREIGN import
###################################################
from datetime import timedelta
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://my-free-mp3.net/'


class MyFreeMp3(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'my-free-mp3.net', 'cookie': 'my-free-mp3.net.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://my-free-mp3.net/'
        self.DEFAULT_ICON_URL = 'https://my-free-mp3.net/img/logo.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.streamUrl = 'https://play.idmp3s.com/'

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

    def listMainMenu(self, cItem):
        printDBG("MyFreeMp3.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MyFreeMp3.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        #
        tmp = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]+?)['"]''')[0])
        sts, tmp = self.getPage(tmp)
        if sts:
            tmp = self.cm.ph.getSearchGroups(tmp, '''['"]([^'^"]*?/newtab[^'^"]+?)['"]''')[0]
            if tmp != '':
                self.streamUrl = self.getFullUrl(tmp)
            if not self.streamUrl.endswith('/'):
                self.streamUrl += '/'
            self.streamUrl = self.cm.getBaseUrl(self.streamUrl)

        url = self.getFullUrl('/api/search.php?callback=jQuery2130550300194200308_1532280982151')
        data = self.cm.ph.getDataBeetwenNodes(data, ('<select', '>', 'sort'), ('</select', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
        for item in data:
            sort = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
            params = dict(cItem)
            params.update({'category': 'list_items', 'url': url})
            params['post_data'] = {'q': searchPattern} #'sort':'2', 'count':'300', 'performer_only':'0'
            if sort == '':
                params['title'] = _('Default')
            else:
                params['title'] = self.cleanHtmlStr(item)
                params['post_data'].update({'sort': sort})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("MyFreeMp3.listItems")
        page = cItem.get('page', 0)

        post_data = dict(cItem['post_data'])
        post_data['page'] = page

        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts:
            return

        m1 = data.find('(')
        m2 = data.rfind(')')
        if -1 in [m1, m2]:
            return

        data = data[m1 + 1:m2]
        try:
            data = byteify(json.loads(data), '')
            printDBG(data)
            for item in data['response']:
                try:
                    title = '%s - %s' % (self.cleanHtmlStr(item.get('artist', '')), self.cleanHtmlStr(item.get('title', '')))
                    desc = str(timedelta(seconds=item['duration']))
                    if desc.startswith('0:'):
                        desc = desc[2:]
                    icon = ''
                    try:
                        desc += ' | ' + item['album']['title']
                        icons = []
                        for key in item['album']['thumb']:
                            val = item['album']['thumb'][key]
                            if not self.cm.isValidUrl(str(val)):
                                continue
                            key = int(key.split('_')[-1])
                            icons.append((key, val))
                        icons.sort(reverse=True)
                        icon = icons[0][1]
                    except Exception:
                        pass
                        #printExc()
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title': title, 'desc': desc, 'icon': icon, 'priv_data': item})
                    self.addAudio(params)
                except Exception:
                    printExc()
        except Exception:
            printExc()

        if len(self.currList):
            params = dict(cItem)
            params.update({'post_data': post_data, 'page': page + 1, 'title': _('Next page')})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("MyFreeMp3.getLinksForVideo [%s]" % cItem)

        map = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvxyz123'

        def encode(input):
            length = len(map)
            encoded = ""
            if input == 0:
                return map[0]
            if input < 0:
                input *= -1
                encoded += "-"
            while input > 0:
                val = input % length
                input = input / length
                encoded += map[val]
            return encoded

        try:
            item = cItem['priv_data']
            if 'aid' in item:
                id = item['aid']
            else:
                id = item['id']

            url = self.streamUrl + 'stream/%s:%s' % (encode(item['owner_id']), encode(id))
            #url  = 'http://streams.my-free-mp3.net/stream/%s:%s' % (encode(item['owner_id']), encode(item['aid']))
            return [{'name': 'direct', 'url': strwithmeta(url, {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl()})}]
        except Exception:
            printExc()

        return []

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
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, MyFreeMp3(), True, [])
