# -*- coding: utf-8 -*-

#
#
# @Codermik release, based on @Samsamsam's E2iPlayer public.
# Released with kind permission of Samsamsam.
# All code developed by Samsamsam is the property of the Samsamsam and the E2iPlayer project,  
# all other work is ï¿½ E2iStream Team, aka Codermik.  TSiPlayer is ï¿½ Rgysoft, his group can be
# found here:  https://www.facebook.com/E2TSIPlayer/
#
# https://www.facebook.com/e2iStream/
#
#

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph

import re, urllib

def gettytul():
    return 'https://pregledaj.net/'


class PregledajNET(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'pregledaj.net', 'cookie': 'pregledaj.net.cookie'})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://lh4.googleusercontent.com/-JxZusTTdS-s/UZ_e9TgnwAI/AAAAAAAAAB4/B2r93QoDt8g/w506-h750/photo.jpg'
        self.MAIN_URL = 'https://www.pregledaj.net/'

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HTTP_HEADER['User-Agent']}
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def getFullIconUrl(self, url, cUrl=None):
        url = self.getFullUrl(url, cUrl)
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, domain=self.cm.getBaseUrl(url, domainOnly=True))
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.HTTP_HEADER['User-Agent']})

    def listMainMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG('CrtankoCom.listMainMenu')
        sts, data = self.cm.getPage(self.getMainUrl())
        if sts:
            self.setMainUrl(self.cm.meta['url'])
            data = ph.find(data, ('<nav', '>', 'navmenu-default'), '</nav>', flags=0)[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][1]
                    params['c_tree']['list'].insert(0, {'dat': cTree['dat']})
                    params['category'] = 'list_categories'
                    self.listCategories(params, nextCategory1, nextCategory2)
                except Exception:
                    printExc()

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True}, {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory1, nextCategory2):
        printDBG('CrtankoCom.listCategories')
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = ph.clean_html(ph.find(item['dat'], '<a', '</a>')[1])
                url = self.getFullUrl(ph.search(item['dat'], ph.A)[1])
                if url.endswith('browse.html'):
                    self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'category': nextCategory2, 'title': title, 'url': url}))
                elif 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'category': nextCategory1, 'title': title, 'url': url}))
                elif len(item['list']) == 1 and title != '':
                    self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url}))

        except Exception:
            printExc()

    def listSubCategories(self, cItem, nextCategory):
        printDBG('CrtankoCom.listSubCategories')
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        data = ph.find(data, ('<ul', '>', 'browse-categories'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for item in data:
            title = ph.clean_html(item)
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            icon = self.getFullIconUrl(ph.search(item, ph.IMG)[1])
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon}))

    def listSubCategory(self, cItem, nextCategory):
        printDBG('CrtankoCom.listSubCategory')
        sts, pageData = self.cm.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        data = ph.find(pageData, ('<div', '>', 'category-subcats'), '</div>', flags=0)[1]
        data = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for item in data:
            title = ph.clean_html(item)
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}))

        if not self.currList:
            self.listItems(MergeDicts(cItem, {'category': nextCategory}), pageData)

    def listSort(self, cItem, nextCategory, pageData=None):
        printDBG('CrtankoCom.listSort')
        if not pageData:
            sts, pageData = self.cm.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(self.cm.meta['url'])
        data = ph.find(pageData, ('<div', '>', 'group-sort'), '</div>', flags=0)[1]
        data = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for item in data:
            title = ph.clean_html(item)
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            if not url:
                continue
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url}))

        if not self.currList:
            self.listItems(MergeDicts(cItem, {'category': nextCategory}), pageData)

    def listItems(self, cItem, data=None):
        printDBG('PregledajNET.listItems')
        page = cItem.get('page', 1)
        if not data:
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(self.cm.meta['url'])
        baseDesc = ph.clean_html(ph.find(data, ('<div', '>', 'description'), '</div>', flags=0)[1])
        nextPage = ph.find(data, ('<ul', '>', 'pagination'), '</ul>', flags=0)[1]
        nextPage = ph.find(nextPage, '<a', '>%s<' % (page + 1))[1]
        nextPage = self.getFullUrl(ph.search(nextPage, ph.A)[1])
        data = ph.find(data, ('<ul', '>', 'browse-video'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for item in data:
            tmp = ph.find(item, ('<h3', '>'), '</h3>', flags=0)[1]
            url = self.getFullUrl(ph.search(tmp, ph.A)[1])
            if not url:
                continue
            title = ph.clean_html(tmp)
            tmp = ph.find(item, '<img', '>')[1]
            icon = self.getFullIconUrl(ph.getattr(tmp, 'data-echo'))
            if not icon:
                icon = self.getFullIconUrl(ph.search(tmp, ph.IMG)[1])
            desc = []
            tmp = ph.rfindall(item, '</div>', ('<div', '>'), flags=0)
            for t in tmp:
                t = ph.clean_html(t)
                if t:
                    desc.append(t)

            self.addVideo(MergeDicts(cItem, {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': (' | ').join(desc) + '[/br]' + baseDesc}))

        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        url = self.getFullUrl('/search.php?keywords=' + urllib.quote_plus(searchPattern))
        self.listItems({'name': 'category', 'category': 'list_items', 'url': url})

    def getLinksForVideo(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        linksTab = []
        data = ph.IFRAME.findall(data)
        for item in data:
            videoUrl = self.getFullUrl(item[1])
            if 1 == self.up.checkHostSupport(videoUrl):
                return self.up.getVideoLinkExt(videoUrl)

        return linksTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('handleService: ||| name[%s], category[%s] ' % (name, category))
        self.currList = []
        if name == None:
            self.listMainMenu({'name': 'category', 'url': self.MAIN_URL}, 'list_sort', 'list_subcategories')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_sort', 'list_subcategories')
        elif category == 'list_subcategories':
            self.listSubCategories(self.currItem, 'list_subcategory')
        elif category == 'list_subcategory':
            self.listSubCategory(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'search':
            self.listSearchResult(MergeDicts(self.currItem, {'search_item': False, 'name': 'category'}), searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()            

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PregledajNET(), True, [])

