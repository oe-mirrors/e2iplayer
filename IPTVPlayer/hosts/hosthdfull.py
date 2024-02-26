# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute_ext, is_js_cached
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetCookieDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
###################################################
# FOREIGN import
###################################################
from binascii import hexlify
from hashlib import md5
import time
import re
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.hdfull_language = ConfigSelection(default="es", choices=[("es", _("Spanish")), ("en", _("English"))])
config.plugins.iptvplayer.hdfull_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.hdfull_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language"), config.plugins.iptvplayer.hdfull_language))
    optionList.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.hdfull_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.hdfull_password))
    return optionList
###################################################


def gettytul():
    return 'https://hdfull.me/'


class SuggestionsProvider:
    MAIN_URL = 'https://hdfull.me/'
    COOKIE_FILE = ''

    def __init__(self):
        self.cm = common()
        self.lang = config.plugins.iptvplayer.hdfull_language.value
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultHeader(browser='chrome')['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items': {'language': self.lang}}

    def getName(self):
        return _("HDFull Suggestions")

    def getSuggestions(self, text, locale):
        lang = locale.split('-', 1)[0]
        if lang in ['es', 'en'] and self.lang != lang:
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['language'])
            self.lang = lang

        url = self.MAIN_URL + '/ajax/search.php'
        sts, data = self.cm.getPage(url, post_data={'q': text, 'limit': '10', 'timestamp': str(int(time.time() * 1000)), 'verifiedCheck': ''})
        if sts:
            retList = []
            for item in json_loads(data):
                retList.append(item['title'])
            return retList
        return None


def jstr(item, key, default=''):
    v = item.get(key, default)
    if None == v:
        return default
    else:
        return ensure_str(v)


class HDFull(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'hdfull.me', 'cookie': 'hdfull.me.cookie'})
        SuggestionsProvider.COOKIE_FILE = self.COOKIE_FILE

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        language = config.plugins.iptvplayer.hdfull_language.value
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items': {'language': language}}

        self.MAIN_URL = 'https://hdfull.me/'
        self.DEFAULT_ICON_URL = 'https://ocio.farodevigo.es/img_contenido/noticias/2018/02/642946/web_cine_pirata.jpg'

        self.filters = []
        self.cacheLinks = {}
        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        CBaseHostClass.setMainUrl(self, url)
        SuggestionsProvider.MAIN_URL = self.getMainUrl()

    def listMain(self, cItem):
        printDBG("HDFull.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        reObj = re.compile('<ul[^>]*?>')
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'dropdown'), ('</ul', '>'), False)
        for menuData in data:
            menuData = reObj.split(menuData, 1)
            menuUrl = self.getFullUrl(self.cm.ph.getSearchGroups(menuData[0], '''\shref=['"]([^'^"]+?)['"]''')[0])
            category = menuUrl.rsplit('/')[-1]
            if category in ['tv-shows', 'series']:
                category = 'list_sort_series'
            elif category in ['peliculas', 'movies']:
                category = 'list_sort_movies'
            elif category == '#':
                category = ''
            else:
                continue

            menuTitle = self.cleanHtmlStr(menuData[0])
            menuData = self.cm.ph.getAllItemsBeetwenMarkers(menuData[-1], '<li', '</li>')

            subItems = []
            if category:
                subItems = [MergeDicts(cItem, {'url': menuUrl, 'title': _('All'), 'category': category})]

            for item in menuData:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                params = {'url': url, 'title': title}
                if category:
                    params['category'] = category
                else:
                    tmp = url.split('#', 1)
                    if len(tmp) == 2:
                        params.update({'category': 'list_episodes_langs', 'url': tmp[0], 'f_action': tmp[1]})
                    else:
                        params['category'] = 'list_items'
                subItems.append(MergeDicts(cItem, params))

            if len(subItems):
                self.addDir(MergeDicts(cItem, {'url': menuUrl, 'title': menuTitle, 'category': 'sub_items', 'sub_items': subItems}))

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubItems(self, cItem):
        printDBG("HDFull.listSubItems")
        self.currList = cItem['sub_items']

    def listSortMoviesSeries(self, cItem, nextCategory1, nextCategory2):
        printDBG("HDFull.listSort")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        hasABCMenu = self.cm.ph.getDataBeetwenMarkers(data, 'filter-title', '</div>', False)[1]
        hasABCMenu = True if '>#<' in hasABCMenu else False

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'row-links-wrapper'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            category = url.rsplit('/')[-1]
            if hasABCMenu and category == 'abc':
                category = nextCategory2
                fixNextPage = False
            elif category in ['abc', 'date', 'imdb_rating']:
                category = nextCategory1
                fixNextPage = hasABCMenu
            else:
                printDBG("SKIP >> [%s] [%s] item[%s]" % (category, url, item))
                continue
            title = self.cleanHtmlStr(item)
            self.addDir(MergeDicts(cItem, {'url': url, 'title': title, 'category': category, 'fix_next_page': fixNextPage}))

    def listSeriesABC(self, cItem, nextCategory):
        printDBG("HDFull.listSeriesABC")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'filter-title'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            self.addDir(MergeDicts(cItem, {'url': url, 'title': title, 'category': nextCategory}))

    def _listItems(self, cItem, nextCategory, data):
        printDBG("HDFull._listItems")
        retList = []
        reLang = re.compile('/images/([^\.]+?)\.png')
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'view'), ('<div', '>', 'clear'), False)[1]
        data = re.compile('''<div[^>]+?view[^>]+?>''').split(data)
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])

            tmp = self.cm.ph.getDataBeetwenMarkers(item, '<h5', '</h5>')[1]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, '''title=['"]([^"^']+?)["']''', 1, True)[0])
            if title == '':
                title = self.cleanHtmlStr(tmp)

            desc = []
            # lang
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'left'), ('</div', '>'), False)[1]
            tmp = reLang.findall(tmp)
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t:
                    desc.append(t)
            desc = [', '.join(desc)]

            # rating
            item = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'right'), ('</div', '>'), False)[1]

            tmp = [self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'rating'), ('<', '>'), False)[1])]
            tmp.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'dec'), ('</', '>'), False)[1]))
            if tmp[0]:
                desc.append('.'.join(tmp))

            retList.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)}))
        return retList

    def listItems(self, cItem, nextCategory):
        printDBG("HDFull.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        page = cItem.get('page', 1)

        if cItem.get('fix_next_page'):
            nextPage = self.cm.meta['url']
            if page == 1:
                if nextPage.endswith('/'):
                    nextPage = nextPage[:-1]
            else:
                if nextPage.endswith('/'):
                    nextPage = nextPage[:-1]
                nextPage = nextPage.rsplit('/', 1)[0]
            nextPage += '/%d' % (page + 1)
        else:
            nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'filter-title', '</div>', False)[1]
            nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>\s*?%s\s*?<''' % (page + 1))[0])

        self.currList.extend(self._listItems(cItem, nextCategory, data))

        if nextPage and len(self.currList):
            self.addDir(MergeDicts(cItem, {'url': nextPage, 'title': _('Next page'), 'page': page + 1}))

    def _getLinks(self, cUrl, data):
        linksTab = []
        ad = self.cm.ph.getSearchGroups(data, '''var\s+?ad\s*?=\s*?['"]([^'^"]+?)['"]''', 1, True)[0]
        tmp = re.compile('''<script[^>]+?src=['"]([^'^"]*?(?:view|providers)[^'^"]*?\.js(?:\?[^'^"]*?)?)['"]''', re.I).findall(data)

        tabJs = {}
        for item in tmp:
            version = item.split('?', 1)[-1]
            if 'providers' in item:
                tabJs['providers'] = {'url': self.getFullUrl(item), 'hash': version + '.1'}
            elif 'view' in item:
                tabJs['view'] = {'url': self.getFullUrl(item), 'hash': version + '.1'}

        for key in tabJs.iterkeys():
            tabJs[key]['name'] = 'hdfull.me_%s' % key
            if not is_js_cached(tabJs[key]['name'], tabJs[key]['hash']):
                sts, jsdata = self.getPage(tabJs[key]['url'])
                if sts:
                    if 'providers' == key:
                        idx1 = jsdata.find('providers')
                        idx2 = jsdata.find(';', idx1 + 9)
                        funName = self.cm.ph.getSearchGroups(jsdata[idx2 + 1:], '''function\s+?([^\(]+?)\(''')[0]
                        tabJs[key]['code'] = 'function buildIframeEmbed(){return arguments[0];}\nbuildIframeGenericEmbed=buildIframeEmbed;\n' + jsdata[:idx2 + 1] + '; function %s(){return function(){};}' % funName
                        printDBG(">>>>")
                        printDBG(tabJs[key]['code'])
                        printDBG("<<<<")
                    else:
                        tmp = ['window=this,window.atob=function(e){e.length%4==3&&(e+="="),e.length%4==2&&(e+="=="),e=Duktape.dec("base64",e),decText="";for(var t=0;t<e.byteLength;t++)decText+=String.fromCharCode(e[t]);return decText};']
                        start = 0
                        while True:
                            idx1 = jsdata.find('String.prototype.', start)
                            if idx1 < 0:
                                break
                            idx2 = jsdata.find('{', idx1 + 17)
                            if idx2 < 0:
                                break
                            num = 1
                            while num > 0:
                                idx2 += 1
                                if idx2 >= len(jsdata):
                                    break
                                if jsdata[idx2] == '{':
                                    num += 1
                                elif jsdata[idx2] == '}':
                                    num -= 1
                            if num == 0:
                                tmp.append(jsdata[idx1:idx2 + 1])
                                start = idx2 + 1
                            else:
                                break
                        mark = 'this.options.links'
                        tt = 'function e2iLinks(r){r=%s;for(var i in r)provider=providers[r[i].provider],r[i].provider=provider.d.split("://")[1],r[i].embed=provider.e(r[i].code,"800","600"),r[i].download=provider.l(r[i].code,"800","600");print(JSON.stringify(r))}'
                        tmp.append(tt % self.cm.ph.getDataBeetwenMarkers(jsdata, mark + '=', ';', False)[1].replace(mark, 'r'))
                        tabJs[key]['code'] = '\n'.join(tmp)
                        printDBG(">>>>")
                        printDBG(tabJs[key]['code'])
                        printDBG("<<<<")
        try:
            js_params = [tabJs['providers']]
            js_params.append(tabJs['view'])
            js_params.append({'code': 'e2iLinks("%s");' % ad})
            ret = js_execute_ext(js_params)

            data = json_loads(ret['data'])
            for item in data:
                name = '%s | %s | %s ' % (item['lang'], item['provider'], item['quality'])
                url = item['embed']
                if not url:
                    url = item['download']
                linksTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})
        except Exception:
            printExc()

        return linksTab

    def exploreItem(self, cItem, nextCategory):
        printDBG("HDFull.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.getFullUrl(self.cm.meta['url'])
        self.setMainUrl(cUrl)

        desc = []
        descObj = self.getArticleContent(cItem, data)[0]
        for item in descObj['other_info']['custom_items_list']:
            desc.append(item[1])
        desc = ' | '.join(desc) + '[/br]' + descObj['text']

        trailer = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''var\s+?trailer\s*?=\s*?['"]([^'^"]+?)['"]''', 1, True)[0], cUrl)
        if trailer:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s - %s' % (cItem['title'], _('trailer')), 'url': strwithmeta(trailer, {'Referer': cUrl}), 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)

        linksTab = self._getLinks(cUrl, data)
        if len(linksTab):
            self.cacheLinks[cUrl] = linksTab
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': cUrl, 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)
        else:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'itemprop="season"'), ('</div', '>'))
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)["']''', 1, True)[0])
                title = self.cleanHtmlStr(item)

                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 's_title': cItem['title'], 'title': title, 'url': url, 'icon': icon, 'prev_url': cUrl, 'desc': desc})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("HDFull.listEpisodes")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.getFullUrl(self.cm.meta['url'])
        self.setMainUrl(cUrl)

        sid = self.cm.ph.getSearchGroups(data, '''var\s+?sid\s*?=\s*?['"]([0-9]+)['"]?;''')[0]
        cItem = MergeDicts(cItem, {'category': 'list_episodes2', 'url': cUrl, 'f_action': 'season', 'f_show': sid, 'f_season': cUrl.rsplit('-', 1)[-1]})
        self.listEpisodes2(cItem)

    def listEpisodes2(self, cItem):
        printDBG("HDFull.listEpisodes [%s]" % cItem)

        ITEMS = 24
        baseIconUrl = '/tthumb/220x124/'
        lang = config.plugins.iptvplayer.hdfull_language.value

        page = cItem.get('page', 0)

        baseEpisodeUrl = '/show/%s/season-%s/episode-%s' if lang == 'en' else '/serie/%s/temporada-%s/episodio-%s'
        post_data = {'action': cItem['f_action'], 'start': page * ITEMS, 'limit': ITEMS}
        if 'f_show' in cItem:
            post_data['show'] = cItem['f_show']
        if 'f_season' in cItem:
            post_data['season'] = cItem['f_season']
        if 'f_elang' in cItem:
            post_data['elang'] = cItem['f_elang'].upper()

        params = dict(self.defaultParams)
        params['header'] = MergeDicts(params['header'], {'Referer': cItem['url'], 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        sts, data = self.getPage(self.getFullUrl('/a/episodes'), params, post_data)
        if not sts:
            return

        try:
            data = json_loads(data)
            for item in data:
                sNum = jstr(item, 'season')
                eNum = jstr(item, 'episode')

                icon = self.getFullIconUrl(baseIconUrl + jstr(item, 'thumbnail'))
                title = '%s - s%se%s %s' % (jstr(item['show']['title'], lang), sNum.zfill(2), eNum.zfill(2), jstr(item['title'], lang))
                desc = jstr(item, 'date_aired') + ' | ' + (', '.join(item.get('languages', [])))
                url = self.getFullUrl(baseEpisodeUrl % (jstr(item, 'permalink'), sNum, eNum))

                self.addVideo({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
        except Exception:
            printExc()

        if len(self.currList) == ITEMS:
            self.addDir(MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1}))

    def listEpisodesLangs(self, cItem, nextCategory):
        printDBG("HDFull.listEpisodesLangs")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.getFullUrl(self.cm.meta['url'])
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'lang-bar'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            lang = self.cm.ph.getSearchGroups(item, '''data\-lang=['"]([^"^']+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            self.addDir(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'f_elang': lang}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        self.tryTologin()

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        post_data = {}
        data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'search'), ('</form', '>'), True, False)[1]
        actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^"^']+?)["']''', 1, True)[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>', False)
        for item in data:
            name = self.cm.ph.getSearchGroups(item, '''name=['"]([^"^']+?)['"]''')[0]
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
            if name != '':
                post_data[name] = value
        post_data.update({'query': searchPattern})

        httpParams = dict(self.defaultParams)
        httpParams['header'] = MergeDicts(httpParams['header'], {'Referer': self.cm.meta['url'], 'Content-Type': 'application/x-www-form-urlencoded'})

        sts, data = self.getPage(actionUrl, httpParams, post_data)
        if sts:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<h3', '</div>'), ('<div', '>', 'clear'))
            for sData in data:
                sData = sData.split('</div>', 1)
                sTtile = self.cleanHtmlStr(sData[0])
                subItem = self._listItems(cItem, 'explore_item', sData[1])

                if len(subItem):
                    params = MergeDicts(cItem, {'good_for_fav': False, 'category': 'sub_items', 'title': sTtile, 'sub_items': subItem})
                    self.addDir(params)

    def getLinksForVideo(self, cItem):
        self.tryTologin()

        if 0 != self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        linksTab = self.cacheLinks.get(cItem['url'], [])
        if linksTab:
            return linksTab

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return linksTab
        cUrl = self.cm.meta['url']

        printDBG(data)

        linksTab = self._getLinks(cUrl, data)

        if len(linksTab):
            self.cacheLinks[cUrl] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("HDFull.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        if 0 != self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        return []

    def _desc(self, data):
        desc = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for t in data:
            t = self.cleanHtmlStr(t)
            desc.append(t)
        return ', '.join(desc)

    def getArticleContent(self, cItem, data=None):
        printDBG("HDFull.getArticleContent [%s]" % cItem)
        retTab = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            self.tryTologin()
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'summary-title'), ('<div', '>', 'breakaway-wrapper'), False)[1]
        title = self.cleanHtmlStr(data[:data.find('</div')])
        icon = self.cm.ph.getSearchGroups(data, '''<img([^>]+?video\-page\-thumbnail[^>]+?)>''')[0]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'description'), ('</div', '>'), False)[1].split('<br', 1)
        desc = self.cleanHtmlStr(tmp[0])

        itemsList = []

        value = self.cm.ph.getSearchGroups(data, '''<([^>]+?datePublished[^>]+?)>''')[0]
        value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(value, '''content=['"]([^"^']+?)['"]''')[0])
        if value:
            itemsList.append((_('Published:'), value))

        item = tmp[-1]
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'details'), ('</div', '>'), False)[1].split('</p>')
        tmp.append(item)
        for item in tmp:
            header = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span', '</span>')[1])
            if header == '':
                continue
            value = self._desc(item)
            if value == '':
                continue
            itemsList.append((header, value))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.hdfull_login.value or \
            self.password != config.plugins.iptvplayer.hdfull_password.value:

            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['language'])

            loginCookie = GetCookieDir('hdfull.me.login')
            self.login = config.plugins.iptvplayer.hdfull_login.value
            self.password = config.plugins.iptvplayer.hdfull_password.value

            sts, data = self.getPage(self.getMainUrl())
            if sts:
                self.setMainUrl(self.cm.meta['url'])

            freshSession = False
            if sts and '/logout' in data:
                printDBG("Check hash")
                hash = hexlify(md5(ensure_binary('%s@***@%s' % (self.login, self.password))).digest())
                prevHash = ReadTextFile(loginCookie)[1].strip()

                printDBG("$hash[%s] $prevHash[%s]" % (hash, prevHash))
                if hash == prevHash:
                    self.loggedIn = True
                    return
                else:
                    freshSession = True

            rm(loginCookie)
            rm(self.COOKIE_FILE)
            if freshSession:
                sts, data = self.getPage(self.getMainUrl(), MergeDicts(self.defaultParams, {'use_new_session': True}))

            self.loggedIn = False
            if '' == self.login.strip() or '' == self.password.strip():
                return False

            if sts:
                actionUrl = self.cm.meta['url']
                post_data = {}
                data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login_form'), ('</form', '>'), True, False)[1]
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>', False)
                for item in data:
                    name = self.cm.ph.getSearchGroups(item, '''name=['"]([^"^']+?)['"]''')[0]
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
                    if name != '':
                        post_data[name] = value
                post_data.update({'username': self.login, 'password': self.password, 'action': 'login'})

                httpParams = dict(self.defaultParams)
                httpParams['header'] = MergeDicts(httpParams['header'], {'Referer': self.cm.meta['url'], 'Content-Type': 'application/x-www-form-urlencoded'})

                sts, data = self.getPage(actionUrl, httpParams, post_data)

            if sts and '/logout' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')

            if self.loggedIn:
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                WriteTextFile(loginCookie, hash)

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

        self.tryTologin()

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'})

        elif category in ['list_sort_series', 'list_sort_movies']:
            self.listSortMoviesSeries(self.currItem, 'list_items', 'list_series_abc')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'list_series_abc':
            self.listSeriesABC(self.currItem, 'list_items')

        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')

        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)

        elif category == 'list_episodes_langs':
            self.listEpisodesLangs(self.currItem, 'list_episodes2')

        elif category == 'list_episodes2':
            self.listEpisodes2(self.currItem)
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

    def getSuggestionsProvider(self, index):
        printDBG('HDFull.getSuggestionsProvider')
        return SuggestionsProvider()


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, HDFull(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('prev_url') or cItem.get('type') == 'video' or cItem.get('category') == 'explore_item':
            return True
        else:
            return False
