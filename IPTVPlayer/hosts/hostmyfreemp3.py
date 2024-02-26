# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
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

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'https://free-mp3-download.net/'


class MyFreeMp3(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'my-free-mp3.net', 'cookie': 'my-free-mp3.net.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://free-mp3-download.net/'
        self.DEFAULT_ICON_URL = 'https://free-mp3-download.net/img/logo.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("MyFreeMp3.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MyFreeMp3.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''src=['"]([^'^"]+?app\.min\.js(?:\?[^'^"]*?)?)['"]''')[0])
        sts, tmp = self.getPage(tmp)
        printDBG("MyFreeMp3.listSearchResult tmp[%s]" % tmp)
        url = self.cm.ph.getSearchGroups(tmp, '''['"]([^'^"]*?/search[^'^"]+?)['"]''')[0]
        url = url + searchPattern
        params = dict(cItem)
        params.update({'category': 'list_items', 'url': url})
        self.listItems(params)

    def listItems(self, cItem):
        printDBG("MyFreeMp3.listItems")

        sts, data = self.getPage(cItem['url'])
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
            next_page = data.get('next', '')
            for item in data['data']:
                try:
                    title = '%s - %s' % (self.cleanHtmlStr(item['artist']['name']), self.cleanHtmlStr(item.get('title', '')))
                    desc = str(timedelta(seconds=item['duration']))
                    if desc.startswith('0:'):
                        desc = desc[2:]
                    icon = ''
                    try:
                        desc += ' | ' + item['album']['title']
                        icon = item['album']['cover']
                    except Exception:
                        pass
                        #printExc()
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title': title, 'desc': desc, 'icon': icon, 'id': item.get('id', '')})
                    self.addAudio(params)
                except Exception:
                    printExc()
        except Exception:
            printExc()

        if len(self.currList):
            if next_page != '':
                params = dict(cItem)
                params.update({'url': next_page, 'title': _('Next page')})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("MyFreeMp3.getLinksForVideo [%s]" % cItem)

        try:
            id = cItem['id']

            url = self.getFullUrl('/download.php?id=%s' % id)
            sts, data = self.getPage(url)
            sitekey = ''
            if 'data-sitekey' in data:
                sitekey = self.cm.ph.getSearchGroups(data, 'data\-sitekey="([^"]+?)"')[0]

            token = ''
            if sitekey != '':
                token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'])
                if token != '':
                    printDBG("MyFreeMp3.getLinksForVideo token[%s]" % token)

            params = dict(self.defaultParams)
            params['raw_post_data'] = True
            params['header']['Referer'] = url
            post_data = '{"i":%s,"f":"mp3-320","h":"%s"}' % (id, token)
            sts, data = self.getPage(self.getFullUrl('/dl.php?'), params, post_data)
            printDBG("MyFreeMp3.getLinksForVideo post[%s]" % data)
            if '.mp3' in data:
                return [{'name': 'direct', 'url': strwithmeta(data.replace(' ', '%20'), {'User-Agent': self.USER_AGENT, 'Referer': url}), 'need_resolve': 0}]
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
