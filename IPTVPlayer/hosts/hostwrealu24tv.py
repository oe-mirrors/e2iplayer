# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################

def gettytul():
    return 'https://wrealu24.tv/'

class WRealu24TV(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'wrealu24.tv', 'cookie':'wrealu24.tv.cookie'})
        self.DEFAULT_ICON_URL = 'https://wrealu24.tv/images/screen_stream2.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://wrealu24.tv/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'})
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def listMainMenu(self, cItem):
        printDBG("WRealu24TV.listMainMenu")
        
        MAIN_CAT_TAB = [{'category':'list_items', 'title': _('Main'), 'url':self.getMainUrl()}, 
                        {'category':'list_items', 'title': _('Videos'), 'url':self.getFullUrl('/filmy')}, 
                       ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem):
        url = cItem['url']
        
        page = cItem.get('page', 1)
        if page > 1:
            url += '/%s' % page
        
        sts, data = self.getPage(url)
        if not sts:
            return
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'pagination'), ('</nav', '>'))[1]
        printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ " + nextPage)
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''href=['"][^'^"]+?/(%s)[^0-9]''' % (page + 1))[0]
        if nextPage != '':
            nextPage = True
        else:
            nextPage = False
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>',), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if '/na-zywo/' not in url and '/film/' not in url:
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'title'), ('</div', '>'))[1])
            if title == '':
                title = self.cleanHtmlStr(item)
            if title == '':
                title = self.cleanHtmlStr(url.split('/')[-1].replace('-', ' '))
            if title == '':
                continue
            desc = []
            for marker in ['released', 'views', 'length']:
                t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', marker), ('</div', '>'))[1])
                desc.append(t)
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':' | '.join(desc)})
            self.addVideo(params)
        
        if nextPage:
            params = dict(cItem)
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'page':page + 1})
            self.addDir(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("WRealu24TV.getLinksForVideo [%s]" % cItem)
        retTab = []
        hlsTab = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        data = re.sub("<!--[\s\S]*?-->", "", data)
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>')[1]
        if 'document.write(' in data:
            jscode = ['var document = {};document.write=function(txt){print(txt);}']
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
            for item in tmp:
                jscode.append(item)
            jscode = '\n'.join(jscode)
            ret = js_execute(jscode)
            if ret['sts'] and 0 == ret['code']:
                data = ret['data'].strip()
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>')
        printDBG(data)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            type = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''')[0].lower()
            label = self.cm.ph.getSearchGroups(item, '''label=['"]([^'^"]+?)['"]''')[0]
            res = self.cm.ph.getSearchGroups(item, '''res=['"]([^'^"]+?)['"]''')[0]
            if label == '':
                label = res
            
            if 'mp4' in type:
                url = self.up.decorateUrl(url, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT, 'Referer':cItem['url']})
                retTab.append({'name':label, 'url':url, 'res':res, 'need_resolve':0})
            elif 'mpegurl' in type:
                url = self.up.decorateUrl(url, {'iptv_proto':'m3u8', 'Origin':self.up.getDomain(cItem['url'], False), 'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT, 'Referer':cItem['url']}) 
                hlsTab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
            else:
                printDBG("Unknown source: [%s]" % item)
        
        if 1 < len(retTab):
            def __getLinkQuality(itemLink):
                try:
                    return int(itemLink['res'])
                except Exception:
                    return 0
            oneLink = CSelOneLink(retTab, __getLinkQuality, 999999999)
            retTab = oneLink.getSortedLinks()
        
        retTab.extend(hlsTab)
        return retTab
        
    def getArticleContent(self, cItem, data=None):
        printDBG("WRealu24TV.getArticleContent [%s]" % cItem)
        
        
        if self.up.getDomain(cItem['url']) not in self.up.getDomain(self.getMainUrl()):
            return []
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        
        otherInfo = {}
        retTab = []
        desc = []
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'chat_round'), ('<div', '>', 'modal-dialog'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''poster=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'chat-video-title'), ('</div', '>'), False)[1])
        released = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'chat-video-date'), ('</div', '>'), False)[1])
        if released != '':
            otherInfo['released'] = released
        
        data = re.compile('<div[^>]+?odswiezchat[^>]+?>').split(data, 1)[-1]
        data = re.compile('<div[^>]+?chat-comment-block[^>]+?>').split(data)
        if len(data):
            del data[0]
        for item in data:
            author = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'chat-comment-author'), ('</div', '>'), False)[1])
            date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'chat-comment-content-data'), ('</div', '>'), False)[1])
            text = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'chat-comment-content"'), ('</div', '>'), False)[1])
            desc.append('%s[/br]%s[/br]%s[/br]' % (author, date, text))
            printDBG("============================================================================")
            printDBG('%s\n%s\n%s\n' % (author, date, text))
        
        desc = '------------------------------------------------------------------------------[/br]'.join(desc)
        
        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        
        return [{'title':self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
    
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
            self.listMainMenu({'name':'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WRealu24TV(), False, [])
    
    
    
