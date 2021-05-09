# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://musicmp3.ru/'


class MusicMp3Ru(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'musicmp3.ru', 'cookie': 'musicmp3.ru.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://musicmp3.ru/'
        self.DEFAULT_ICON_URL = 'http://www.darmowe-na-telefon.pl/uploads/tapeta_240x320_muzyka_23.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.jscode = []

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getMoreItem(self, cUrl, data):
        moreItem = {}
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'show_more'), ('</div', '>'))[1]
        ajaxData = clean_html(self.cm.ph.getSearchGroups(data, '''\sdata\-infiniteAjaxScroll=['"]([^'^"]+?)['"]''')[0])
        queryData = clean_html(self.cm.ph.getSearchGroups(data, '''\sdata\-query=['"]([^'^"]+?)['"]''')[0])
        try:
            data = byteify(json.loads(ajaxData))
            moreItem['params'] = data
            moreItem['query'] = queryData
            moreItem['next'] = self.getFullUrl(data['url'] + '?' + queryData + '&page={0}', cUrl)
            moreItem['pages'] = data.get('k', 0)
        except Exception:
            printExc()
        printDBG(moreItem)
        return moreItem

    def listMainMenu(self, cItem, nextCategory):
        printDBG("MusicMp3Ru.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        cUrl = self.cm.getBaseUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu_main'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
            type = url.split('/')[-1].split('.', 1)[0].split('_', 1)[-1]
            if type == 'genres':
                type = 'albums'
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'url': self.getFullUrl(url, cUrl), 'title': title, 'f_type': type})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubMenu(self, cItem):
        printDBG("MusicMp3Ru.listSubMenu")
        subMenuIdx = cItem.get('sub_menu_idx', 0)
        nextCategory = 'list_%s' % cItem.get('f_type', '')

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cUrl = self.cm.getBaseUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu_sub'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], cUrl)
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': url, 'title': title, 'sub_menu_idx': subMenuIdx + 1})
            if subMenuIdx > 0:
                params.update({'good_for_fav': True, 'category': nextCategory})
            self.addDir(params)

        if len(self.currList):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('--All--')})
            self.currList.insert(0, params)

    def _addBaseItem(self, cItem, nextCategory, item):
        params = dict(cItem)
        params.pop('f_more', None)
        params.pop('page', None)
        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(item)
        params.update({'good_for_fav': True, 'category': nextCategory, 'url': url, 'title': title})
        self.addDir(params)

    def _getData(self, cItem):
        printDBG("MusicMp3Ru._getData")
        page = cItem.get('page', 1)
        moreItem = {}
        retData = ''
        if page == 1:
            sts, data = self.getPage(cItem['url'])
            if sts:
                retData = data
                moreItem = self.getMoreItem(data.meta['url'], data)
        else:
            moreItem = cItem.get('f_more', {})
            sts, data = self.getPage(moreItem['next'].format(page))
            if sts:
                retData = data

        return retData, moreItem

    def _addNextPage(self, cItem, moreItem):
        printDBG("MusicMp3Ru._addNextPage")
        page = cItem.get('page', 1)
        if len(self.currList) and moreItem.get('next', '') != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'f_more': moreItem, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listArtists(self, cItem, nextCategory):
        printDBG("MusicMp3Ru.listArtists")
        page = cItem.get('page', 1)
        data, moreItem = self._getData(cItem)
        if page == 1:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'small_list'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            self._addBaseItem(cItem, nextCategory, item)
        self._addNextPage(cItem, moreItem)

    def listAlbums(self, cItem, nextCategory):
        printDBG("MusicMp3Ru.listAlbums cItem[%s]" % cItem)
        page = cItem.get('page', 1)
        data, moreItem = self._getData(cItem)

        if page == 1:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'content'), ('<script', '>'))[1]
        data = re.compile('''<div[^>]+?['"]album_report['"][^>]*?>''').split(data)
        if len(data):
            del data[0]
        for item in data:
            if 'album_report' not in item:
                continue

            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h5', '</h5>')[1])

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', 'album_report_'), ('</div', '>'))
            for it in tmp:
                t = self.cleanHtmlStr(it).replace(' , ', ', ')
                if t == '':
                    continue
                if 'second_line' in it:
                    title += ' - ' + t
                else:
                    desc.append(t)

            descTab = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>')
            for it in item:
                t = self.cleanHtmlStr(it)
                if t == '':
                    continue
                if '_name' in it:
                    title = t
                else:
                    descTab.append(t)
            desc.append(' | '.join(descTab))
            params = dict(cItem)
            params.pop('f_more', None)
            params.pop('page', None)
            params.update({'good_for_fav': True, 'category': nextCategory, 'url': url, 'title': title, 'desc': '[/br]'.join(desc), 'icon': icon})
            self.addDir(params)
        self._addNextPage(cItem, moreItem)

    def listSongsItems(self, cItem):
        printDBG("MusicMp3Ru.listSongsItems [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<table', '>', 'tracklist'), ('</table', '>'))[1]
        basePlaybackUrl = self.cm.ph.getSearchGroups(tmp, '''\sdata\-url=['"]([^'^"]+?)['"]''')[0]

        data = self.cm.ph.getDataBeetwenMarkers(data, '<tbody', '</tbody>')[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<tr', '>', 'song'), ('</tr', '>'))
        for item in data:
            title = ''
            rel = self.cm.ph.getSearchGroups(item, '''\srel=['"]([^'^"]+?)['"]''')[0]
            id = self.cm.ph.getSearchGroups(item, '''\sid=['"]([^'^"]+?)['"]''')[0]
            desc = []
            item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<td', '>'), ('</td', '>'))
            for it in item:
                t = self.cleanHtmlStr(it)
                if t == '':
                    continue
                if '_name' in it:
                    title = t
                else:
                    desc.append(t)
            desc = ' | '.join(desc)
            if title == '':
                continue
            params = {'good_for_fav': True, 'title': title, 'url': basePlaybackUrl, 'rel': rel, 'id': id, 'desc': desc}
            self.addAudio(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MusicMp3Ru.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search.html?text=%s&all=%s' % (urllib.quote(searchPattern), searchType))
        if searchType == 'songs':
            self.listSongsItems(cItem)
        elif searchType == 'albums':
            self.listAlbums(cItem, 'list_songs')
        elif searchType == 'artists':
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'content'), ('</div', '>'))[1]
            data = re.compile('''<li[^>]+?artist_preview[^>]*?>''').split(data)
            if len(data):
                del data[0]
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
                desc = []
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<dl', '</dl>')
                for it in item:
                    header = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(it, '<dt', '</dt>')[1])
                    it = self.cm.ph.getAllItemsBeetwenMarkers(it, '<li', '</li>')
                    descTab = []
                    for t in it:
                        t = self.cleanHtmlStr(t)
                        if t != '':
                            descTab.append(t)
                    desc.append('%s: %s' % (header, ', '.join(descTab)))
                params = dict(cItem)
                params.pop('f_more', None)
                params.pop('page', None)
                params.update({'good_for_fav': True, 'category': 'list_albums', 'url': url, 'title': title, 'desc': '[/br]'.join(desc)})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("MusicMp3Ru.getLinksForVideo [%s]" % cItem)

        if self.jscode == []:
            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return []
            scriptUrl = self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]*?/scripts\.js[^'^"]*?)['"]''')[0]
            if scriptUrl == '':
                return []
            sts, data = self.getPage(self.getFullUrl(scriptUrl))
            if not sts:
                return []
            jscode = ['var iptvObj={%s};' % self.cm.ph.getDataBeetwenMarkers(data, 'boo:', '},')[1]]
            jscode.append('var iptvArg="%s";')
            jscode.append('print(iptvObj["boo"](iptvArg));')
            self.jscode = jscode

        playbackUrl = cItem['url']
        rel = cItem['rel']
        id = cItem['id']
        cookieVal = self.cm.getCookieItem(self.COOKIE_FILE, 'SessionId')

        jscode = list(self.jscode)
        jscode[1] = jscode[1] % (id[5:] + cookieVal[8:])
        jscode = '\n'.join(jscode)
        ret = js_execute(jscode)
        if ret['sts'] and 0 == ret['code']:
            url = playbackUrl + '/' + ret['data'].strip() + "/" + rel
            return [{'name': 'direct', 'url': strwithmeta(url, {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Cookie': 'SessionId=%s;' % cookieVal}), 'need_resolve': 0}]
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
            self.listMainMenu({'name': 'category'}, 'sub_menu')
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem)
        elif category == 'list_artists':
            self.listArtists(self.currItem, 'list_albums')
        elif category == 'list_albums':
            self.listAlbums(self.currItem, 'list_songs')
        elif category == 'list_songs':
            self.listSongsItems(self.currItem)
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
        CHostBase.__init__(self, MusicMp3Ru(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("SONGS"), "songs"))
        searchTypesOptions.append((_("ALBUMS"), "albums"))
        searchTypesOptions.append((_("ARTISTS"), "artists"))
        return searchTypesOptions
