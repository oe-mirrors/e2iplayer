# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, formatBytes, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
import urllib
from datetime import  datetime, timedelta
###################################################
###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://redbull.tv/'

class Redbull(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'redbull.tv', 'cookie':'redbull.tv.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header':self.HTTP_HEADER}
        self.REDBULL_API = "https://appletv.redbull.tv/" 
        self.MAIN_URL   = 'http://redbull.tv/'
        self.DEFAULT_ICON_URL = 'https://www.redbull.com/v3/resources/images/appicon/android-chrome-192.png'

    def listMain(self, cItem, nextCategory):
        printDBG("Redbull.listMain")

        MAIN_CAT_TAB = [ 
                        {'category':'explore_item',       'title': _('Discover'),  'url':self.REDBULL_API + "products/discover"       },
                        {'category':'explore_item',       'title': _('TV'),        'url':self.REDBULL_API + "products/tv"             },
                        {'category':'explore_item',       'title': _('Channels'),  'url':self.REDBULL_API + "products/channels"       },
                        {'category':'explore_item',       'title': _('Calendar'),  'url':self.REDBULL_API + "products/calendar"       },
                        {'category':'search',             'title': _('Search'),    'search_item':True,},
                        {'category':'search_history',     'title': _('Search history'),            } 
                        ]

        self.listsTab(MAIN_CAT_TAB, cItem)

    def handleSection(self, cItem, nextCategory, section):
        printDBG("Redbull.handleSection")
        section = ph.STRIP_HTML_COMMENT_RE.sub("", section)

        tmp = section.split('</table>', 1)
        sTitle = self.cleanHtmlStr(tmp[0])
        if sTitle.lower() in ('linki',): #'kategorie'
            return
        sIcon = self.getFullUrl( ph.search(section, ph.IMAGE_SRC_URI_RE)[1] )

        subItems = []
        uniques = set()
        iframes = ph.findall(section, '<center>', '</iframe>')
        if iframes:
            for iframe in iframes:
                title = self.cleanHtmlStr(iframe).split('Video Platform', 1)[0].strip()
                iframe = ph.search(iframe, ph.IFRAME_SRC_URI_RE)[1]
                if iframe in uniques:
                    continue
                uniques.add(iframe)
                if not title: title = sTitle
                subItems.append(MergeDicts(cItem, {'category':nextCategory, 'title':title, 'url':iframe}))

        iframes = ph.IFRAME_SRC_URI_RE.findall(section)
        if iframes:
            for iframe in iframes:
                iframe = iframe[1]
                if iframe in uniques:
                    continue
                uniques.add(iframe)
                subItems.append(MergeDicts(cItem, {'category':nextCategory, 'title':sTitle, 'url':iframe}))
        section = ph.findall(section, ('<a', '>', ph.check(ph.any, ('articles.php', 'readarticle.php'))), '</a>')
        for item in section:
            url = self.getFullUrl( ph.search(item, ph.A_HREF_URI_RE)[1] )
            icon = self.getFullUrl( ph.search(item, self.reImgObj)[1] )
            title = self.cleanHtmlStr(item)
            if not title: 
                title = icon.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                #title = self.titlesMap.get(title, title.upper())
            subItems.append(MergeDicts(cItem, {'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon}))

        if len(subItems) > 1:
            self.addDir(MergeDicts(cItem, {'category':'sub_items', 'title':sTitle, 'icon':sIcon, 'sub_items':subItems}))
        elif len(subItems) == 1:
            params = subItems[0]
            params.update({'title':sTitle})
            self.addDir(params)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace('&amp;', '&'), currUrl)

    def getInfo(self, item):
        desc = ''
        icon = self.getFullIconUrl(ph.search(item, '''src720=['"]([^'^"]+?)['"]''')[0])
        url = self.getFullUrl(ph.search(item, '''loadPage\(['"]([^'^"]+?)['"]''')[0])
        if url:
            content_type = ph.search(url, '''appletv.redbull.tv/(.*?)[\?/]''')[0]

        title = self.cleanHtmlStr(ph.search(item, '''<title>([^>]+?)</title>''')[0])
        title2 = self.cleanHtmlStr(ph.search(item, '''<label>([^>]+?)</label>''')[0])
        if len(title2)>len(title):
            title = title2
        
        title3 = self.cleanHtmlStr(ph.search(item, '''<label2>([^>]+?)</label2>''')[0])
        if title3:
            if title:
                title = title + "  " + title3
            else:
                title = title3
        if not title: 
            title = self.cleanHtmlStr(ph.search(item, '''accessibilityLabel=['"]([^'^"]+?)['"]''')[0])
        if not title:
            title = self.cleanHtmlStr(ph.search(item, '''Label=['"]([^'^"]+?)['"]''')[0])

        summary = self.cleanHtmlStr(ph.search(item, '''<summary>([^>]+?)</summary>''')[0])
        if summary:
            desc = summary
            
        subtitle = self.cleanHtmlStr(ph.search(item, '''<subtitle>([^>]+?)</subtitle>''')[0])
        if subtitle:
            if desc:
                desc = subtitle + "\n" + desc
            else:
                desc = subtitle
                
        time = self.cleanHtmlStr(ph.search(item, '''Duration: ([^'^"]+?)<''')[0])
        if time:
            desc = time + "\n" + desc 
        
        timestamp = ph.search(item, '''<rightLabel>([^>]+?)</rightLabel>''')[0]
        
        if timestamp.isdigit():
            v_date = datetime.fromtimestamp(int(timestamp)).strftime("%d/%m/%Y, %H:%M")
            if desc:
                desc = _("Live at: ") + v_date + '\n' + desc
            else:
                desc = _("Live at: ") + v_date
        else:
            if timestamp:
                if desc:
                    desc = timestamp + '\n' + desc
                else:
                    desc = timestamp
                
        params = {'title':title, 'icon':icon, 'desc': desc, 'url':url, 'content_type': content_type}
        return params    
    
    def listSubItems(self, cItem):
        printDBG("Redbull.listSubItems")
        self.currList = cItem['sub_items']

    def exploreItem(self, cItem):
        printDBG("Redbull.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts: return []

        if '<mediaURL>' in data: 
            icon = self.getFullIconUrl(ph.search(data, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(data, '''loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(data, '''<label2>([^>]+?)</label2>''')[0])
            if not title: 
                title = self.cleanHtmlStr(ph.search(data, '''<title>([^>]+?)</title>''')[0])
            params = {'title':title, 'icon':icon, 'desc':'', 'url': cItem['url']}
            self.addVideo(params)

        posters=[]
        data3 = ph.findall(data, '<showcasePoster', '</showcasePoster>')
        for item in data3:
            params = self.getInfo(item)
            posters.append(params)
            
        if len(posters):
            self.addDir({'title': _('Showcase'), 'icon': self.DEFAULT_ICON_URL, 'category': 'video_collection', 'sub_items': posters})
        
        data2 = re.findall("(<collectionDivider.*?</collectionDivider>.*?<grid.*?</grid>)",data)
        
        if not len(data2):
            data2 = re.findall("(<collectionDivider.*?</collectionDivider>.*?<collectionDivider.*?</collectionDivider>)",data)
        
        for item2 in data2:
            #printDBG("------------------------------------")
            if ('<shelf' in item2) or ('<grid' in item2):
                posters=[]
                poster_title = self.cleanHtmlStr(ph.search(item2, '''<title>([^>]+?)</title>''')[0])
                data3 = ph.findall(item2, '<sixteenByNinePoster', '</sixteenByNinePoster>')
                for item in data3:
                    params=self.getInfo(item)
                    posters.append(params)
                
                data3 = ph.findall(item2, '<moviePoster', '</moviePoster>')
                for item in data3:
                    params=self.getInfo(item)
                    posters.append(params)
                
                if len(posters):
                    self.addDir({'title': poster_title, 'icon': self.DEFAULT_ICON_URL, 'category': 'video_collection', 'sub_items': posters})
 
        data2 = ph.findall(data, '<centerShelf>', '</centerShelf>')
        for d in data2:
            data3 = ph.findall(d, '<actionButton', '</actionButton>')
            for item in data3:
                params = self.getInfo(item)

                if params['content_type'] in ['products','collection']:
                    params['icon'] = cItem['icon']
                    params['category'] = 'explore_item'
                    self.addDir(params)
                elif params['content_type'] in ['content','page_stream']:
                    params['icon'] = cItem['icon'] 
                    self.addVideo (params)
                else:
                    printDBG("Content Type unknown: %s " % params['content_type'])
        
        data2 = ph.findall(data, '<bottomShelf>', '</bottomShelf>')
        for d in data2:
            posters=[]
            data3 = ph.findall(d, '<sixteenByNinePoster', '</sixteenByNinePoster>')
            
            for item in data3:
                params = self.getInfo(item)
                posters.append(params)
            
            if len(posters):
                self.addDir({'title': 'Related', 'icon': self.DEFAULT_ICON_URL, 'category': 'video_collection', 'sub_items': posters})

        
        data2 = ph.findall(data, '<twoLine', '</twoLine')
        for item in data2:
            params = self.getInfo(item)
            self.addVideo(params)
        
    def listVideoItems(self, cItem):
        printDBG("Redbull.listVideoItems")
        videos = cItem['sub_items']
        
        for v in videos:
            content_type = v.get('content_type','')

            if content_type in ['products','collection']:
                v['category'] = 'explore_item'
                self.addDir(v)
            elif content_type in ['content','page_stream']:
                self.addVideo (v)
            else:
                printDBG("Content Type unknown: %s " % content_type)
            
    def listSearchResult(self, cItem, searchPattern, searchType):

        url = self.REDBULL_API + "search?q=%s" % urllib.quote_plus(searchPattern)
        cItem = MergeDicts(cItem, {'category':'list_search', 'url':url})
        self.listSearchItems(cItem)

    def listSearchItems(self, cItem):
        printDBG("Redbull.listSearchItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        #printDBG("hostredbull.listSearchItems |%s|" % data)

        data2 = ph.findall(data, '<twoLine', '</twoLine')
        for item in data2:
            params = self.getInfo(item)

            if params['content_type'] in ['products','collection']:
                params['category'] = 'explore_item'
                #printDBG(str(params))
                self.addDir(params)
                
            elif params['content_type'] in ['content','page_stream']:
                #printDBG(str(params))
                self.addVideo (params)
            else:
                printDBG("Content Type unknown: %s " % params['content_type'])

    def getLinksForVideo(self, cItem):
        printDBG("Redbull.getLinksForVideo %s" % cItem['url'])
        urlsTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return []
        #printDBG("Redbull.getLinksForVideo.data |%s|" % data)
        videoUrl = ph.search(data, '''<mediaURL>([^"]+?)<''')[0]
        if videoUrl:
            urlsTab.extend(getDirectM3U8Playlist(videoUrl, checkExt=True, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999)) 
        else: 
            url = self.getFullUrl(ph.search(data, '''loadPage\(['"]([^'^"]+?)['"]''')[0])
            sts, data = self.getPage(url)
            if not sts: 
                return []
            printDBG("hostredbull.getLinksForVideo.data |%s|" % data)
            videoUrl = ph.search(data, '''<mediaURL>([^"]+?)<''')[0]
            if videoUrl:
                urlsTab.extend(getDirectM3U8Playlist(videoUrl, checkExt=True, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999)) 
        
        return urlsTab


    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: ||| name[%s], category[%s] " % (name, category) )
        self.currList = []

        #MAIN MENU
        if name == None:
            self.listMain({'name':'category', 'type':'category'}, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'video_collection':
            self.listVideoItems(self.currItem)
            
        #SEARCH
        elif category == 'list_search':
            self.listSearchItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        
        #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Redbull(), True, [])

