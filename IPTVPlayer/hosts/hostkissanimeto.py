# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetTmpDir, CSelOneLink, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import base64
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from binascii import a2b_hex
from hashlib import sha256
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvimageselector import IPTVMultipleImageSelectorWidget
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kissanime_defaultformat = ConfigSelection(default="999999", choices=[("0", _("the worst")), ("360", "360p"), ("480", "480p"), ("720", "720p"), ("1080", "1080p"), ("999999", "the best")])
config.plugins.iptvplayer.kissanime_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                         ("proxy_1", _("Alternative proxy server (1)")),
                                                                                         ("proxy_2", _("Alternative proxy server (2)"))])

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.kissanime_defaultformat))
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kissanime_proxy))
    return optionList
###################################################

def gettytul():
    return 'http://kissanime.ru/'

class KissAnimeTo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kissanime.to', 'cookie': 'kissanimeto.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:56.0) Gecko/20100101 Firefox/56.0'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_URL = 'http://kissanime.ru/'
        self.DEFAULT_ICON_URL = "https://ausanimecons.files.wordpress.com/2015/01/kissanime-logo.jpg"
        
        self.MAIN_CAT_TAB = [{'category': 'home', 'title': _('Home'), 'url': self.getMainUrl(), },
                             {'category': 'list_cats', 'title': _('Anime list'), 'url': self.getFullUrl('AnimeList'), },
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]
        
        self.SORT_BY_TAB = [{'title': _('Sort by alphabet')},
                            {'title': _('Sort by popularity'), 'sort_by': 'MostPopular'},
                            {'title': _('Latest update'), 'sort_by': 'LatestUpdate'},
                            {'title': _('New cartoon'), 'sort_by': 'Newest'}]
        self.cacheHome = {}
        self.cache = {}
        
    def getPage(self, baseUrl, addParams={}, post_data=None):
        images = []
        errorMessages = []
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        baseUrl = self.cm.iriToUri(baseUrl)
        proxy = config.plugins.iptvplayer.kissanime_proxy.value
        printDBG(">> " + proxy)
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})
        
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': self.getFullUrl}
        while True:
            sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
            if sts and 'areyouhuman' in self.cm.meta['url'].lower():
                errorMessages = []
                formData = ''
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<form', '</form>', withMarkers=False, caseSensitive=False)
                for item in tmp:
                    if 'answerCap' in item:
                        formData = item
                        break
                
                messages = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(formData, '<p', '</p>')
                for item in tmp:
                    item = self.cleanHtmlStr(item)
                    if item != '':
                        messages.append(item)
                
                if len(messages) < 2:
                    errorMessages.append(_('Unknown captcha form! Data: "%s"') % messages)
                    break
                
                action = self.cm.ph.getSearchGroups(formData, '''action=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                if action == '':
                    action = '/'
                action = self.getFullUrl(action)
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(formData, '<input', '>', False, False)
                post_data2 = {}
                for item in tmp:
                    name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                    if name != '':
                        post_data2[name] = value
                
                header = dict(self.HTTP_HEADER)
                header['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
                params = dict(self.defaultParams)
                params.update({'maintype': 'image', 'subtypes': ['jpeg', 'jpg', 'png'], 'check_first_bytes': ['\xFF\xD8', '\xFF\xD9', '\x89\x50\x4E\x47'], 'header': header})
                
                prevMeta = self.cm.meta
                images = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(formData, '<img', '>', False, False)
                for item in tmp:
                    index = self.cm.ph.getSearchGroups(item, '''indexValue=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                    imgUrl = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
                    if index != '' and imgUrl != '':
                        filePath = GetTmpDir('.iptvplayer_captcha_picture_%s.jpg' % index)
                        rm(filePath)
                        ret = self.cm.saveWebFile(filePath, imgUrl.replace('&amp;', '&'), params)
                        if ret.get('sts'):
                            images.append({'path': filePath, 'id': index})
                            continue
                        errorMessages.append(_('Download "%s" in to "%s" failed!') % (imgUrl, filePath))
                    else:
                        errorMessages.append(_('Unknow data in the captcha item!'))
                        errorMessages.append('item: "%s"' % item)
                    break
                self.cm.meta = prevMeta
                if 0 == len(errorMessages):
                    printDBG("++++++++++++++++++++++++++++++++++")
                    printDBG('action:    %s' % action)
                    printDBG('post_data: %s' % post_data2)
                    printDBG('images:    %s' % images)
                    printDBG("++++++++++++++++++++++++++++++++++")
                    message = '\n'.join(messages[1:])
                    if ' TWO ' in message: 
                        maxSelItems = 2
                        acceptLabel = None
                    else: 
                        maxSelItems = None
                        acceptLabel = _('-- OK --')
                    retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleImageSelectorWidget, title='Captcha', message=message, message_height=100, images=images, image_width=160, image_height=160, accep_label=acceptLabel, max_sel_items=maxSelItems)
                    printDBG(retArg)
                    if retArg and len(retArg) and isinstance(retArg[0], list):
                        printDBG(retArg[0])
                        post_data2['answerCap'] = ','.join(retArg[0]) + ','
                        addParams2 = dict(addParams)
                        addParams2['header'] = dict(addParams2['header'])
                        addParams2['header']['Referer'] = prevMeta['url']
                        sts2, data2 = self.cm.getPageCFProtection(action, addParams, post_data2)
                        #printDBG("++++++++++++++++++++++++++++++++++")
                        #printDBG(data2)
                        #printDBG("++++++++++++++++++++++++++++++++++")
                        if sts2:
                            if 'areyouhuman' in self.cm.meta['url'].lower():
                                printDBG(">>> TRY AGAIN")
                                continue
                            else:
                                sts, data = sts2, data2
                    else:
                        self.cm.meta = prevMeta
            break
        
        if len(errorMessages):
            GetIPTVNotify().push('\n'.join(errorMessages), 'error', 10)
        
        #printDBG("++++++++++++++++++++++++++++++++++")
        #printDBG(data)
        #printDBG("++++++++++++++++++++++++++++++++++")
        
        for item in images:
            rm(item['path'])
        
        return sts, data
        
    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['cf_clearance'])
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def _getItems(self, data, sp='', forceIcon=''):
        printDBG("listHome._getItems")
        if '' == sp: 
            sp = "<div style='position:relative'"
        data = data.split(sp)
        if len(data):
            del data[0]
        tab = []
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=["']([^"^']+?)["']''')[0]
            if '' == url:
                continue
            title = self.cm.ph.getDataBeetwenMarkers(item, '<span class="title">', '</span>', False)[1]
            if '' == title:
                title = self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>')[1]
            if forceIcon == '':
                icon = self.cm.ph.getSearchGroups(item, '''src=["']([^"^']+?)["']''')[0]
            else:
                icon = forceIcon
            desc = self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1]
            if '' == desc:
                desc = '<' + item
            tab.append({'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'icon': self.getFullIconUrl(icon), 'desc': self.cleanHtmlStr(desc)})
        return tab
            
    def listHome(self, cItem, category):
        printDBG("listHome.listHome [%s]" % cItem)
        
        #http://kissanime.to/Home/GetNextUpdatedCartoon
        #POSTDATA {id:50, page:10}

        self.cacheHome = {}
        self.sortTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="tabmenucontainer">', '</div>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li>', '</li>')
        
        tabs = []
        for item in tmp:
            tabId = self.cm.ph.getSearchGroups(item, '''showTabData\('([^']+?)'\)''')[0]
            tabTitle = self.cleanHtmlStr(item)
            tabs.append({'id': tabId, 'title': tabTitle})
        
        printDBG(tabs)
        
        tmp2 = self.cm.ph.getDataBeetwenMarkers(data, '<div id="subcontent">', '<div class="clear">', False)[1]
        tmp2 = tmp2.split('<div id="tab-')
        if len(tmp2):
            del tmp2[0]
        for item in tmp2:
            # find tab id and title
            tabId = item[:item.find('"')].replace('-', '')
            cTab = None
            for tab in tabs:
                if tabId == tab['id']:
                    cTab = tab
                    break
            if cTab == None: 
                printDBG('>> continue tabId[%s]' % tabId)
                continue
            # check for more item
            moreUrl = self.cm.ph.getSearchGroups(item, '''<a href="([^"]+?)">More\.\.\.</a>''')[0]
            if moreUrl != '':
                params = dict(cItem)
                params.update({'category': category, 'title': tab['title'], 'url': self.getFullUrl(moreUrl)})
                self.addDir(params)
                continue
            itemsTab = self._getItems(item)
            if len(itemsTab):
                self.cacheHome[tab['id']] = itemsTab
                params = dict(cItem)
                params.update({'category': 'list_cached_items', 'tab_id': tab['id'], 'title': tab['title']})
                self.addDir(params)
            
    def listCats(self, cItem, category):
        printDBG("KissAnimeTo.listCats [%s]" % cItem)
        self.cache = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        # alphabet
        cacheKey = 'alphabet'
        self.cache[cacheKey] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="alphabet">', '</div>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''')[0]
            if '://' not in url and not url.startswith('/'):
                url = 'CartoonList/' + url
            title = self.cleanHtmlStr(item)
            self.cache[cacheKey].append({'title': title, 'url': self.getFullUrl(url)})
        if len(self.cache[cacheKey]) > 0:
            params = dict(cItem)
            params.update({'category': category, 'title': _('Alphabetically'), 'cache_key': cacheKey})
            self.addDir(params)
        
        # left tab
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="rightBox">', '<div class="clear', False)
        for item in tmp:
            catTitle = self.cm.ph.getDataBeetwenMarkers(item, '<div class="barTitle">', '</div>', False)[1]
            if catTitle == '':
                continue
            self.cache[catTitle] = []
            tmp2 = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a ', '</a>')
            for item2 in tmp2:
                url = self.cm.ph.getSearchGroups(item2, '''href="([^"]+?)"''')[0]
                title = self.cleanHtmlStr(item2)
                desc = self.cm.ph.getSearchGroups(item2, '''title="([^"]+?)"''')[0]
                self.cache[catTitle].append({'title': title, 'desc': desc, 'url': self.getFullUrl(url)})
            
            if len(self.cache[catTitle]) > 0:
                params = dict(cItem)
                params.update({'category': category, 'title': self.cleanHtmlStr(catTitle), 'cache_key': catTitle})
                self.addDir(params)
        
    def listSubCats(self, cItem, category):
        printDBG("KissAnimeTo.listSubCats [%s]" % cItem)
        tab = self.cache[cItem['cache_key']]
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(tab, cItem)
            
    def _urlAppendPage(self, url, page, sortBy, keyword=''):
        post_data = None
        if '' != keyword:
            post_data = {'keyword': keyword}
        if sortBy != '':
            if not url.endswith('/'):
                url += '/'
            url += sortBy + '/'
        if page > 1:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'page=%d' % page
        return post_data, url
        
    def listItems(self, cItem, category):
        printDBG("KissAnimeTo.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        sort_by = cItem.get('sort_by', '')
        post_data, url = self._urlAppendPage(cItem['url'], page, sort_by, cItem.get('keyword', ''))
        sts, data = self.getPage(url, {}, post_data)
        if not sts:
            return
        
        nextPage = False
        if ('page=%d"' % (page + 1)) in data:
            nextPage = True
            
        data = self.cm.ph.getDataBeetwenMarkers(data, 'Latest episode', '</table>')[1]
        data = self._getItems(data, '<tr')
        
        params = dict(cItem)
        params['category'] = category
        params['good_for_fav'] = True
        self.listsTab(data, params)
        
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)
            
    def listEpisodes(self, cItem):
        printDBG("KissAnimeTo.listEpisodes [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url']) 
        if not sts:
            return
        
        printDBG(data)
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'Day Added', '</table>')[1]
        data = self._getItems(data, '<tr', cItem.get('icon', ''))
        data.reverse()
        params = dict(cItem)
        params['category'] = 'video'
        params['good_for_fav'] = True
        self.listsTab(data, params, 'video')
        
    def getLinksForVideo(self, cItem):
        printDBG("KissAnimeTo.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        url = cItem['url']
        tries = 0
        while tries < 2:
            tries += 1
            
            sts, data = self.getPage(url) 
            if not sts:
                return urlTab
            
            if 'areyouhuman' in self.cm.meta.get('url', '').lower():
                tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'specialButton'), ('</a', '>'))[1]
                tmp = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=["']([^"^']+?)['"]''')[0])
                if tmp != '':
                    url = tmp
                    continue
            
            # get server list
            data = self.cm.ph.getDataBeetwenMarkers(data, 'id="selectServer"', '</select>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
            for item in data:
                serverTitle = self.cleanHtmlStr(item)
                serverUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''value="([^"]+?)"''')[0])
                if self.cm.isValidUrl(serverUrl):
                    urlTab.append({'name': serverTitle, 'url': serverUrl, 'need_resolve': 1})
            
            if 0 == len(urlTab):
                urlTab.append({'name': 'default', 'url': cItem['url'], 'need_resolve': 1})
            break
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("KissAnimeTo.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        if 'kissanime' not in videoUrl:
            return self.up.getVideoLinkExt(videoUrl)
        #if '&s=' in videoUrl:
        
        def _decUrl(data, password):
            printDBG('PASSWORD 2: ' + sha256(password).hexdigest())
            key = a2b_hex(sha256(password).hexdigest())
            printDBG("key: [%s]" % key)
            iv = a2b_hex("a5e8d2e9c1721ae0e84ad660c472c1f3")
            encrypted = base64.b64decode(data)
            cipher = AES_CBC(key=key, keySize=32)
            return cipher.decrypt(encrypted, iv)
            
        sts, data = self.getPage(videoUrl) 
        if not sts:
            return urlTab
        if 'AreYouHuman' in self.cm.meta['url']:
            SetIPTVPlayerLastHostError('Captcha failed! Try to use the RapidVideo hosting if available.')
        
        keySeed = self.cm.ph.getSearchGroups(data, r'"(\\x[^"]+?)"')[0]
        try:
            keySeed = keySeed.decode('string-escape')
        except Exception:
            printExc()
        
        printDBG('keySeed: ' + keySeed)
        
        tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(data, 'asp.wrap(', ')', False)
        for tmp in tmpTab:
            tmp = tmp.strip()
            if tmp.startswith('"'):
                tmp = tmp[1:-1]
            else:
                tmp = self.cm.ph.getSearchGroups(data, '''var %s =[^'^"]*?["']([^"^']+?)["']''')[0]
            if tmp == '':
                continue
            try:
                tmp = base64.b64decode(tmp)
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
                for item in tmp:
                    url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''')[0]
                    if 'googlevideo.com' not in url:
                        continue
                    name = self.cleanHtmlStr(item)
                    urlTab.append({'name': name, 'url': url, 'need_resolve': 0})
            except Exception:
                printExc()
                continue
               
        tmpTab = self.cm.ph.getDataBeetwenMarkers(data, '<select id="slcQualix">', '</select>', False)[1]
        tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(tmpTab, '<option', '</option>')
        for item in tmpTab:
            url = self.cm.ph.getSearchGroups(item, '''value="([^"]+?)"''')[0]
            if '' == url:
                continue
            try:
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> url[%s]" % url)
                url = _decUrl(url, base64.b64decode('bmhjc2NzZGJjc2R0ZW5lNzIzMGNzYjZuMjNuY2NzZGxuMjEzem5zZGJjc2QwMTI5MzM0NzM='))
                printDBG("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< url[%s]" % url)
                url = strwithmeta(url, {'Referer': 'http://kissanime.ru/Scripts/jwplayer/jwplayer.flash.swf'})
            except Exception:
                printExc()
                continue
            if not self.cm.isValidUrl(url):
                continue
            name = self.cleanHtmlStr(item)
            urlTab.append({'name': name, 'url': url, 'need_resolve': 0})
            
        if 0 < len(urlTab):
            max_bitrate = int(config.plugins.iptvplayer.kissanime_defaultformat.value)
            def __getLinkQuality(itemLink):
                try:
                    return int(self.cm.ph.getSearchGroups('|' + itemLink['name'] + '|', '[^0-9]([0-9]+?)[^0-9]')[0])
                except Exception:
                    return 0
            urlTab = CSelOneLink(urlTab, __getLinkQuality, max_bitrate).getBestSortedList()
            for idx in range(len(urlTab)):
                urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], {'iptv_wget_retry_on_http_error': '429', 'iptv_wget_waitretry': '0.1', 'iptv_wget_tries': '1000'})
                
            
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe ', '>', withMarkers=True, caseSensitive=False)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', grupsNum=1, ignoreCase=True)[0]
            url = self.getFullUrl(url)
            if url.startswith('http') and 'facebook.com' not in url and 1 == self.up.checkHostSupport(url):
                urlTab.extend(self.up.getVideoLinkExt(url))
        
        return urlTab
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KissAnimeTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({'keyword': searchPattern, 'url': self.getFullUrl('/Search/Anime')})
        self.listItems(cItem, 'list_episodes')
    
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
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'home':
            self.listHome(self.currItem, 'list_items')
        elif category == 'list_cached_items':
            cItem = dict(self.currItem)
            cItem['category'] = 'list_episodes'
            self.listsTab(self.cacheHome.get(cItem.get('tab_id'), []), cItem)
        elif category == 'list_cats':
            self.listCats(self.currItem, 'list_sub_cats')
        elif category == 'list_sub_cats':
            if self.currItem.get('cache_key', '') == 'alphabet':
                self.listSubCats(self.currItem, 'list_items')
            else:
                self.listSubCats(self.currItem, 'list_sort_tab')
        elif category == 'list_sort_tab':
            cItem = dict(self.currItem)
            cItem['category'] = 'list_items'
            self.listsTab(self.SORT_BY_TAB, cItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, KissAnimeTo(), True, [])
