# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlsplit, urlunsplit, urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import iterDictItems
###################################################
# FOREIGN import
###################################################
import re
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kkiste_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                           ("proxy_1", _("Alternative proxy server (1)")),
                                                                                           ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.kkiste_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kkiste_proxy))
    if config.plugins.iptvplayer.kkiste_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.kkiste_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://kinokiste.me/' #'https://kkiste.ag/'


class KKisteAG(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kkiste.ag', 'cookie': 'kkiste.ag.cookie'})
        self.reIMG = re.compile(r'''<img[^>]+?src=(['"])([^>]*?)(?:\1)''', re.I)
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items': {'approve_search': 'yes'}}

        self.DEFAULT_ICON_URL = 'https://tarnkappe.info/wp-content/uploads/kkiste-logo.jpg'

        self.DEFAULT_MAIN_URL = 'https://kinokiste.me/'
        self.domains = ['https://kinokiste.me/', 'https://www2.streamkiste.com/']
        self.MAIN_URL = None

        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.cacheLinks = {}

    def getMainUrl(self):
        if not self.MAIN_URL:
            self.selectDomain()
        return self.MAIN_URL if self.MAIN_URL else self.DEFAULT_MAIN_URL

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.kkiste_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HTTP_HEADER['User-Agent']}
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def selectDomain(self):
        domains = list(self.domains)
        domain = config.plugins.iptvplayer.kkiste_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and '&genre=' in data:
                self.setMainUrl(data.meta['url'])
                break

    def listMain(self, cItem, nextCategory):
        printDBG("KKisteAG.listMain")
        self.cacheFilters = {}

        sts, data = self.getPage(self.getFullUrl('/featured'))
        if not sts:
            return
        data = re.sub("<!--[\s\S]*?-->", "", data)

        if 'myFilter()' in data:
            tmp = ph.find(data, ('<ul', '>', 'menu-main-menu'), '</div>', flags=0)[1]
            tmp = re.compile('</?ul[^>]*?>').split(tmp)

            sTitle = ''
            url = ''
            for section in tmp:
                subItems = []
                section = ph.findall(section, ('<a', '>'), '</a>', flags=ph.START_S)
                for idx in range(1, len(section), 2):
                    url = ph.search(section[idx - 1], ph.A)[1]
                    title = ph.clean_html(section[idx])
                    if url == '#':
                        continue
                    else:
                        subItems.append(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'url': self.getFullUrl(url)}))

                if subItems and sTitle:
                    self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'title': sTitle, 'sub_items': subItems}))
                    sTitle = ''
                else:
                    self.currList.extend(subItems)

                if url == '#':
                    sTitle = title

            # filter
            filtersMap = {'Sortieren nach': 'order_by', 'Auflösung': 'res', 'Yahr': 'year', 'Genres': 'genre'}
            tmp = ph.find(data, ('<div', '>', 'tag_cloud'), ('<div', '>', 'loop-'), flags=0)[1]
            tmp = ph.rfindall(tmp, '</div>', ('<h3', '</h3>'), flags=ph.END_S)
            for idx in range(1, len(tmp), 2):
                sTitle = ph.clean_html(tmp[idx - 1])
                key = filtersMap.get(sTitle, '')
                if not key:
                    continue
                self.cacheFilters[key] = []
                filters = []
                items = ph.findall(tmp[idx], ('<a', '>'), '</a>', flags=ph.START_S)
                for i in range(1, len(items), 2):
                    value = ph.search(ph.getattr(items[i - 1], 'href'), '%s=([^&]+)' % key)[0]
                    self.cacheFilters[key].append({'f_%s' % key: value, 'title': ph.clean_html(items[i])})

                if self.cacheFilters[key]:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                    self.cacheFiltersKeys.append(key)

            if len(self.cacheFiltersKeys):
                self.addDir(MergeDicts(cItem, {'category': 'list_filters', 'title': 'FILTER', 'f_idx': 0}))
        else:
            pass
            # ToDo

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listFilters(self, cItem, nextCategory):
        printDBG("KKisteAG.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listSubItems(self, cItem):
        printDBG("KKisteAG.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem):
        printDBG("KKisteAG.listItems")
        page = cItem.get('page', 1)

        if page == 1 and 'f_idx' in cItem:
            url = ''
            query = {}
            for key in self.cacheFiltersKeys:
                val = cItem.get('f_' + key)
                if not val:
                    continue
                query[key] = val
            url = self.getFullUrl('?c=movie&m=filter&' + urllib_urlencode(query))
        else:
            url = cItem['url']

        sts, data = self.getPage(url)
        if not sts:
            return

        if page == 1 and 'f_idx' not in cItem:
            tmp = ph.find(data, 'function load_contents', '}')[1]
            url = self.getFullUrl(ph.search(tmp, '''['"]([^'^"]*m=[^'^"]*?)['"]''')[0])
            if url:
                self.listItems2(MergeDicts(cItem, {'url': url, 'category': 'list_items2'}))
                return
        nextPage = ph.find(data, ('<div', '>', 'pag-nav'), '</div>', flags=0)[1]
        nextPage = self.getFullUrl(ph.clean_html(ph.search(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>\s*?%s\s*?<''' % (page + 1))[0]))

        data = ph.find(data, ('<div', '>', 'loop-content'), ('<div', '>', 'loop-nav'))[1]
        self.doListItems(cItem, data)
        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1}))

    def listItems2(self, cItem):
        printDBG("KKisteAG.listItems2")
        page = cItem.get('page', 1)
        sts, data = self.getPage(cItem['url'], post_data={'page': page})
        if not sts:
            return
        self.doListItems(cItem, data)
        if len(self.currList):
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'page': page + 1}))

    def doListItems(self, cItem, data):
        data = ph.rfindall(data, '</div>', ('<div', '>', 'post-'))
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            icon = self.getFullIconUrl(ph.search(item, self.reIMG)[1])
            title = ph.clean_html(ph.find(item, ('<h2', '>'), '</h2>', flags=0)[1])

            desc = []
            tmp = ph.find(item, ('<div', '>', 'meta'), '</div>', flags=0)[1]
            tmp = ph.findall(tmp, ('<span', '>'), '</span>', flags=0)
            for t in tmp:
                t = ph.clean_html(t)
                if t:
                    desc.append(t)

            desc = [' | '.join(desc)]
            desc.append(ph.clean_html(ph.find(item, ('<p', '>'), '</p>', flags=0)[1]))

            desc.append(ph.clean_html(ph.find(item, ('<div', '>', 'desc'), '</div>', flags=0)[1]))
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'prev_url': url, 'category': 'explore_item', 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        url = self.getFullUrl('?c=movie&m=filter&keyword=' + urllib_quote_plus(searchPattern))
        self.listItems({'name': 'category', 'category': 'list_items', 'url': url})

    def exploreItem(self, cItem):
        printDBG("KKisteAG.exploreItem")

        sts, mainData = self.getPage(cItem['url'])
        if not sts:
            return

        url = self.getFullUrl(ph.search(mainData, ph.IFRAME)[1])
        if not url:
            return

        if 'season=' in url:
            sts, data = self.getPage(url + '&referrer=link')
            if sts:
                data = data.split('</body>', 1)[1]
                data = ph.find(data, ('<span', '>', 'server'), '</div>')[1]
                data = ph.findall(data, ('<span', '>'), '</span>')
                for item in data:
                    title = ph.clean_html(ph.getattr(item, 'title'))
                    if not title:
                        title = ph.clean_html(item)
                    url = self.getFullUrl(ph.search(item, ph.A)[1])
                    self.addVideo(MergeDicts(cItem, {'title': '%s: %s' % (cItem['title'], title), 'url': url}))
        else:
            self.addVideo(MergeDicts(cItem, {'url': url}))

    def joinLink(self, params):
        tab = []
        for key, value in iterDictItems(params[1]):
            tab.append('%s=%s' % (key, value))
        return params[0] + '?' + '&'.join(tab)

    def getFunctionCode(self, data, marker):
        funData = ''
        start = data.find(marker)
        idx = data.find('{', start) + 1
        num = 1
        while idx < len(data):
            if data[idx] == '{':
                num += 1
            elif data[idx] == '}':
                num -= 1
            if num == 0:
                funData = data[start:idx + 1]
                break
            idx += 1
        return funData

    def getLinksForVideo(self, cItem):
        linksTab = self.cacheLinks.get(cItem['url'], [])
        if linksTab:
            return linksTab

        url_data = cItem['url'].split('?', 1)
        if len(url_data) != 2:
            return []

        query = {}
        url_data[1] = url_data[1].split('&')
        for item in url_data[1]:
            item = item.split('=', 1)
            if len(item) != 2:
                continue
            query[item[0]] = item[1]
        url_data[1] = query

        url_data[1]['server'] = 'alternate'
        url_data[1]['referrer'] = 'link'
        url = self.joinLink(url_data)

        sts, data = self.getPage(url)
        if sts:
            e = '1' #ph.clean_html(ph.find(data, ('<span', '>', 'serverActive'), '</a>')[1])
            data = self.getFunctionCode(data, 'function streams(')
            jscode = 'efun=function(){},elem={slideToggle:efun,toggleClass:efun,hide:efun,removeAttr:efun,attr:efun},$=function(){return elem},$.post=function(){print(arguments[0])};document={"querySelector":function(){return {"textContent":"'
            jscode += e + '"};}};streams();' + data
            ret = js_execute(jscode)
            if ret['sts'] and 0 == ret['code']:
                url = self.getFullUrl(ret['data'].strip(), self.cm.meta['url'])
                sts, data = self.getPage(url)
                if sts:
                    printDBG(">>>")
                    printDBG(data)
                    data = ph.find(data, ('<ul', '>'), '</ul>', flags=0)[1].split('</li>')
                    for item in data:
                        tmp = ph.find(item, 'show_player(', ')', flags=0)[1].replace('\\"', '"').replace("\\'", "'")
                        url = self.getFullUrl(ph.search(item, '''['"]((?:https?:)?//[^'^"]+?)['"]''')[0])
                        if not url:
                            url = ph.search(item, ph.A)[1]
                        if url:
                            name = []
                            item = ph.findall(item, ('<span', '>'), '</span>', flags=0)
                            for t in item:
                                t = ph.clean_html(t)
                                if t:
                                    name.append(t)
                            linksTab.append({'name': ' | '.join(name), 'url': url, 'need_resolve': 1})

        url_data[1]['server'] = '1'
        url_data[1]['referrer'] = 'link'
        url = self.joinLink(url_data)
        linksTab.insert(0, {'name': 'Server 1', 'url': url, 'need_resolve': 1})

        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("KKisteAG.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        if 1 == self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        params = dict(self.defaultParams)
        params['header'] = MergeDicts(params['header'], {'Referer': self.getMainUrl()})
        videoLinks = []

        sts, data = self.getPage(videoUrl, params)
        if not sts:
            return videoLinks
        tmp = ph.find(data, ('<video', '>'), '</video>', flags=0)[1]
        tmp = ph.findall(tmp, '<source', '>', flags=0)
        for item in tmp:
            url = self.getFullUrl(ph.getattr(item, 'src'))
            type = ph.getattr(item, 'type')
            label = ph.getattr(item, 'data-res')
            if not label:
                label = ph.getattr(item, 'label')
            if not label:
                label = type
            videoLinks.append({'url': strwithmeta(url, {'Cookie': 'approve=1;'}), 'name': label})
        if not videoLinks:
            tmp = ph.find(data, 'show_player(', ')', flags=0)[1].replace('\\"', '"').replace("\\'", "'")
            url = self.getFullUrl(ph.search(tmp, '''['"]((?:https?:)?//[^'^"]+?)['"]''')[0])
            return self.up.getVideoLinkExt(url)

        return videoLinks

    def getArticleContent(self, cItem, data=None):
        printDBG("KKisteAG.getArticleContent [%s]" % cItem)
        retTab = []
        itemsList = []

        if not data:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts:
                return []
            data = re.sub("<!--[\s\S]*?-->", "", data)

        data = ph.find(data, ('<div', '>', 'content'), '<style', flags=0)[1]

        title = ph.clean_html(ph.find(data, ('<h', '>'), '</h', flags=0)[1])
        icon = ''
        desc = ph.clean_html(ph.find(data, ('<p', '>'), '</p>', flags=0)[1])

        data = ph.findall(data, ('<div', '>', 'extras'), '</div>', flags=0)
        for item in data:
            item = item.split(':', 1)
            label = ph.clean_html(item[0])
            value = ph.clean_html(item[-1])
            if label and value:
                itemsList.append((label + ':', value))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': ph.clean_html(title), 'text': ph.clean_html(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'}, 'list_items')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')

        elif category == 'list_items':
            self.listItems(self.currItem)

        elif category == 'list_items2':
            self.listItems2(self.currItem)

        elif category == 'explore_item':
            self.exploreItem(self.currItem)

    #SEARCH
        elif category == 'search':
            self.listSearchResult(MergeDicts(self.currItem, {'search_item': False, 'name': 'category'}), searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, KKisteAG(), True, [])

    def withArticleContent(self, cItem):
        return 'prev_url' in cItem
