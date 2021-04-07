# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
###################################################

###################################################
# FOREIGN import
###################################################

###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################


def gettytul():
    return 'https://fullmatchtv.com/'


class Fullmatchtv(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'fullmatchtv.org', 'cookie': 'fullmatchtv.cookie'})
        
        self.DEFAULT_ICON_URL = 'https://pbs.twimg.com/profile_images/683367328248164352/Ivn9ly9e_400x400.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html'}
        self.MAIN_URL = 'https://fullmatchtv.com/'
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.login = ''
        self.password = ''
        self.categoryId = ''
        self.maxPage = ''

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        return self.cm.getPage(url, addParams, post_data)
        
    def listMainMenu(self, cItem):
        printDBG("fullmatchtv.listMainMenu")
        sts, data = self.getPage(self.MAIN_URL)
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'td-mobile-content'), ('</div', '>'))[1]
            printDBG("fullmatchtv.listMainMenu data[%s]" % data)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                nextCategory = ''
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if 'category' not in url:
                    url = url.replace('.com', '.com/category')
                title = self.cleanHtmlStr(item)
                if url == '' or title == 'Home':
                    continue
                nextCategory = 'list_items'
                printDBG(">>>>>>>>>>>>>>>>> title[%s] url[%s]" % (title, url))
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                self.addDir(params)
    
    def listItems(self, cItem):
        printDBG("fullmatchtv.listItems")

        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        if page == 1:
            data = self.cm.ph.getDataBeetwenNodes(data, ('jQuery(window)', '{'), '});')[1]
            self.categoryId = self.cm.ph.getSearchGroups(data, '''['"]category_id['"]\s*?:?\s*?([0-9]+?)[^0-9]''')[0]
            data = self.cm.ph.getDataBeetwenNodes(data, ('else', '{'), '}')[1]
            self.maxPage = self.cm.ph.getSearchGroups(data, '''max_num_pages\s=\s([0-9]+?);''')[0]
            printDBG("fullmatchtv.listItems categoryId[%s] maxPage[%s]" % (self.categoryId, self.maxPage))

        post_data = {'action': 'td_ajax_loop', 'loopState[moduleId]': '1', 'loopState[currentPage]': page, 'loopState[atts][category_id]': self.categoryId}
        sts, data = self.getPage('https://fullmatchtv.com/wp-admin/admin-ajax.php?td_theme_name=Newspaper&v=10.1', self.defaultParams, post_data)
        if not sts:
            return
        data = data.replace('\\', '')
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'td-module-thumb'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            title = self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^"^']+?)['"]''')[0].replace('&#8211;', '-')
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0])
            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon}
            self.addVideo(params)

        if self.maxPage != '':
            page += 1
            if page < int(self.maxPage):
                params = dict(cItem)
                params.update({'title': _("Next page"), 'url': cItem['url'], 'page': page})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("fullmatchtv.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'td-post-content'), ('</p', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'))
        if len(tmp):
            for item in tmp:
                url = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
                if url.startswith('//'):
                    url = 'http:' + url
                if 1 != self.up.checkHostSupport(url):
                    continue
                name = self.up.getDomain(url)
                urlTab.append({'name': name, 'url': self.getFullUrl(url), 'need_resolve': 1})

        return urlTab
    
    def getVideoLinks(self, videoUrl):
        printDBG("fullmatchtv.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if 1 == self.up.checkHostSupport(videoUrl): 
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Fullmatchtv(), True, [])
    
