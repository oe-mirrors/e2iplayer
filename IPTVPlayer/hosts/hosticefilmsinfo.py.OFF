# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
import random
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.icefilmsinfo_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                            ("proxy_1", _("Alternative proxy server (1)")),
                                                                                            ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.icefilmsinfo_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.icefilmsinfo_proxy))
    if config.plugins.iptvplayer.icefilmsinfo_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.icefilmsinfo_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'http://icefilms.info/'


class IceFilms(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'IceFilms.tv', 'cookie': 'IceFilms.cookie'})
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.cm.HEADER = self.HEADER # default header
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'http://whatyouremissing.weebly.com/uploads/1/9/6/3/19639721/144535_orig.jpg'
        self.MAIN_URL = None

    def selectDomain(self):
        domains = ['http://www.icefilms.info/', 'https://icefilms.unblocked.gdn/', 'https://icefilms.unblocked.at/']
        domain = config.plugins.iptvplayer.icefilmsinfo_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and 'donate.php' in data:
                if self.setMainUrl(self.cm.meta['url']):
                    break

        if self.MAIN_URL == None:
            self.MAIN_URL = 'http://www.icefilms.info/'

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('TV Shows'), 'url': self.getFullUrl('tv/popular/1'), 'f_idx': 0},
                             {'category': 'list_filters', 'title': _('Movies'), 'url': self.getFullUrl('movies/popular/1'), 'f_idx': 0},
                             {'category': 'list_filters', 'title': _('Stand-Up'), 'url': self.getFullUrl('standup/popular/1'), 'f_idx': 0},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        self.cacheFilters = {}
        self.cacheLinks = {}
        self.cacheSeries = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        proxy = config.plugins.iptvplayer.icefilmsinfo_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    #def getFullIconUrl(self, url, baseUrl=None):
    #    return ''

    def _getAttrVal(self, data, attr):
        val = self.cm.ph.getSearchGroups(data, '[<\s][^>]*' + attr + '=([^\s^>]+?)[\s>]')[0].strip()
        if len(val) > 2:
            if val[0] in ['"', "'"]:
                val = val[1:]
            if val[-1] in ['"', "'"]:
                val = val[:-1]
            return val
        return ''

    def listFilters(self, cItem, nextCategory):
        printDBG("IceFilms.listFilters cItem[%s] nextCategory[%s]" % (cItem, nextCategory))
        cacheKey = '{0}_{1}'.format(cItem['f_idx'], cItem['url'])
        tab = self.cacheFilters.get(cItem['url'], {}).get('tab', [])
        if 0 == len(tab):
            self.cacheFilters[cacheKey] = {}
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '''<div class="menu submenu''', '</div>', withMarkers=True)
            numOfTabs = len(data)
            if numOfTabs <= cItem['f_idx']:
                self.listItems(cItem, 'list_episodes')
                return
            data = data[cItem['f_idx']]
            data = data.split('</a>')
            tab = []
            firstItem = True
            for item in data:
                if firstItem:
                    item = item[item.find('>') + 1:]
                    firstItem = False
                # there can be sub item
                item = item.split('</b>')
                for idx in range(len(item)):
                    if not item[idx].strip().startswith('<b'):
                        url = self.getFullUrl(self._getAttrVal(item[idx], 'href'))
                    else:
                        url = cItem['url']
                    title = self.cleanHtmlStr(item[idx])
                    if self.cm.isValidUrl(url):
                        params = dict(cItem)
                        params.update({'title': title, 'url': url})
                        if 'rand.php' in url:
                            params.pop('f_idx', None)
                            params['category'] = 'list_random'
                        elif numOfTabs - 1 > cItem['f_idx']:
                            params['f_idx'] += 1
                        else:
                            params.pop('f_idx', None)
                            params['category'] = nextCategory
                        tab.append(params)
            if len(tab):
                self.cacheFilters[cacheKey]['tab'] = tab

        tab = self.cacheFilters.get(cacheKey, {}).get('tab', [])
        for params in tab:
            self.currList.append(params)

    def listRandom(self, cItem, nextCategory):
        printDBG("IceFilms.listRandom")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        url = self.cm.meta['url']

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<title>', '</span>', False)[1]
        mainDesc = self.cleanHtmlStr(tmp)
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span', '</span>')[1])

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'imdb', '>')[1]
        id = self._getAttrVal(tmp, 'id')

        params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': mainDesc}
        if id != '':
            params.update({'imdb_id': id, 'icon': 'http://www.imdb.com/title/tt%s/?fake=need_resolve.jpeg' % id})
        if '/tv/' not in url:
            self.addVideo(params)
        else:
            params['category'] = nextCategory
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("IceFilms.listItems")

        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<span class="?list"?'), re.compile('</span>'), withMarkers=False)[1]
        data = data.split('</h3>')
        if len(data) and '<h3' in data[0]:
            desc = self.cleanHtmlStr(data[0])
        else:
            desc = ''
        for item in data:
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", '<br>', withMarkers=True)
            for tmpItem in tmpTab:
                url = self._getAttrVal(tmpItem, 'href')
                id = self._getAttrVal(tmpItem, 'id')
                title = self.cleanHtmlStr(tmpItem)
                params = {'good_for_fav': True, 'title': title, 'url': self.getFullUrl(url), 'desc': desc}
                if id != '':
                    params.update({'imdb_id': id, 'icon': 'http://www.imdb.com/title/tt%s/?fake=need_resolve.jpeg' % id})
                if '/tv/' not in url:
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)
            desc = item.rfind('<h3')
            if desc >= 0:
                desc = self.cleanHtmlStr(item[desc:])
            else:
                desc = ''

    def listEpisodes(self, cItem):
        printDBG("IceFilms.listEpisodes")
        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<title>', '<div', False)[1]
        mainDesc = self.cleanHtmlStr(tmp)

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'imdb', '>')[1]
        id = self._getAttrVal(tmp, 'id')
        printDBG('series old imdb_id[%s]' % cItem.get('imdb_id', ''))
        printDBG('series new imdb_id[%s]' % id)
        if id == '':
            id = cItem.get('imdb_id', '')

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<span class="?list"?'), re.compile('</span>'), withMarkers=False)[1]
        data = data.split('</h3>')
        for item in data:
            desc = mainDesc
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", '<br>', withMarkers=True)
            for tmpItem in tmpTab:
                url = self._getAttrVal(tmpItem, 'href')
                title = self.cleanHtmlStr(tmpItem)
                params = {'good_for_fav': True, 'title': '{0}: {1}'.format(cItem['title'], title), 'url': self.getFullUrl(url), 'desc': desc}
                if id != '':
                    params.update({'imdb_id': id, 'icon': 'http://www.imdb.com/title/tt%s/?fake=need_resolve.jpeg' % id})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("IceFilms.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        baseUrl = self.getFullUrl('/search.php?q=%s&x=0&y=0' % urllib_quote_plus(searchPattern))
        sts, data = self.getPage(baseUrl)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div class=['"]?number['"]?'''), re.compile('</table>'), withMarkers=True)[1]
        data = data.split('</tr>')
        for item in data:
            url = self.getFullUrl(self._getAttrVal(item, 'href'))
            if not self.cm.isValidUrl(url):
                continue
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('''<div class=['"]?desc['"]?'''), re.compile('</div>'), withMarkers=True)[1])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>', withMarkers=True)[1])
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc}
            if '/tv/' not in url:
                self.addVideo(params)
            else:
                params['category'] = 'list_episodes'
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("IceFilms.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if len(self.cacheLinks.get(cItem['url'], [])):
            return self.cacheLinks[cItem['url']]

        rm(self.COOKIE_FILE)
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        url = self.getFullUrl(url)

        sts, data = self.getPage(url, self.defaultParams)
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenMarkers(data, 'id="srclist"', 'These links brought')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'ripdiv', '</div>')
        for item in data:
            mainTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<b', '</b>')[1])

            sourcesTab = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</i>')
            for source in sourcesTab:
                sourceId = self.cm.ph.getSearchGroups(source, '''onclick=['"]go\((\d+)\)['"]''')[0]
                if sourceId == '':
                    continue
                sourceName = self.cleanHtmlStr(clean_html(source.replace('</a>', ' ')))

                urlTab.append({'name': '[{0}] {1}'.format(mainTitle, sourceName), 'url': strwithmeta(sourceId, {'url': cItem['url']}), 'need_resolve': 1})

        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("IceFilms.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            key = self.cacheLinks.keys()[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break

        sourceId = videoUrl
        url = strwithmeta(videoUrl).meta.get('url')

        sts, data = self.getPage(url, self.defaultParams)
        if not sts:
            return []

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        frameUrl = self.getFullUrl(url)

        sts, data = self.getPage(frameUrl, self.defaultParams)
        if not sts:
            return []

        baseUrl = '/membersonly/components/com_iceplayer/video.php-link.php?s=%s&t=%s'
        secret = self.cm.ph.getSearchGroups(data, '<input[^>]+?name="secret"[^>]+?value="([^"]+?)"')[0]

        try:
            match = re.search('lastChild\.value="([^"]+)"(?:\s*\+\s*"([^"]+))?', data)
            secret = ''.join(match.groups(''))
        except Exception:
            printExc()
            return []

        captcha = self.cm.ph.getSearchGroups(data, '<input[^>]+?name="captcha"[^>]+?value="([^"]+?)"')[0]
        iqs = self.cm.ph.getSearchGroups(data, '<input[^>]+?name="iqs"[^>]+?value="([^"]+?)"')[0]
        uri = self.cm.ph.getSearchGroups(data, '<input[^>]+?name="url"[^>]+?value="([^"]+?)"')[0]
        try:
            t = self.cm.ph.getSearchGroups(data, '"&t=([^"]+)')[0]
        except Exception:
            printExc()
            return []

        try:
            baseS = int(self.cm.ph.getSearchGroups(data, '(?:\s+|,)s\s*=(\d+)')[0])
        except Exception:
            printExc()
            return []

        try:
            baseM = int(self.cm.ph.getSearchGroups(data, '(?:\s+|,)m\s*=(\d+)')[0])
        except Exception:
            printExc()
            return []

        s = baseS + random.randint(3, 1000)
        m = baseM + random.randint(21, 1000)
        #url = self.getFullUrl(baseUrl % (sourceId, s, m, secret, t))
        url = self.getFullUrl(baseUrl % (sourceId, t))

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = frameUrl

        sts, data = self.getPage(url, params, post_data={'id': sourceId, 's': s, 'iqs': iqs, 'url': uri, 'm': m, 'captcha': ' ', 'secret': secret, 't': t})
        if not sts:
            return []
        printDBG(data)

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', '_blank'), ('</a', '>'))
        for item in tmp:
            videoUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if 1 == self.up.checkHostSupport(videoUrl):
                urlTab.extend(self.up.getVideoLinkExt(videoUrl))

        videoUrl = urllib_unquote(data.split('?url=')[-1].strip())
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("IceFilms.getArticleContent [%s]" % cItem)
        retTab = []

        if 'imdb_id' not in cItem:
            return retTab

        url = 'http://www.imdb.com/title/tt{0}/'.format(cItem['imdb_id'])
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
            title = cItem['desc']

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
        if self.MAIN_URL == None:
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'list_filters' == category:
            self.listFilters(self.currItem, 'list_items')
        elif 'list_random' == category:
            self.listRandom(self.currItem, 'list_episodes')
        elif 'list_items' == category:
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
        CHostBase.__init__(self, IceFilms(), True, [])

    def withArticleContent(self, cItem):
        printDBG(cItem)

        if cItem['type'] != 'video' and cItem.get('category', '') != 'list_episodes':
            return False
        return True
