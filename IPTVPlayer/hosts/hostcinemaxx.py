# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetJSScriptFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.hdgocc import HdgoccParser
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
import re
import time
import math
import cookielib
###################################################


def gettytul():
    return 'http://cinemaxx.cc/'


class Cinemaxx(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cinemaxx.cc', 'cookie': 'cinemaxx.cc.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'http://cinemaxx.cc/'
        self.DEFAULT_ICON_URL = 'https://fdtech.pl/wp-content/uploads/2017/01/kinowy-40-100k-765x509.jpg' #self.getFullIconUrl('/templates/flat-cinema/images/logo.png')

        self.cacheLinks = {}
        self.hdgocc = HdgoccParser()

    def getPage(self, baseUrl, addParams={}, post_data=None):
        tries = 0
        cUrl = ''
        while tries < 4:
            tries += 1
            if addParams == {}:
                addParams = dict(self.defaultParams)
            sts, data = self.cm.getPage(baseUrl, addParams, post_data)
            if not sts:
                return sts, data
            cUrl = self.cm.meta['url']
            if 'DDoS' in data:
                if tries == 1:
                    rm(self.COOKIE_FILE)
                    continue
                timestamp = time.time() * 1000
                jscode = ''
                tmp = ph.findall(data, ('<script', '>'), '</script>', flags=0)
                for item in tmp:
                    if 'xhr.open' in item:
                        jscode = item
                        break
                js_params = [{'path': GetJSScriptFile('cinemaxx1.byte')}]
                js_params.append({'code': jscode})
                ret = js_execute_ext(js_params)
                if ret['sts'] and 0 == ret['code']:
                    try:
                        tmp = ret['data'].split('\n', 1)
                        sleep_time = int(float(tmp[1]))
                        tmp = json_loads(tmp[0])
                        url = self.getFullUrl(tmp['1'], cUrl)
                        params = dict(addParams)
                        params['header'] = MergeDicts(self.HTTP_HEADER, {'Referer': cUrl})
                        sts2, data2 = self.cm.getPage(url, params)
                        if not sts2:
                            break
                        js_params = [{'path': GetJSScriptFile('cinemaxx2.byte')}]
                        js_params.append({'code': data2 + 'print(JSON.stringify(e2iobj));'})
                        ret = js_execute_ext(js_params)
                        if ret['sts'] and 0 == ret['code']:
                            cj = self.cm.getCookie(self.COOKIE_FILE)
                            for item in json_loads(ret['data'])['cookies']:
                                for cookieKey, cookieValue in item.iteritems():
                                    cookieItem = cookielib.Cookie(version=0, name=cookieKey, value=cookieValue, port=None, port_specified=False, domain='.' + self.cm.getBaseUrl(cUrl, True), domain_specified=True, domain_initial_dot=True, path='/', path_specified=True, secure=False, expires=time.time() + 3600 * 48, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
                                    cj.set_cookie(cookieItem)
                            cj.save(self.COOKIE_FILE, ignore_discard=True)

                            sleep_time -= time.time() * 1000 - timestamp
                            if sleep_time > 0:
                                GetIPTVSleep().Sleep(int(math.ceil(sleep_time / 1000.0)))
                            continue
                        else:
                            break
                    except Exception:
                        printExc()
                else:
                    break
        if sts and cUrl:
            self.cm.meta['url'] = cUrl
        return sts, data

    def listMain(self, cItem, nextCategory):
        printDBG("Cinemaxx.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        subItems = []
        tmp = ph.findall(data, ('<div', '>', 'owl-cat'), '</div>')
        for item in tmp:
            icon = self.getFullIconUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1])
            item = ph.find(item, ('<h2', '>'), '</h2>', flags=0)[1]
            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
            title = self.cleanHtmlStr(item)
            subItems.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}))

        printDBG(subItems)
        sections = ph.find(data, ('<div', '>', 'navbar-collapse'), '</div>')[1]
        sections = ph.rfindall(sections, '</li>', ('<li', '>', 'nav'), flags=0)
        for section in sections:
            tmp = ph.findall(section, ('<a', '>'), '</a>', flags=ph.START_S, limits=1)
            if not tmp:
                continue
            sTitle = ph.clean_html(tmp[1])
            sUrl = ph.getattr(tmp[0], 'href')

            if sUrl == '/':
                self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'sub_items': subItems, 'title': sTitle}))
            elif '<ul' in section:
                subItems = []
                section = ph.findall(section, ('<li', '>'), '</li>', flags=0)
                for item in section:
                    title = ph.clean_html(item)
                    url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
                    subItems.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}))
                if len(subItems):
                    self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'sub_items': subItems, 'title': sTitle}))
            else:
                self.addDir(MergeDicts(cItem, {'category': nextCategory, 'url': self.getFullUrl(sUrl), 'title': sTitle}))

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubItems(self, cItem):
        printDBG("Cinemaxx.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("Cinemaxx.listItems")
        cItem = dict(cItem)
        page = cItem.get('page', 1)
        post_data = cItem.pop('post_data', None)

        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        printDBG(data)

        tmp = ph.find(data, ('<div', '>', 'pages-numbers'), '</div>')[1]
        tmp = ph.search(tmp, '''<a([^>]+?)>%s<''' % (page + 1))[0]
        nextPage = self.getFullUrl(ph.getattr(tmp, 'href'))

        data = ph.find(data, ('<div', '>', 'shortstory'), ('<div', '>', 'clearfix'))[1]
        data = ph.rfindall(data, '</div>', ('<div', '>', 'shortstory'))
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
            icon = self.getFullIconUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1])
            title = self.cleanHtmlStr(ph.find(item, ('<h', '>'), '</h', flags=0)[1])

            desc = []
            tmp = [ph.find(item, ('<', '>', 'current-rating'), ('</', '>'), flags=0)[1] + '/100']
            tmp.extend(ph.findall(item, ('<span', '>'), '</span>', flags=0))
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t:
                    desc.append(t)
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)}))

        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1}))

    def exploreItem(self, cItem, nextCategory):
        printDBG("Cinemaxx.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        desc = []
        descObj = self.getArticleContent(cItem, data)[0]
        icon = descObj['images'][0]['url']
        baseTitle = descObj['title']
        for item in descObj['other_info']['custom_items_list']:
            desc.append(item[1])
        desc = ' | '.join(desc) + '[/br]' + descObj['text']

        data = ph.find(data, ('<div', '>', 'dle-content'), ('<div', '>', 'fstory-info'), flags=0)[1]
        trailer = ph.find(data, ('<', '>', '#trailer'), '</div>', flags=0)[1]
        title = self.cleanHtmlStr(trailer)
        trailer = self.getFullUrl(ph.search(trailer, ph.IFRAME_SRC_URI_RE)[1])
        if trailer:
            self.addVideo({'good_for_fav': True, 'prev_url': cUrl, 'title': '%s %s' % (title, baseTitle), 'url': trailer, 'icon': icon, 'desc': desc})

        data = ph.find(data, ('<div', '>', 'full-video'), '</div>', flags=0)[1]
        url = self.getFullUrl(ph.search(data, ph.IFRAME_SRC_URI_RE)[1])
        if url:
            if ('/video/' in url and '/serials/' in url) or 'playlist' in url:
                url = strwithmeta(url, {'Referer': cUrl})
                seasons = self.hdgocc.getSeasonsList(url)
                for item in seasons:
                    self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'prev_url': cUrl, 'category': nextCategory, 'serie_title': baseTitle, 'title': 'Staffel %s' % item['title'], 'season_id': item['id'], 'url': item['url'], 'icon': icon, 'desc': desc}))

                if 0 != len(seasons):
                    return

                seasonUrl = url
                episodes = self.hdgocc.getEpiodesList(seasonUrl, -1)
                for item in episodes:
                    title = '{0} - {1} - s01e{2} '.format(baseTitle, item['title'], str(item['id']).zfill(2))
                    self.addVideo({'good_for_fav': False, 'type': 'video', 'prev_url': cUrl, 'title': title, 'url': item['url'], 'icon': icon, 'desc': desc})

                if 0 != len(episodes):
                    return

            self.addVideo({'good_for_fav': False, 'prev_url': cUrl, 'title': baseTitle, 'url': url, 'icon': icon, 'desc': desc})
        else:
            data = ph.find(data, 'vk.show(', ');', flags=0)[1].split(',', 1)[-1]
            ret = js_execute('print(JSON.stringify(%s));' % data)
            if ret['sts'] and 0 == ret['code']:
                try:
                    data = json_loads(ret['data'])
                    for sNum, season in enumerate(data, 1):
                        subItems = []
                        for eNum, episode in enumerate(season, 1):
                            title = baseTitle + ' s%se%s' % (str(sNum).zfill(2), str(eNum).zfill(2))
                            subItems.append({'good_for_fav': False, 'type': 'video', 'prev_url': cUrl, 'title': title, 'url': episode, 'icon': icon, 'desc': desc})
                        if subItems:
                            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'prev_url': cUrl, 'title': 'Staffel %s' % (str(sNum).zfill(2)), 'category': 'sub_items', 'sub_items': subItems}))
                except Exception:
                    printExc()

    def listEpisodes(self, cItem):
        printDBG("Cinemaxx.listEpisodes")

        title = cItem['serie_title']
        id = cItem['season_id']

        episodes = self.hdgocc.getEpiodesList(cItem['url'], id)

        for item in episodes:
            self.addVideo(MergeDicts(cItem, {'title': '{0} - s{1}e{2} {3}'.format(title, str(id).zfill(2), str(item['id']).zfill(2), item['title']), 'url': item['url']}))

    def listSearchResult(self, cItem, searchPattern, searchType):

        url = self.getFullUrl('/api/private/get/search?query=%s&limit=100&f=1' % urllib.quote(searchPattern))
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        value = ph.search(data, '''var\s*?dle_login_hash\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
        post_data = {'query': searchPattern, 'user_hash': value, 'do': 'search', 'subaction': 'search', 'story': searchPattern}
        self.listItems(MergeDicts(cItem, {'url': self.getFullUrl('/index.php?do=search'), 'post_data': post_data}), 'explore_item')

    def getLinksForVideo(self, cItem):
        linksTab = self.cacheLinks.get(cItem['url'], [])
        if linksTab:
            return linksTab

        linksTab = self.up.getVideoLinkExt(cItem['url'])
        for item in linksTab:
            item['need_resolve'] = 1

        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("Cinemaxx.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        return [{'name': 'direct', 'url': videoUrl}]

    def getArticleContent(self, cItem, data=None):
        printDBG("Cinemaxx.getArticleContent [%s]" % cItem)
        retTab = []
        itemsList = []

        if not data:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts:
                return []
            self.setMainUrl(self.cm.meta['url'])

        tmp = ph.find(data, ('<div', '>', 'dle-content'), ('<div', '>', 'fstory-info'), flags=0)[1]
        title = self.cleanHtmlStr(ph.find(tmp, ('<h1', '>'), '</h1>', flags=0)[1])
        icon = self.getFullIconUrl(ph.search(tmp, ph.IMAGE_SRC_URI_RE)[1])
        desc = self.cleanHtmlStr(ph.find(data, ('<div', '>', 'fstory-content'), '</div>', flags=0)[1])

        data = ph.find(data, ('<div', '>', 'finfo'), ('<div', '>', 'fstory-content'), flags=0)[1]
        data = ph.rfindall(data, '</div>', ('<div', '>', 'finfo-block'), flags=0)

        for item in data:
            key = self.cleanHtmlStr(ph.find(item, ('<div', '>', 'title'), '</div>', flags=0)[1])
            if 'current-rating' in item:
                value = self.cleanHtmlStr(ph.find(item, ('<', '>', 'current-rating'), ('</', '>'), flags=0)[1] + '/100')
            else:
                value = self.cleanHtmlStr(ph.find(item, ('<div', '>', 'text'), '</div>', flags=0)[1].rsplit('</ul>', 1)[-1])
            itemsList.append((key, value))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'}, 'list_items')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')

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
        CHostBase.__init__(self, Cinemaxx(), True, [])

    def withArticleContent(self, cItem):
        return True if 'explore_item' == cItem.get('category') or 'prev_url' in cItem else False
