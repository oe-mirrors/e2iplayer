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
import re
import urllib
from urlparse import urlparse
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://tainieskaiseires.tv/'


class TainieskaiSeiresTv(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tainieskaiseires.tv', 'cookie': 'tainieskaiseires.tv.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://www.tainieskaiseires.tv/wp-content/uploads/2017/01/Logo-002.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*'})
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.seasonsCache = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def selectDomain(self):
        domain = 'http://www.tainieskaiseires.tv/'
        addParams = dict(self.defaultParams)
        addParams['with_metadata'] = True

        sts, data = self.getPage(domain, addParams)
        if sts:
            self.MAIN_URL = self.cm.getBaseUrl(data.meta['url'])
        else:
            self.MAIN_URL = domain

        self.MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]

    def listMainMenu(self, cItem):
        printDBG("TainieskaiSeiresTv.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'classic-dropdown'), ('</nav', '>'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = 'list_categories'
                    self.listCategories(params, 'list_items')
                except Exception:
                    printExc()
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("TainieskaiSeiresTv.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item['dat'], '<a', '</a>')[1])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.pop('c_tree', None)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    params = dict(cItem)
                    params.pop('c_tree', None)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
            url = cItem.get('url', '')
            if len(self.currList) and self.cm.isValidUrl(url) and '@' not in url:
                params = dict(cItem)
                params.pop('c_tree', None)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('--All--'), 'url': url})
                self.currList.insert(0, params)
        except Exception:
            printExc()

    def listItems(self, cItem, nextCategory1, nextCategory2):
        printDBG("TainieskaiSeiresTv.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        parsedUri = urlparse(cItem['url'])
        if parsedUri.path == '/' and parsedUri.query == '':
            data = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', '/category/'), ('</strong', '>'))
            printDBG(data)
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if url == '':
                    continue
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': title, 'url': url, 'icon': icon})
                self.addDir(params)
        elif '/category/' in cItem['url'] or '/?s=' in cItem['url']:
            page = cItem.get('page', 1)
            data = self.cm.ph.getDataBeetwenMarkers(data, '<section', '</section>')[1]
            nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagenavi'), ('</div', '>'))[1]
            nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''\shref=['"]([^"^']*?/page/%s/[^"^']*?)['"]''' % (page + 1))[0])

            data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('<div', '>', 'clearfix'), ('<div', '>', 'video-item'))
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                if url == '':
                    continue
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'fa-eye'), ('</span', '>'))[1])
                desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])

                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory2, 'title': title, 'url': url, 'info_url': url, 'icon': icon, 'desc': desc})
                self.addDir(params)

            if nextPage != '':
                params = dict(cItem)
                params.update({'title': _("Next page"), 'url': nextPage, 'page': page + 1})
                self.addDir(params)
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'smart-box '), ('<div', '>', '"clear"'))
            for section in data:
                sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
                itemsTab = []
                section = self.cm.ph.getAllItemsBeetwenNodes(section, ('<div', '>', 'video-item'), ('</a', '>'))
                for item in section:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                    if url == '':
                        continue
                    icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0])
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^"^']+?)['"]''')[0])
                    if title == '':
                        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\salt=['"]([^"^']+?)['"]''')[0])
                    desc = self.cleanHtmlStr(item)
                    itemsTab.append({'title': title, 'url': url, 'info_url': url, 'icon': icon, 'desc': desc})
                if len(itemsTab):
                    params = dict(cItem)
                    params.update({'title': sTitle, 'category': nextCategory1, 'items_tab': itemsTab})
                    self.addDir(params)

    def listSectionItems(self, cItem, nextCategory):
        printDBG("TainieskaiSeiresTv.listSectionItems [%s]" % cItem)
        cItem = dict(cItem)
        listTab = cItem.pop('items_tab', [])
        cItem.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(listTab, cItem)

    def exploreItem(self, cItem, nextCategory):
        printDBG("TainieskaiSeiresTv.exploreItem")
        self.cacheLinks = {}
        linksTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        baseTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h1>', '</h1>', '<strong'), ('<', '>'))[1])
        if baseTitle == '':
            baseTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h', '>', 'entry-title'), ('</h', '>'))[1])
        if baseTitle == '':
            baseTitle = cItem['title']

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player-embed'), ('', '</div>'))[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<(?:iframe|embed)[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        if self.cm.isValidUrl(url):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s %s' % (_('[trailer]'), cItem['title']), 'url': url})
            self.addVideo(params)

        reObjSeasons = re.compile('(<strong[^>]*?>[^>]*?SEASON[^>]*?</strong>)', re.IGNORECASE)
        seasonsData = self.cm.ph.getDataBeetwenReMarkers(data, reObjSeasons, re.compile('<div[^>]+?item\-tax\-list[^>]+?>'))[1]
        seasonsData = reObjSeasons.split(seasonsData)
        if len(seasonsData):
            del seasonsData[0]
        if 0 == len(seasonsData):
            seasonsData = self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>')[1]
            seasonsData = self.cm.ph.getAllItemsBeetwenMarkers(seasonsData, '<td', '</td>')

        if 0 == len(seasonsData):
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'href'), ('</a', '>'))
            for item in data:
                name = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                if 1 == self.up.checkHostSupport(url):
                    linksTab.append({'name': name, 'url': url, 'need_resolve': 1})
        elif 'SEASON' in self.cleanHtmlStr(seasonsData[0]).upper():
            seasonsKeys = []
            self.seasonsCache = {}
            domain = self.up.getDomain(self.getMainUrl())
            reSeasonObj = re.compile('SEASON\s+?[0-9]+', re.IGNORECASE)
            reEpisodeObj = re.compile('\sE[0-9]+(?:\-E?[0-9]+)?', re.IGNORECASE)
            for idx in range(0, len(seasonsData), 2):
                sTitle = self.cleanHtmlStr(seasonsData[idx]).replace("Ε", "E")
                sSubTitle = self.cleanHtmlStr(reSeasonObj.sub('', sTitle))
                seasonId = self.cleanHtmlStr(self.cm.ph.getSearchGroups(sTitle, 'SEASON\s*?([0-9]+(?:\-[0-9]+)?)', 1, True)[0])
                printDBG("++ SEASON ID -> \"%s\" \"%s\"" % (seasonId, sSubTitle))
                if seasonId not in seasonsKeys:
                    seasonsKeys.append(seasonId)
                    self.seasonsCache[seasonId] = {'title': sTitle.replace(sSubTitle, ''), 'season_id': seasonId, 'episodes': []}

                tmp = self.cm.ph.getAllItemsBeetwenMarkers(seasonsData[idx + 1], '<a', '</a>')
                for item in tmp:
                    eTitle = ' ' + self.cleanHtmlStr(item).replace("Ε", "E")
                    eSubTitle = self.cleanHtmlStr(reEpisodeObj.sub('', eTitle))
                    episodeId = self.cleanHtmlStr(self.cm.ph.getSearchGroups(eTitle, '\s(E[0-9]+(?:\-E?[0-9]+)?)', 1, True)[0])
                    printDBG("+++++++++++++++++ EPISODE ID \"%s\"-> \"%s\"" % (eTitle, episodeId))
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                    if url == '':
                        continue

                    fakeUrl = cItem['url'] + '#season=%s&episode=%s' % (seasonId, eTitle)
                    if fakeUrl not in self.cacheLinks:
                        self.cacheLinks[fakeUrl] = []
                        if seasonId != '' and episodeId != '':
                            title = '%s - S%s%s %s' % (baseTitle, seasonId.zfill(2), episodeId, eSubTitle)
                        else:
                            title = ('%s - %s %s') % (baseTitle, sTitle.replace(sSubTitle, ''), eTitle)
                        self.seasonsCache[seasonId]['episodes'].append({'title': title, 'episode_id': seasonId, 'url': fakeUrl})

                    if domain not in url:
                        name = self.up.getHostName(url)
                        if sSubTitle != '':
                            name += ' ' + sSubTitle
                    else:
                        name = sSubTitle
                    self.cacheLinks[fakeUrl].append({'name': name, 'url': url, 'need_resolve': 1})

            for seasonKey in seasonsKeys:
                season = self.seasonsCache[seasonKey]
                if 0 == len(season['episodes']):
                    continue
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': season['title'], 'season_id': season['season_id']})
                self.addDir(params)

            if 1 == len(self.currList):
                cItem = self.currList.pop()
                self.listEpisodes(cItem)
        else:
            for idx in range(0, len(seasonsData), 2):
                quality = self.cleanHtmlStr(seasonsData[idx])
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(seasonsData[idx + 1], '<a', '</a>')
                for item in tmp:
                    name = self.cleanHtmlStr(item)
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                    linksTab.append({'name': '%s - %s' % (quality, name), 'url': url, 'need_resolve': 1})

        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': baseTitle})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("TainieskaiSeiresTv.listEpisodes")
        listTab = self.seasonsCache[cItem['season_id']]['episodes']
        cItem = dict(cItem)
        cItem.update({'good_for_fav': False})
        self.listsTab(listTab, cItem, 'video')

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TainieskaiSeiresTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'list_section_items', 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("TainieskaiSeiresTv.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("TainieskaiSeiresTv.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        subTracks = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        domain = self.up.getDomain(self.getMainUrl())
        if domain in videoUrl:
            sts, data = self.getPage(videoUrl)
            if not sts:
                return

            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player-embed'), ('', '</div>'))[1]
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("TainieskaiSeiresTv.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem.get('info_url', ''))
        if not sts:
            return retTab

        data = self.cm.ph.rgetDataBeetwenNodes(data, ('</table', '>'), ('<table', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<th', '</th>')

        if len(tmp) > 2:
            desc = tmp[1].split('</span>', 1)
            title = self.cleanHtmlStr(desc[0])
            desc = self.cleanHtmlStr(desc[-1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tmp[0], '''\ssrc=['"]([^'^"]+?)['"]''')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', '')

        descData = self.cm.ph.getAllItemsBeetwenMarkers(tmp[-1], '<span', '</span>')
        descTabMap = {"Ετος παραγωγής": "year",
                      "Βαθμολογία": "rated",
                      "Ηθοποιοί": "actors",
                      "Κατηγορία": "genres",
                      "Σκηνοθεσία": "director",
                     }

        otherInfo = {}
        for idx in range(1, len(descData), 2):
            key = self.cleanHtmlStr(descData[idx - 1])
            val = self.cleanHtmlStr(descData[idx])
            if val.endswith(','):
                val = val[:-1]
            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = val
                except Exception:
                    continue

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_section_items', 'explore_item')
        elif category == 'list_section_items':
            self.listSectionItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, TainieskaiSeiresTv(), True, [])

    def withArticleContent(self, cItem):
        if 'info_url' in cItem:
            return True
        return False
