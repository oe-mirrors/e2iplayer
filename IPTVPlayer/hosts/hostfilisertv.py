# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetTmpDir, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.sweetcaptcha_v2widget import UnCaptchaSweetCaptchaWidget
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
import base64
try:    import json
except Exception: import simplejson as json
from datetime import datetime
from time import sleep, time
from copy import deepcopy
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################


def gettytul():
    return 'https://fili.cc/'

class FiliserTv(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'FiliserTv.tv', 'cookie':'filisertv.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://fili.cc/'
        self.DEFAULT_ICON_URL = 'https://fili.cc/assets/img/logo2.png'
        
        self.MAIN_CAT_TAB = [{'category':'list_items',        'title': _('Movies'),                       'url':self.getFullUrl('filmy')   },
                             {'category':'list_items',        'title': _('Series'),                       'url':self.getFullUrl('seriale') },
                             {'category':'search',            'title': _('Search'),               'search_item':True,                      },
                             {'category':'search_history',    'title': _('Search history'),                                                } 
                            ]
        
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.cacheSeasons = {}
        FiliserTv.SALT_CACHE = {}
        self.WaitALittleBit  = None
        self.filtersTab = [] # ['language', 'genres', 'year', 'sort_by']

    def getStr(self, item, key):
        if key not in item: return ''
        if item[key] == None: return ''
        return str(item[key])

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if url == '': return ''

            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        addParams['cookie_items'] = {'adult_warning':'true'}

        url = baseUrl
        urlParams = deepcopy(addParams)
        urlData = deepcopy(post_data)
        unloadUrl = None #
        tries = 0
        removeCookieItems = False
        while tries < 20:
            tries += 1
            sts, data = self.cm.getPageCFProtection(url, urlParams, urlData)
            if not sts: return sts, data

            if unloadUrl != None:
                self.cm.getPageCFProtection(unloadUrl, urlParams)
                unloadUrl = None

            if 'sucuri_cloudproxy' in data:
                cookieItems = {}
                jscode = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)[1]
                if 'eval' in jscode:
                    jscode = '%s\n%s' % (base64.b64decode('''dmFyIGlwdHZfY29va2llcz1bXSxkb2N1bWVudD17fTtPYmplY3QuZGVmaW5lUHJvcGVydHkoZG9jdW1lbnQsImNvb2tpZSIse2dldDpmdW5jdGlvbigpe3JldHVybiIifSxzZXQ6ZnVuY3Rpb24obyl7bz1vLnNwbGl0KCI7IiwxKVswXS5zcGxpdCgiPSIsMiksb2JqPXt9LG9ialtvWzBdXT1vWzFdLGlwdHZfY29va2llcy5wdXNoKG9iail9fSk7dmFyIHdpbmRvdz10aGlzLGxvY2F0aW9uPXt9O2xvY2F0aW9uLnJlbG9hZD1mdW5jdGlvbigpe3ByaW50KEpTT04uc3RyaW5naWZ5KGlwdHZfY29va2llcykpfTs='''), jscode)
                    ret = js_execute( jscode )
                    if ret['sts'] and 0 == ret['code']:
                        try:
                            cookies = byteify(json.loads(ret['data'].strip()))
                            for cookie in cookies: cookieItems.update(cookie)
                        except Exception:
                            printExc()
                cookieItems.update({'adult_warning':'true'})
                self.defaultParams['cookie_items'] = cookieItems
                urlParams['cookie_items'] = cookieItems
                removeCookieItems = False
                sts, data = self.cm.getPageCFProtection(url, urlParams, urlData)

            # remove not needed used cookie
            if removeCookieItems:
                self.defaultParams.pop('cookie_items', None)
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['___utmvc'])
#            printDBG(data)
            return sts, data

        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url)
        if url == '': return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})

    def fillFilters(self, cItem):
        self.cacheFilters = {}
        self.filtersTab = [] # ['language', 'genres', 'year', 'sort_by']
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        def addFilter(data, key, addAny, titleBase, marker):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, '''%s=['"]([^'^"]+?)['"]''' % marker)[0]
                if value == '': continue
                title = ph.clean_html(item)
                if titleBase == '':
                    title = title.title()
                self.cacheFilters[key].append({'title':titleBase + title, key:value})
            if addAny and len(self.cacheFilters[key]):
                self.cacheFilters[key].insert(0, {'title':'Wszystkie'})
            if len(self.cacheFilters[key]):
                self.filtersTab.append(key)

        # language
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="vBox"', '</div>', withMarkers=True)
        addFilter(tmpData, 'language', True, '', 'data-type')

        # genres
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li data-gen', '</li>', withMarkers=True)
        addFilter(tmpData, 'genres', True, '', 'data-gen') 

        # year
        self.cacheFilters['year'] = [{'title':_('Year: ') + _('Any')}]
        year = datetime.now().year
        while year >= 1978:
            self.cacheFilters['year'].append({'title': _('Year: ') + str(year), 'year': year})
            year -= 1

        # sort
        self.cacheFilters['sort_by'] = []
        for item in [('date', 'data dodania/aktualizacji'), ('views', ' liczba wyświetleń'), ('rate', ' ocena')]:
            self.cacheFilters['sort_by'].append({'title': _('Sort by: ') + str(item[1]), 'sort_by': item[0]})

        # add order to sort_by filter
        orderLen = len(self.cacheFilters['sort_by'])
        for idx in range(orderLen):
            item = deepcopy(self.cacheFilters['sort_by'][idx])
            # desc
            self.cacheFilters['sort_by'][idx].update({'title':'\xe2\x86\x93 ' + self.cacheFilters['sort_by'][idx]['title'], 'order':'desc'})
            # asc
            item.update({'title': '\xe2\x86\x91 ' + item['title'], 'order':'asc'})
            self.cacheFilters['sort_by'].append(item)
        if len(self.cacheFilters['sort_by']):
            self.filtersTab.append('sort_by')

    def listFilter(self, cItem):
        params = dict(cItem)
        idx = params.get('f_idx', 0)
        params['f_idx'] = idx + 1
        
        if idx < len(self.filtersTab):
            tab = self.cacheFilters.get(self.filtersTab[idx], [])
            self.listsTab(tab, params)
        
    def listItems(self, cItem, nextCategory):
        printDBG("FiliserTv.listItems")
        
        baseUrl = cItem['url']
        if '?' not in baseUrl:
            baseUrl += '?'
        else:
            baseUrl += '&'
        
        page = cItem.get('page', 1)
        if page > 1:
            baseUrl += 'page={0}&'.format(page)
        
        if cItem.get('genres', '') not in ['-', '']:
            baseUrl += 'kat={0}&'.format(urllib.quote(cItem['genres']))
        
        if cItem.get('language', '') not in ['-', '']:
            baseUrl += 'ver={0}&'.format(urllib.quote(cItem['language']))
        
        if cItem.get('year', '0') not in ['0', '-', '']:
            baseUrl += 'start_year={0}&end_year={1}&'.format(cItem['year'], cItem['year'])
        
        if cItem.get('sort_by', '0') not in ['0', '-', '']:
            baseUrl += 'sort_by={0}&'.format(urllib.quote(cItem['sort_by']))
            
        if cItem.get('order', '0') not in ['0', '-', '']:
            baseUrl += 'type={0}&'.format(urllib.quote(cItem['order']))
            
        sts, data = self.getPage(self.getFullUrl(baseUrl), self.defaultParams)
        if not sts: return
        
        if '>Następna<' in data:
            nextPage = True
        else: nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section class="item"', '</section>', withMarkers=True)
        for item in data:
            url    = self.getFullUrl(ph.search(item, ph.A)[1])
            icon   = self.getFullIconUrl(ph.search(item, ph.IMG)[1].strip())
            title  = ph.clean_html(ph.getattr(item, 'alt'))
            if title == '': title = ph.clean_html(ph.getattr(item, 'title'))
            title1 = ph.clean_html(ph.find(item, ('<h3', '>'), '</h3>', flags=0)[1])
            title2 = ph.clean_html(ph.find(item, ('<h4', '>'), '</h4>', flags=0)[1])
            
            desc   = ph.clean_html(item.split('<div class="block2">')[-1].replace('<p class="desc">', '[/br]'))
            params = {'good_for_fav': True, 'title':title, 'url':url, 'icon':icon, 'desc':desc}
            if '/film/' in url:
                self.addVideo(params)
            elif '/serial/' in url:
                params['category'] = nextCategory
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title':_('Next page'), 'page':page + 1})
            self.addDir(params)

    def listSeasons(self, cItem, nextCategory):
        printDBG("FiliserTv.listSeasons")
        
        self.cacheSeasons = {'keys':[], 'dict':{}}
        
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts: return
        
        data = data.split('<div id="episodes">')
        if 2 != len(data): return
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data[0], '<div id="seasons_list">', '<div class="clear">')[1]
        tmp = re.compile('<[^>]+?num\="([0-9]+?)"[^>]*?>([^<]+?)<').findall(tmp)
        for item in tmp:
            self.cacheSeasons['keys'].append({'key':item[0], 'title':ph.clean_html(item[1])})
        
        del data[0]
        
        # fill episodes
        for season in self.cacheSeasons['keys']:
            tmp = self.cm.ph.getDataBeetwenMarkers(data[0], 'data-season-num="%s"' % season['key'], '</ul>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>', withMarkers=True)
            self.cacheSeasons['dict'][season['key']] = []
            for item in tmp:
                url    = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                title  = ph.clean_html(self.cm.ph.getDataBeetwenMarkers(item, '<a class="episodeName"', '</a>')[1])
                es     = self.cm.ph.getSearchGroups(url, '''/(s[0-9]+?e[0-9]+?)/''')[0]
                self.cacheSeasons['dict'][season['key']].append({'good_for_fav': True, 'title': '%s: %s %s' % (cItem['title'], es, title), 'url':url})
                
        for season in self.cacheSeasons['keys']:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category':nextCategory, 'title':season['title'], 's_key':season['key']})
            self.addDir(params)
        
    def listEpisodes(self, cItem):
        printDBG("FiliserTv.listEpisodes")
        
        tab = self.cacheSeasons.get('dict', {}).get(cItem['s_key'], [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FiliserTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        baseUrl = self.getFullUrl('szukaj?q=' + urllib.quote_plus(searchPattern))
        sts, data = self.getPage(baseUrl)
        if not sts: return

        data = ph.findall(data, ('<ul', '>', 'resultList2'), '</ul>', flags=0)
        for sData in data:
            sData = ph.findall(sData, ('<li', '>'), '</li>', flags=0)
            for item in sData:
                tmp    = item.split('<div class="info">')
                url    = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                title  = ph.clean_html(tmp[0].replace('<div class="title_org">', '/'))
                icon   = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0].strip())
                desc   = ph.clean_html(tmp[-1])
                params = {'good_for_fav': True, 'title':title, 'url':url, 'icon':icon, 'desc':desc}
                if '/film/' in url:
                    self.addVideo(params)
                elif '/serial/' in url:
                    params['category'] = 'list_seasons'
                    self.addDir(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("FiliserTv.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if len(self.cacheLinks.get(cItem['url'], [])):
            return self.cacheLinks[cItem['url']]

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts: return []

        errorMessage = ph.clean_html(ph.find(data, ('<h2', '>', 'title_block'), '</section>')[1])
        if '' != errorMessage:  SetIPTVPlayerLastHostError(errorMessage)

        lParams = {}
        tmp = ph.findall(data, ('<div', '>', ph.check(ph.any, ('"box"',"'box'"))), '</section>', flags=ph.START_S, limits=2)
        if not tmp: return
        lParams['code'] = ph.getattr(tmp[0], 'data-code')
        lParams['code2'] = ph.getattr(tmp[0], 'data-code2')
        lParams['type'] = ph.getattr(tmp[0], 'id').split('_', 1)[0]

        tmp = ph.findall(tmp[1], ('<h', '>'), ('</h', '>'), flags=0, limits=2)
        lParams['title1'] = ph.clean_html(tmp[0])
        lParams['title2'] = ph.clean_html(tmp[-1])

        data = data.split('<div id="links">')
        if 2 != len(data): return []

        tabs = []
        tmp = ph.find(data[0], '<div id="video_links"', '<div class="clear">')[1]
        tmp = re.compile('<[^>]+?data-type\="([^"]+?)"[^>]*?>([^<]+?)<').findall(tmp)
        for item in tmp:
            tabs.append({'key':item[0], 'title':ph.clean_html(item[1])})

        if tabs: del data[0]

        for tab in tabs:
            tmp = ph.find(data[0], 'data-type="%s"' % tab['key'], '</ul>')[1]
            tmp =  ph.findall(tmp, '<li', '</li>')
            for item in tmp:
                url    = strwithmeta(ph.getattr(item, 'data-ref'), {'link_params':lParams})
                title  = ph.clean_html(item.split('<div class="rightSide">')[0])
                urlTab.append({'name': '%s: %s' % (tab['title'], title), 'url':url, 'need_resolve':1})
        
        self.cacheLinks[cItem['url']] = urlTab
        return urlTab
        
    def getHeaders(self, tries):
        header = dict(self.HEADER)
        if tries == 1:
            return header
        
        if self.WaitALittleBit == None:
            try:
                tmp = 'ZGVmIHphcmF6YShpbl9hYmMpOg0KICAgIGRlZiByaGV4KGEpOg0KICAgICAgICBoZXhfY2hyID0gJzAxMjM0NTY3ODlhYmNkZWYnDQogICAgICABiID0gZmYoYiwgYywgZCwgYSwgdGFiQlszXSwgMjIsIC0xMDQ0NTI1MzMwKTsN\rZGVmIFdhaXRBTGl0dGxlQml0KHRyaWVzKToNCiAgICBmaXJzdEJ5dGUgPSBbODUsMTA5LDg5LDkxLDQ2LDE3OCwyMTcsMjEzXQ0KICAgIGlwID0gJyVzLiVzLiVzLiVzJyAlIChmaXJzdEJ5dGVbcmFuZGludCgwLCBsZW4oZmlyc3RCeXRlKSldLCByYW5kaW50KDAsIDI0NiksICByYW5kaW50KDAsIDI0NiksICByYW5kaW50KDAsIDI0NikpDQogICAgcmV0dXJuIHsnVXNlci1BZ2VudCc6J01vemlsbGEvNS4wJywnQWNjZXB0JzondGV4dC9odG1sJywnWC1Gb3J3YXJkZWQtRm9yJzppcH0NCg0K'
                tmp = base64.b64decode(tmp.split('\r')[-1]).replace('\r', '')
                WaitALittleBit = compile(tmp, '', 'exec')
                vGlobals = {"__builtins__": None, 'len': len, 'list': list, 'dict':dict, 'randint':randint}
                vLocals = { 'WaitALittleBit': '' }
                exec WaitALittleBit in vGlobals, vLocals
                self.WaitALittleBit = vLocals['WaitALittleBit']
            except Exception:
                printExc()
        try:
            header.update(self.WaitALittleBit(tries))
        except Exception:
            printExc()
        return header
        
    def getSweetCaptchaRespond(self, data):
        printDBG("FiliserTv.getSweetCaptchaRespond")
        
        def _getFullUrl(url):
            urlPrefix = 'http:'
            if url.startswith('//'): url = urlPrefix + url
            return url
        
        def n(e, n):
            a = ""
            n = urllib.unquote(n)
            for r in range(len(n)-1, -1, -1):
                t = n[r]
                if (t >= "a" and "z" >= t) or (t >= "A" and "Z" >= t):
                    a += chr(65 + e.find(t) % 26)
                else:
                    a += t
            return a.lower()
        
        retData = {}
        
        printDBG(data)
        url = _getFullUrl(self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?/captcha/[^'^"]*?)['"]''')[0])
        url += 'mobile=1&_=' + str(int(time() * 1000))
        
        sts, data = self.getPage(url)
        if not sts: return retData
        
        printDBG(data)
        thumbFileTab = []
        try:
            data = json_loads(data)
            imgUrlTab = []
            for item in data["a"]:
                imgUrlTab.append(_getFullUrl(n(data['simple_key'], item['src'])))
            imgUrlTab.append(_getFullUrl(n(data['simple_key'], data['q'])))
            printDBG(imgUrlTab)
            
            errorOccurred = False
            params = {'maintype': 'image', 'subtypes':['png'], 'check_first_bytes':['\x89\x50\x4E\x47']}
            for idx in range(len(imgUrlTab)):
                imgUrl   = imgUrlTab[idx]
                filePath = GetTmpDir('.iptvplayer_captcha_%s.png' % idx)
                ret = self.cm.saveWebFile(filePath, imgUrl, params)
                if not ret.get('sts'):
                    SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                    errorOccurred = True
                    break
                thumbFileTab.append(filePath)
            if not errorOccurred:
                verify = data['drag']['verify']
                challenge = data['drag']['challenge']
                printDBG(thumbFileTab)
                printDBG("OK")
                printDBG(verify)
                printDBG(challenge)
                
                retArg = self.sessionEx.waitForFinishOpen(UnCaptchaSweetCaptchaWidget, params={'icon_list':thumbFileTab, 'title':verify, 'challenge':challenge})
                printDBG('>>>>>>>> Captcha response %r' % (retArg))
                if retArg is not None and len(retArg) and retArg[0]:
                    answer = retArg[0]['resp_idx']
                    printDBG('>>>>>>>> Captcha answer[%s]' % (answer))
                    retData = {'sckey':data['k'], 'scvalue':data['a'][answer]['hash'][5:15], 'scvalue2':0}
                else:
                    retData = None
        except Exception:
            printExc()
        
        for file in thumbFileTab:
            rm(file)
        
        return retData
        
    def getVideoLinks(self, videoUrl):
        printDBG("FiliserTv.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            key = self.cacheLinks.keys()[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break
        
        reCaptcha = False
        if not self.cm.isValidUrl(videoUrl):
            linkParams = videoUrl.meta['link_params']
            url = self.getFullUrl('/embed?type=%s&code=%s&code2=%s&salt=%s&title=%s&title2=%s' % (linkParams['type'], linkParams['code'], linkParams['code2'], videoUrl, urllib.quote(linkParams['title1']), urllib.quote(linkParams['title2'])))
            salt = '%s|%s' % (videoUrl, linkParams)
            if salt not in FiliserTv.SALT_CACHE:
                httpParams = dict(self.defaultParams)
                tries = 0
                googleCaptcha = False
                while tries < 6:
                    reCaptcha = False
                    
                    tries += 1
                    #if tries > 3:
                    #    rm(self.COOKIE_FILE)
                    
                    if tries > 1 and googleCaptcha: httpParams['header'] = self.getHeaders(tries)
#                    httpParams['header']['Cookie'] = 'adult_warning=true'
                    sts, data = self.getPage(url, httpParams)
                    if not sts: return urlTab
                    
                    if '/captchaResponse' in data:
                        googleCaptcha = True
                        reCaptcha = True
                        sleep(1)
                        continue
                        
                    if 'sweetcaptcha' in data:
                        post_data = self.getSweetCaptchaRespond(data)
                        printDBG(post_data)
                        
                        if post_data == None: # cancelled
                            videoUrl = ''
                            break
                        
                        if post_data == {}: # retry
                            continue
                        
                        httpParams2 = dict(httpParams)
                        httpParams2['header']['Referer'] = url
                        sts, data = self.getPage(url, httpParams2, post_data)
                        
                        if not sts or 'sweetcaptcha' in data:
                            continue # wrong answer? -> Another try 
                        reCaptcha = True
                        printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                        printDBG(data)
                        printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                    
                    videoUrl = self.cm.ph.getSearchGroups(data, '''var\s*url\s*=\s*['"](http[^'^"]+?)['"]''')[0]
                    videoUrl = videoUrl.replace('#WIDTH', '800').replace('#HEIGHT', '600')
                    
                    if self.cm.isValidUrl(videoUrl):
                        FiliserTv.SALT_CACHE[salt] = base64.b64encode(videoUrl)
                    
                    break
            else:
                videoUrl = base64.b64decode(FiliserTv.SALT_CACHE[salt])

        from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser 
        videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url}) 

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
            
        if reCaptcha and 0 == len(urlTab):
            self.sessionEx.waitForFinishOpen(MessageBox, 'Otwórz stronę http://filiser.tv/ w przeglądarce i odtwórz dowolny film potwierdzając, że jesteś człowiekiem.', type = MessageBox.TYPE_ERROR, timeout = 10 )
        
        return urlTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')

        printDBG( "handleService: || name[%s], category[%s] " % (name, category) )
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif 'list_items' == category:
            idx = self.currItem.get('f_idx', 0)
            if 0 == idx:
                self.fillFilters(self.currItem)

            if idx < len(self.filtersTab):
                self.listFilter(self.currItem)
            else:
                self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
    #SEARCH
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
        CHostBase.__init__(self, FiliserTv(), True, [])


