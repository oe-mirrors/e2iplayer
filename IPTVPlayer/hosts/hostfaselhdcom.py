# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
###################################################


def gettytul():
    return 'https://faselhd.co/'


class FaselhdCOM(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'faselhd.com', 'cookie': 'faselhd.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www.faselhd.co/'
        self.DEFAULT_ICON_URL = self.getFullUrl('https://i2.wp.com/www.faselhd.com/wp-content/themes/adbreak/images/logo.png')
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if sts and 'http-equiv="refresh"' in data:
            url = ph.find(data, ('<meta', '>', 'http-equiv="refresh"'))[1]
            url = self.getFullUrl(ph.getattr(url.replace(';', ' '), 'URL'), self.cm.meta['url'])
            return self.cm.getPageCFProtection(url, addParams, post_data)
        return sts, data

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url)
        if url != '' and self.up.getDomain(url) in self.getMainUrl():
            url = 'https://i2.wp.com/' + url.split('://', 1)[-1]
        return url

    def listMainMenu(self, cItem):
        printDBG("FaselhdCOM.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'class="menu'), ('</div', '>'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = 'list_categories'
                    self.listCategories(params, 'list_items')
                except Exception:
                    printExc()

        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("FaselhdCOM.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item['dat'], '<a', '</a>')[1])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if '/promo' in url:
                    return
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

    def listItems(self, cItem, nextCategory=''):
        printDBG("FaselhdCOM.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        baseData = data

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))[0])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'one-movie'), ('</a', '>'))
        printDBG(data)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''[\s\-]src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h1', '</h1>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '':
                continue

            desc = []
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'movie-meta'), ('</div', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
            for t in tmp:
                label = ''
                if 'fa-star' in t:
                    label = _('Rating:')
                elif 'fa-eye' in t:
                    label = _('Views:')
                t = self.cleanHtmlStr(t)
                if t != '':
                    if label != '':
                        desc.append('%s %s' % (label, t))
                    else:
                        desc.append(t)

            if '/seasons/' in self.cm.meta['url'] and not cItem.get('sub_view'):
                title = '%s - %s' % (cItem['title'], title)
                self.addDir(MergeDicts(cItem, {'url': url, 'title': title, 'sub_view': True}))
            else:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
                if nextCategory == '' or cItem.get('f_list_episodes'):
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)

        if not cItem.get('sub_view'):
            data = ph.findall(baseData, ('<span', '>', 'sub-view'), '</span>')
            for item in data:
                if 'display:none' in item:
                    continue
                url = self.getFullUrl(ph.getattr(item, 'href'), self.cm.meta['url'])
                title = '%s - %s' % (cItem['title'], ph.clean_html(item))
                self.addDir(MergeDicts(cItem, {'url': url, 'title': title, 'sub_view': True}))

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("FaselhdCOM.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        url = self.cm.ph.getDataBeetwenNodes(data, ('<meta', '>', 'refresh'), ('<', '>'))[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(url, '''url=['"]([^'^"]+?)['"]''', 1, True)[0])

        if self.cm.isValidUrl(url):
            sts, tmp = self.getPage(url)
            if sts:
                data = tmp

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'movie-btns'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            if 'youtube-play' not in item:
                continue
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', 1, True)[0])
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'url': url, 'title': '%s - %s' % (cItem['title'], title)})
                self.addVideo(params)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'movies-servers'), ('<div', '>', 'container'))[1]
        if tmp != '':
            params = dict(cItem)
            self.addVideo(params)
        else:
            cItem = dict(cItem)
            cItem.update({'category': nextCategory, 'page': 1, 'f_list_episodes': True})
            if self.cm.isValidUrl(url):
                cItem['url'] = url
            self.listItems(cItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FaselhdCOM.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 1 == cItem.get('page', 1):
            cItem['category'] = 'list_items'
            cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("FaselhdCOM.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        retTab = []
        dwnTab = []

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        dwnLink = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'download_direct_link'), ('</a', '>'))[1]
        dwnLink = self.cm.ph.getSearchGroups(dwnLink, '''href=['"](https?://[^"^']+?)['"]''')[0]

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'movies-servers'), ('<script', '>'))[1]

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul', '</ul>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            marker = self.cm.ph.getSearchGroups(item, '''href=['"]#([^"^']+?)['"]''')[0]
            name = self.cleanHtmlStr(item)
            dat = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', marker), ('<iframe', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(dat, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if url == '':
                url = self.cm.ph.getSearchGroups(item, '''href\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
                tmp = url.split('embed.php?url=', 1)
                if 2 == len(tmp):
                    url = urllib.unquote(tmp[-1])
            retTab.append({'name': name, 'url': self.getFullUrl(url), 'need_resolve': 1})

        if self.cm.isValidUrl(dwnLink):
            sts, data = self.getPage(dwnLink)
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'other_servers'), ('</div', '>'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''href=['"](https?://[^"^']+?)['"]''')[0]
                if 1 != self.up.checkHostSupport(url):
                    continue
                name = self.cleanHtmlStr(item)
                dwnTab.append({'name': name, 'url': url, 'need_resolve': 1})

        retTab.extend(dwnTab)
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("FaselhdCOM.getVideoLinks [%s]" % baseUrl)
        videoUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        urlTab = self.up.getVideoLinkExt(videoUrl)
        if 0 == len(urlTab):
            sts, data = self.getPage(videoUrl)
            if not sts:
                return []

            hlsUrl = self.cm.ph.getSearchGroups(data, '''["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']''', ignoreCase=True)[0]
            printDBG("hlsUrl||||||||||||||||| " + hlsUrl)
            if hlsUrl != '':
                hlsUrl = strwithmeta(hlsUrl, {'User-Agent': self.defaultParams['header']['User-Agent'], 'Referer': baseUrl})
                urlTab = getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=999999999)

            if 0 == len(urlTab):
                data = self.cm.ph.getDataBeetwenMarkers(data, '.setup(', ')')[1]
                videoUrl = self.cm.ph.getSearchGroups(data, '''['"]?file['"]?\s*:\s*['"](https?://[^'^"]+?)['"]''')[0]
                if self.cm.isValidUrl(videoUrl):
                    videoUrl = strwithmeta(videoUrl, {'User-Agent': self.defaultParams['header']['User-Agent'], 'Referer': baseUrl})
                    urlTab.append({'name': 'direct', 'url': videoUrl})

        return urlTab

    def getArticleContent(self, cItem, data=None):
        printDBG("FaselhdCOM.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        url = self.cm.ph.getDataBeetwenNodes(data, ('<meta', '>', 'refresh'), ('<', '>'))[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(url, '''url=['"]([^'^"]+?)['"]''', 1, True)[0])

        if self.cm.isValidUrl(url):
            sts, tmp = self.getPage(url)
            if sts:
                data = tmp

        data = self.cm.ph.getDataBeetwenNodes(data, ('<header', '>'), ('<style', '>'))[1]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p', '</p>')[1])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''\ssrc=['"]([^'^"]+?)['"]''')[0])

        keysMap = {'دولة المسلسل': 'country',
                   'حالة المسلسل': 'status',
                   'اللغة': 'language',
                   'توقيت الحلقات': 'duration',
                   'الموسم': 'seasons',
                   'الحلقات': 'episodes',

                   'تصنيف الفيلم': 'genres',
                   'مستوى المشاهدة': 'age_limit',
                   'سنة الإنتاج': 'year',
                   'مدة الفيلم': 'duration',
                   'تقييم IMDB': 'imdb_rating',
                   'بطولة': 'actors',
                   'جودة الفيلم': 'quality'}
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<i', '>', 'fa-'), ('</span', '>'))
        printDBG(data)
        for item in data:
            tmp = self.cleanHtmlStr(item).split(':')
            marker = tmp[0].strip()
            value = tmp[-1].strip().replace(' , ', ', ')

            printDBG(">>>>>>>>>>>>>>>>>> marker[%s] -> value[%s]" % (marker, value))

            #marker = self.cm.ph.getSearchGroups(item, '''(\sfa\-[^'^"]+?)['"]''')[0].split('fa-')[-1]
            #printDBG(">>>>>>>>>>>>>>>>>> " + marker)
            if marker not in keysMap:
                continue
            if value == '':
                continue
            otherInfo[keysMap[marker]] = value

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
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
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'list_lists':
            self.listLists(self.currItem, 'list_items')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_items')
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
        CHostBase.__init__(self, FaselhdCOM(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('good_for_fav', False)
