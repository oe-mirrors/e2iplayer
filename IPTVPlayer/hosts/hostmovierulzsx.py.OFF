# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://movierulz.be/'


class MovieRulzSX(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'movierulz.sx', 'cookie': 'movierulz.sx.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://movierulz.be/'
        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/xplugin.video.movierulz.png.pagespeed.ic.em3U-ZIgpV.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.cacheGenresSections = []

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
        printDBG("MovieRulzSX.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', '"menu"'), ('</nav', '>'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = 'list_categories'
                    self.listCategories(params, 'list_items', 'list_genres_sections')
                except Exception:
                    printExc()
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory1, nextCategory2):
        printDBG("MovieRulzSX.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item['dat'], '<a', '</a>')[1])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if url.endswith('movies-by-genres-and-years/') or url.endswith('others-movies/'):
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory2, 'title': title, 'url': url})
                        self.addDir(params)
                elif 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory1, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listGenresSections(self, cItem, nextCategory):
        printDBG("MovieRulzSX.listGenresSections")
        self.cacheGenresSections = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</table', '>'), ('<p', '>', 'center;'))
        for section in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<p', '</p>')[1])
            tabItems = []
            section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<a', '</a>')
            for item in section:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                tabItems.append({'title': title, 'url': url})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'f_sec_idx': len(self.cacheGenresSections)})
                self.addDir(params)
                self.cacheGenresSections.append(tabItems)

        if 1 == len(self.currList):
            params = self.currList.pop()
            self.listGenreSection(params, 'list_items')

    def listGenreSection(self, cItem, nextCategory):
        printDBG("MovieRulzSX.listGenreSection")

        idx = cItem.get('f_sec_idx', 0)
        params = dict(cItem)
        params.update({'category': nextCategory})
        self.listsTab(self.cacheGenresSections[idx], params)

    def listItems(self, cItem):
        printDBG("MovieRulzSX.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'nav-older'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0])

        reObjYer = re.compile('(\([0-9]{4}\))')
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'cont_display'), ('</li', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''[\s\-]src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            try:
                title = ''.join(reObjYer.split(title)[:2])
            except Exception:
                printExc()
            desc = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addVideo(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovieRulzSX.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 1 == cItem.get('page', 1):
            cItem['category'] = 'list_items'
            cItem['url'] = self.getFullUrl('/?s=') + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("MovieRulzSX.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}
        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if url != '':
                name = self.up.getDomain(url)
                retTab.append({'name': name, 'url': url, 'need_resolve': 1})

        data = self.cm.ph.rgetDataBeetwenNodes(data, ('<', '>', 'post-nav'), ('<div', '>', 'entry-content'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href=['"](https?://[^"^']+?)['"]''')[0].replace('&amp;', '&')
            if url == '':
                continue
            name = self.cleanHtmlStr(item.split('<a', 1)[0])
            retTab.append({'name': name, 'url': url, 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("MovieRulzSX.getVideoLinks [%s]" % baseUrl)
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

        if 1 != self.up.checkHostSupport(baseUrl):
            sts, data = self.getPage(videoUrl)
            if not sts:
                return []
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'entry-content'), ('</div', '>'))[1]
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]).replace('&amp;', '&')
            if videoUrl == '':
                videoUrl = self.cm.ph.getSearchGroups(tmp, '''href=['"](https?://[^"^']+?)['"]''')[0].replace('&amp;', '&')
            if videoUrl == '':
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
                for item in tmp:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                    if 1 == self.up.checkHostSupport(url):
                        videoUrl = strwithmeta(url, {'Referer': baseUrl})

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None):
        printDBG("MovieRulzSX.getArticleContent [%s]" % cItem)

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
            self.listCategories(self.currItem, 'list_items', 'list_genres_sections')
        elif category == 'list_genres_sections':
            self.listGenresSections(self.currItem, 'list_genre_section')
        elif category == 'list_genre_section':
            self.listGenreSection(self.currItem, 'list_items')
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
        CHostBase.__init__(self, MovieRulzSX(), True, [])

    #def withArticleContent(self, cItem):
    #    return cItem.get('good_for_fav', False)
