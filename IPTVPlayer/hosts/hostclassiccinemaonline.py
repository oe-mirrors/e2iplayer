# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://classiccinemaonline.com/'


class ClassicCinemaOnline(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'classiccinemaonline.com', 'cookie': 'classiccinemaonline.com.cookie'})
        self.DEFAULT_ICON_URL = 'http://www.classiccinemaonline.com/templates/rt_metropolis/images/logo/dark/logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.classiccinemaonline.com/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_movies_cats', 'title': 'Movie Billboards', 'url': self.getMainUrl()},
                             {'category': 'list_items', 'title': 'Serials', 'url': self.getFullUrl('/serials')},
                             {'category': 'list_items', 'title': 'Silent Films', 'url': self.getFullUrl('/silent-films')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]

    def getMaxDisplayItems(self):
        return 10

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem, nextCategory):
        printDBG("ClassicCinemaOnline.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesCats(self, cItem, nextCategory):
        printDBG("ClassicCinemaOnline.listCats")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = []
        data = self.cm.ph.getDataBeetwenNodes(data, ('<a', '</a>', 'javascript:void(0);'), ('<a', '</a>', '/serials'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            # check if this is sub-category
            isSubCategory = False
            for u in tmp:
                if u in url:
                    isSubCategory = True
                    break
            if isSubCategory:
                continue

            tmp.append(url)
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': self.getFullUrl(url)})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("ClassicCinemaOnline.listItems [%s]" % cItem)
        page = cItem.get('page', 0)
        post_data = None
        if page == 0:
            post_data = {'limit': self.getMaxDisplayItems(), 'filter_order': '', 'filter_order_Dir': '', 'limitstart': ''}

        url = cItem['url']

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<a', '>', 'Next'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&'))

        # list sub-categories
        items = self.cm.ph.getDataBeetwenMarkers(data, 'Subcategories', '</ul>')[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(items, '<li', '</li>')
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            tmp = item.split('</h3>', 1)
            title = self.cleanHtmlStr(tmp[0])
            desc = self.cleanHtmlStr(tmp[-1])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': self.getFullUrl(url), 'desc': desc})
            self.addDir(params)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<tr', '>', 'cat-list-row'), ('</tr', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            tmp = item.split('</td>', 1)
            title = self.cleanHtmlStr(tmp[0])
            desc = 'Hits: %s' % self.cleanHtmlStr(tmp[-1])
            icon = url + '?fake=need_resolve.jpeg'
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': self.getFullUrl(url), 'icon': icon, 'desc': desc})
            self.addVideo(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ClassicCinemaOnline.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 0)
        if page == 0:
            url = self.getFullUrl('/component/search/?searchword=%s&ordering=newest&searchphrase=all&limit=%s' % (urllib.quote(searchPattern), self.getMaxDisplayItems()))
        else:
            url = cItem['url']

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<a', '>', 'Next'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&'))

        data = self.cm.ph.getDataBeetwenMarkers(data, '<dl', '</dl>')[1]
        data = re.compile('<dt[^>]+?result-title[^>]+?>').split(data)
        if len(data):
            del data[0]
        for item in data:
            tmp = item.split('</dt>', 1)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[0], '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp[0], '<a', '</a>')[1])
            desc = self.cleanHtmlStr(tmp[-1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url, 'desc': desc})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("ClassicCinemaOnline.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        if 'Display #' in data:
            cItem = dict(cItem)
            cItem['category'] = nextCategory
            self.listItems(cItem, nextCategory)
        else:
            params = dict(cItem)
            params['icon'] = params['url'] + '?fake=need_resolve.jpeg'
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("ClassicCinemaOnline.getLinksForVideo [%s]" % cItem)

        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        reObj = re.compile('''['"]([^"^']+?\.mp4(:?\?[^"^']+?)?)['"]''', re.IGNORECASE)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<center>', '</center>')
        for item in data:
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if videoUrl == '':
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<embed[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if videoUrl == '':
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<object[^>]+?value=['"]([^"^']+?)['"]''', 1, True)[0])
            if videoUrl.split('?', 1)[0].endswith('.swf'):
                baseUrl = self.cm.ph.getSearchGroups(item, '''['"]?baseUrl['"]?\s*:\s*['"](https?://[^"^']+?)['"]''', 1, True)[0]
                item = reObj.findall(item)
                for url in item:
                    url = url[0]
                    if url != '' and not self.cm.isValidUrl(url):
                        url = baseUrl + url
                    if self.cm.isValidUrl(url):
                        retTab.append({'name': 'mp4', 'url': url, 'need_resolve': 0})

            if self.cm.isValidUrl(videoUrl):
                retTab.extend(self.up.getVideoLinkExt(videoUrl))

        return retTab

    def getArticleContent(self, cItem):
        printDBG("ClassicCinemaOnline.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return retTab

        imdbId = self.cm.ph.getSearchGroups(data, 'imdb\.com/title/tt([0-9]+?)[^0-9$]')[0]
        if imdbId == '':
            img_url = self.cm.ph.getDataBeetwenNodes(data, ('<center>', '</center>', '<img'), ('<', '>'))[1]
            img_url = self.getFullUrl(self.cm.ph.getSearchGroups(img_url, '<img[^>]+?src="([^"]+?\.(:?jpe?g|png)(:?\?[^"]+?)?)"')[0])
            return [{'title': cItem['title'], 'text': cItem.get('desc', ''), 'images':[{'title': '', 'url': img_url}], 'other_info': {}}]

        url = 'http://www.imdb.com/title/tt{0}/'.format(imdbId)
        sts, data = self.getPage(url)
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<meta property=['"]?og\:title['"]?[^>]+?content=['"]([^"^']+?)['"]''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="summary_text"', '</div>')[1])
        if desc == '':
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<meta property=['"]?og\:description['"]?[^>]+?content=['"]([^"^']+?)['"]''')[0])
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<meta property=['"]?og\:image['"]?[^>]+?content=['"]([^"^']+?)['"]''')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            title = cItem.get('desc', '')

        descData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h4 class="inline"', '</div>')
        descKeyMap = {"also known as": "alternate_title",
                      "production co": "production",
                      "director": "director",
                      "directors": "directors",
                      "creators": "creators",
                      "creator": "creator",
                      "Stars": "stars",
                      "genres": "genres",
                      "country": "country",
                      "language": "language",
                      "release date": "released",
                      "runtime": "duration"}

        otherInfo = {}
        for item in descData:
            item = item.split('</h4>')
            printDBG(item)
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').strip().lower()
            if key not in descKeyMap:
                continue
            val = self.cleanHtmlStr(item[1]).split('See more')[0]
            otherInfo[descKeyMap[key]] = val
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="ratingValue">', '</div>')[1]
        otherInfo['imdb_rating'] = self.cm.ph.getSearchGroups(data, '''title=['"]([^"^']+?)['"]''')[0]

        return [{'title': title, 'text': desc, 'images': [{'title': '', 'url': icon}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_movies_cats':
            self.listMoviesCats(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_items')
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
        CHostBase.__init__(self, ClassicCinemaOnline(), True, [])

    def withArticleContent(self, cItem):
        printDBG(cItem)
        if cItem['type'] == 'video':
            return True
        return False
