# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote, urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import iterDictItems
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.hdsto_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                     ("webproxy", _("Web proxy")),
                                                                                     ("proxy_1", _("Alternative proxy server (1)")),
                                                                                     ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.hdsto_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.hdsto_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.hdsto_proxy))
    optionList.append(getConfigListEntry(_("email"), config.plugins.iptvplayer.hdsto_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.hdsto_password))
    return optionList
###################################################


def gettytul():
    return 'http://hds.to/'


class HDSTo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'HDSTo', 'cookie': 'HDSTo.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'http://www.hds.to/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/images/logox2.png')

        self.cacheLinks = {}
        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.membersOnly = [_('Page accessible to logged in members only.'), _('You can try to use proxy as workaround, check options under blue button.')]

    def getRealUrl(self, url):
        if config.plugins.iptvplayer.hdsto_proxy.value == 'webproxy' and url != None and 'browse.php?u=' in url:
            url = urllib_unquote(self.cm.ph.getSearchGroups(url + '&', '''\?u=(http[^&]+?)&''')[0])
        return url

    def getFullUrl(self, url, baseUrl=None):
        url = self.getRealUrl(url)
        baseUrl = self.getRealUrl(baseUrl)
        if not self.cm.isValidUrl(url) and baseUrl != None:
            if url.startswith('/'):
                baseUrl = self.cm.getBaseUrl(baseUrl)
            else:
                baseUrl = baseUrl.rsplit('/', 1)[0] + '/'
        return CBaseHostClass.getFullUrl(self, url.replace('&#038;', '&'), baseUrl)

    def setMainUrl(self, url):
        CBaseHostClass.setMainUrl(self, self.getRealUrl(url))

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.hdsto_proxy.value
        if proxy == 'webproxy':
            addParams = dict(addParams)
            proxy = 'http://n-guyot.fr/exit/browse.php?u={0}&b=4'.format(urllib_quote(baseUrl, ''))
            addParams['header']['Referer'] = proxy + '&f=norefer'
            baseUrl = proxy
        elif proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})
        tries = 0
        while tries < 2:
            tries += 1
            sts, data = self.cm.getPage(baseUrl, addParams, post_data)
            if sts:
                if self.getFullUrl(self.cm.meta['url']).endswith('/home.php'):
                    SetIPTVPlayerLastHostError('\n'.join(self.membersOnly))
                elif config.plugins.iptvplayer.hdsto_proxy.value == 'webproxy' and 'sslagree' in data:
                    sts, data = self.cm.getPage('http://n-guyot.fr/exit/includes/process.php?action=sslagree', addParams, post_data)
                    continue
            break
        return sts, data

    def getFullIconUrl(self, url, currUrl=None):
        url = self.getFullUrl(url, currUrl)
        proxy = config.plugins.iptvplayer.hdsto_proxy.value
        if proxy == 'webproxy':
            return url
        elif proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        return url

    def listMain(self, cItem):
        printDBG("HDSTo.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        if self.getFullUrl(self.cm.meta['url']).endswith('/home.php'):
            GetIPTVNotify().push('\n'.join(self.membersOnly), 'info', 10)

        printDBG(data)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>'), ('</nav', '>'), False)[1]
        tmp = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(tmp)
        if len(tmp) > 1:
            try:
                cTree = self.listToDir(tmp[1:-1], 0)[0]
                params = dict(cItem)
                params['c_tree'] = cTree['list'][0]
                params['category'] = 'cat_items'
                self.listCatItems(params, 'list_items')
            except Exception:
                printExc()

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def searchUrl(self, data):
        url = self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=([^>\s]+?)[>\s]''')[0]
        if url.startswith('"'):
            url = self.cm.ph.getSearchGroups(url, '"([^"]+?)"')[0]
        if url.startswith("'"):
            url = self.cm.ph.getSearchGroups(url, "'([^']+?)'")[0]
        return self.getFullUrl(url)

    def listCatItems(self, cItem, nextCategory):
        printDBG("HDSTo.listCatItems")
        printDBG('++++')
        printDBG(cItem['c_tree'])
        try:
            #cTree = cItem['c_tree']
            for cTree in cItem['c_tree']['list']:
                url = self.searchUrl(cTree['dat'])
                title = self.cleanHtmlStr(cTree['dat'])

                if url != '':
                    if 'list' in cTree:
                        title = _('--All--')
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                    params.pop('c_tree')
                    self.addDir(params)

                if len(cTree.get('list', [])) and title != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': title, 'c_tree': cTree})
                    self.addDir(params)

                for item in cTree.get('list', []):
                    title = self.cleanHtmlStr(item['dat'])
                    printDBG('>> ' + title)
                    url = self.searchUrl(item['dat'])
                    if 'list' not in item:
                        if url != '' and title != '':
                            params = dict(cItem)
                            params.pop('c_tree')
                            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                            self.addDir(params)
                    elif len(item['list']) == 1 and title != '':
                        item['list'][0]['dat'] = item['dat']
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                        self.addDir(params)
                    elif len(item['list']) > 1 and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'title': title, 'c_tree': item})
                        self.addDir(params)
        except Exception:
            printExc()

    def listSubItems(self, cItem):
        printDBG("HDSTo.listSubItems")
        self.currList = cItem['sub_items']

    def getItems(self, cItem, nextCategory, data):
        printDBG("HDSTo.getItems")
        retList = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^'^"]*?)?)['"]''')[0]
            if icon == '':
                icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'), False)[1])
            if 'details-serie' in cItem['url']:
                title += ' ' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'opacity'), ('</span', '>'), False)[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'name'), ('</a', '>'), False)[1])

            desc = ''
            descTab = []

            desc = self.cm.ph.getAllItemsBeetwenMarkers(item, '<h3', '</h3>')
            desc.append(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'genre'), ('</div', '>'))[1])
            desc.extend(self.cm.ph.getAllItemsBeetwenNodes(item, ('<span', '>'), ('</span', '>')))

            for t in desc:
                d = self.cleanHtmlStr(t)
                if d == '':
                    continue
                else:
                    descTab.append(d)
            desc = ' | '.join(descTab)
            params = dict(cItem)
            if 'tout_voir' in icon:
                params.update({'good_for_fav': False, 'title': 'TOUT VOIR >>'})
            elif 'details-serie' in url:
                params.update({'good_for_fav': True, 'title': title})
            else:
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title})

            params.update({'url': url, 'desc': desc, 'icon': self.getFullIconUrl(icon)})
            retList.append(params)
        return retList

    def listItems(self, cItem, nextCategory):
        printDBG("HDSTo.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        page = cItem.get('page', 1)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'), False)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)["'][^>]*?>\s*%s\s*<''' % (page + 1), 1, True)[0])

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '</ul>', 'filter-list-index'), ('</ul', '>'))
        if 0 == len(tmp):
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'sorting-list-'), ('</ul', '>'), False)[1]
            self.currList = self.getItems(cItem, nextCategory, data)
        else:
            for item in tmp:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h1', '</h1>')[1].replace(':', ''))
                subItems = self.getItems(cItem, nextCategory, item)
                if len(subItems):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': title, 'category': 'sub_items', 'sub_items': subItems})
                    self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("HDSTo.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.getFullUrl(self.cm.meta['url'])
        self.setMainUrl(cUrl)

        sTtile = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'title-holder'), ('</h', '>'), False)[1])
        desc = ''

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'iframe'), ('</a', '>'))
        for item in tmp:
            if 'file-video-o' not in item:
                continue
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
            if url == '':
                continue
            self.cacheLinks[url] = [{'name': '', 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1}]

            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': sTtile + '- ' + title, 'url': strwithmeta(url, {'Referer': cUrl}), 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)

        sts, tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '</a>', 'fa-language'), ('<', '>'))
        if sts:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': sTtile, 'url': strwithmeta(cUrl, {'Referer': cUrl}), 'desc': desc, 'prev_url': cUrl})
            self.addVideo(params)
            self.cacheLinks[cUrl] = [{'name': '', 'url': strwithmeta(cUrl, {'Referer': cUrl}), 'need_resolve': 1}]

            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
            title = self.cleanHtmlStr(tmp)
            if url != '':
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': sTtile + '- ' + title, 'url': strwithmeta(url, {'Referer': cUrl}), 'desc': desc, 'prev_url': cUrl})
                self.addVideo(params)
                self.cacheLinks[url] = [{'name': '', 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1}]

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'collapsible'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '</i>', '<script>')[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            urls = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
            for it in item:
                linkName = self.cleanHtmlStr(it)
                linkUrl = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''href=['"]([^"^']+?)["']''', 1, True)[0], cUrl)
                if linkUrl == '':
                    continue
                urls.append({'name': linkName, 'url': strwithmeta(linkUrl, {'Referer': cUrl}), 'need_resolve': 1})

            if len(urls):
                url = cUrl + '#' + title
                self.cacheLinks[url] = urls
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': sTtile + ' ' + title, 'url': strwithmeta(url, {'Referer': cUrl}), 'desc': desc, 'prev_url': cUrl})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        self.tryTologin()

        searchPattern = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['category'] = 'list_items'
        cItem['url'] = self.getFullUrl('/search.php?q=') + urllib_quote_plus(searchPattern)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'film-preview'), ('</ul', '>'), False)[1]
        self.currList = self.getItems(cItem, 'explore_item', data)

    def getLinksForVideo(self, cItem):
        self.tryTologin()

        printDBG("HDSTo.getLinksForVideo [%s]" % cItem)
        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("HDSTo.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        linksTab = []
        if 0 == self.up.checkHostSupport(videoUrl):
            sts, data = self.getPage(videoUrl)
            if sts:
                cUrl = self.getFullUrl(self.cm.meta['url'])
                sts, tmp = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>')
                if sts:
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>', False, False)
                    for item in tmp:
                        if 'video/mp4' in item.lower():
                            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                            if url != '':
                                linksTab.append({'name': str(len(linksTab) + 1) + ' mp4', 'url': url})

                jwplayer = False
                jscode = []
                data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
                for item in data:
                    if '"$' in item or 'var _' in item or 'bitrates' in item:
                        jscode.append(item)
                    elif 'jwplayer' in item:
                        jwplayer = True
                        jscode.append(item)

                if not jwplayer:
                    jscode.insert(0, 'var document={};function RadiantMP(){return document}document.getElementById=function(){return document},document.addEventListener=function(){},document.init=function(){print(JSON.stringify(arguments))};')
                else:
                    jscode.insert(0, 'window=this; function stub() {}; function jwplayer() {return {setup:function(){print(JSON.stringify(arguments[0]))}, onTime:stub, onPlay:stub, onComplete:stub, onReady:stub, addButton:stub}}; window.jwplayer=jwplayer;')

                ret = js_execute('\n'.join(jscode))
                try:
                    data = byteify(json.loads(ret['data'].strip()))
                    if jwplayer:
                        for dat in data['playlist']:
                            subsTab = []
                            for item in dat.get('tracks', []):
                                try:
                                    if item.get('kind', '') != 'captions':
                                        continue
                                    title = self.cleanHtmlStr(item['label'])
                                    lang = item['file'].rsplit('-', 1)[-1].split('.', 1)[0]
                                    if lang == '':
                                        lang = title
                                    subsTab.append({'title': title, 'url': self.getFullUrl(item['file'], cUrl), 'lang': lang, 'format': item['file'].rsplit('.', 1)[-1]})
                                except Exception:
                                    pass

                            tmpLinksTab = []
                            for item in dat.get('sources', []):
                                name = len(tmpLinksTab)
                                if isinstance(item, dict):
                                    url = item['file']
                                    name = item.get('label', name)
                                else:
                                    url = item
                                type = url.split('.')[-1].split('?', 1)[0].lower()
                                if type == 'm3u8':
                                    tmpLinksTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True))
                                elif type == 'mp4':
                                    tmpLinksTab.append({'name': name, 'url': url})

                            if len(subsTab):
                                for idx in range(len(tmpLinksTab)):
                                    tmpLinksTab[idx]['url'] = strwithmeta(tmpLinksTab[idx]['url'], {'external_sub_tracks': subsTab})

                            linksTab.extend(tmpLinksTab)
                    else:
                        for key, dat in iterDictItems(data):
                            subsTab = []
                            for item in dat.get('ccFiles', []):
                                if len(item) < 3:
                                    continue
                                subsTab.append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[2], cUrl), 'lang': self.cleanHtmlStr(item[0]), 'format': self.cleanHtmlStr(item[0]).rsplit('.', 1)[-1]})

                            tmpLinksTab = []
                            for type, item in iterDictItems(dat.get('bitrates', {})):
                                if type == 'hls':
                                    tmpLinksTab.extend(getDirectM3U8Playlist(item, checkExt=False, checkContent=True))
                                elif type == 'mp4' and isinstance(item, list):
                                    for url in item:
                                        if '-' in url:
                                            name = url.rsplit('-', 1)[-1].replace('.', ' ')
                                        else:
                                            name = 'mp4'
                                        tmpLinksTab.append({'name': name, 'url': url})

                            if len(subsTab):
                                for idx in range(len(tmpLinksTab)):
                                    tmpLinksTab[idx]['url'] = strwithmeta(tmpLinksTab[idx]['url'], {'external_sub_tracks': subsTab})

                            linksTab.extend(tmpLinksTab)
                except Exception:
                    printExc()
        else:
            linksTab = self.up.getVideoLinkExt(videoUrl)
        return linksTab

    def getArticleContent(self, cItem, data=None):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem)
        retTab = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            self.tryTologin()
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        data = data.split('title-holder', 1)[-1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h', '>'), ('</h', '>'), False)[1])
        icon = ''
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'text-hold'), ('</div', '>'), False)[1])

        itemsList = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'descr-list'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            item = item.split('</span>', 1)
            key = self.cleanHtmlStr(item[0])
            val = self.cleanHtmlStr(item[-1]).replace(' , ', ', ')
            if val == '' and 'determinate' in item[-1]:
                val = self.cm.ph.getSearchGroups(item[-1], '''<div([^>]+?determinate[^>]+?)>''')[0]
                val = self.cm.ph.getSearchGroups(val, '''width\:\s*([0-9]+)''')[0]
                try:
                    val = str(int(val) / 10.0)
                except Exception:
                    continue
            if key == '' or val == '':
                continue
            itemsList.append((key, val))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.hdsto_login.value or\
            self.password != config.plugins.iptvplayer.hdsto_password.value:

            self.login = config.plugins.iptvplayer.hdsto_login.value
            self.password = config.plugins.iptvplayer.hdsto_password.value

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                return False

            rm(self.COOKIE_FILE)

            sts, data = self.getPage(self.getFullUrl('/home.php'))
            if not sts:
                return False

            actionUrl = self.getFullUrl(self.cm.meta['url'])
            post_data = {'email': self.login, 'password': self.password, 'submit_form': 'Login'}

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = self.cm.meta['url']
            sts, data = self.getPage(actionUrl, httpParams, post_data)
            if sts and (actionUrl != self.getFullUrl(self.cm.meta['url']) or 'sweetAlert(' not in data):
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                if sts:
                    data = self.cm.ph.getDataBeetwenMarkers(data, 'sweetAlert(', ')', False)[1]
                    data = data.split('",')
                    if len(data) == 3:
                        idx = data[1].find('"')
                        if idx >= 0:
                            msgTab.append(self.cleanHtmlStr(data[1][idx + 1:]))
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

        self.tryTologin()

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'})
        elif category == 'cat_items':
            self.listCatItems(self.currItem, 'list_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, HDSTo(), True, [])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
