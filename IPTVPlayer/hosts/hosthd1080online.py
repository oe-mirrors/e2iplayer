# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.hdgocc import HdgoccParser
###################################################


def gettytul():
    return 'https://hd1080.online/'


class HD1080Online(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'hd1080.online', 'cookie': 'hd1080.online.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://hd1080.online/'
        self.DEFAULT_ICON_URL = 'https://spliffmobile.com/1080-x-1920-wallpapers/hd/images/big-next-0001-focus.png'

        self.cacheLinks = {}
        self.hdgocc = HdgoccParser()

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem, nextCategory):
        printDBG("HD1080Online.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = ph.find(data, ('<ul', '>', 'first-menu'), '</ul>', flags=0)[1]
        tmp = ph.findall(tmp, ('<li', '>'), '</li>', flags=0)
        for item in tmp:
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            title = ph.clean_html(item)
            self.addDir(MergeDicts(cItem, {'category': nextCategory, 'url': url, 'title': title}))

        data = ph.find(data, ('<aside', '>'), '</aside>')[1]
        tmp = ph.rfindall(data, '</ul>', ('<div', '>'), flags=0)
        for section in tmp:
            section = section.split('</div>', 1)
            sTitle = ph.clean_html(section[0])
            section = ph.findall(section[-1], ('<li', '>'), '</li>', flags=0)
            subItems = []
            for item in section:
                url = self.getFullUrl(ph.search(item, ph.A)[1])
                title = ph.clean_html(item)
                subItems.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}))
            if len(subItems):
                self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'sub_items': subItems, 'title': sTitle}))

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubItems(self, cItem):
        printDBG("HD1080Online.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("HD1080Online.listItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = ph.find(data, ('<span', '>', 'pnext'), '</span>', flags=0)[1]
        nextPage = self.getFullUrl(ph.search(nextPage, ph.A)[1])

        data = ph.find(data, ('<div', '>', 'dle-content'), ('<aside', '>'))[1]
        data = ph.rfindall(data, '</div>', ('<div', '>', 'kino-item'))
        if data and nextPage:
            data[-1] = ph.find(data[-1], '<div', ('<div', '>', 'pagi-nav'))[1]

        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            icon = self.getFullIconUrl(ph.search(item, ph.IMG)[1])
            title = self.cleanHtmlStr(ph.find(item, ('<div', '>', 'title'), '</div>', flags=0)[1])

            desc = []
            tmp = ph.find(item, ('<ul', '>', 'lines'), '<ul', flags=0)[1]
            tmp = ph.findall(tmp, ('<li', '>'), '</li>', flags=0)
            for t in tmp:
                t = ph.clean_html(t)
                if t:
                    desc.append(t)

            # rating
            desc.append(ph.clean_html(ph.rfind(item, ('<div', '>', 'ratig-layer'), ('<b', '>'), flags=0)[1]))
            t = ph.clean_html(ph.find(item, ('<li', '>', 'current-rating'), '</li>', flags=0)[1])
            if t.isdigit():
                desc[-1] += ' %s/10' % str(int(t) / 10.0)

            desc.append(ph.clean_html(ph.find(item, ('<div', '>', 'desc'), '</div>', flags=0)[1]))
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}))

        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1}))

    def exploreItem(self, cItem, nextCategory):
        printDBG("HD1080Online.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        desc = []
        descObj = self.getArticleContent(cItem, data)[0]
        icon = descObj['images'][0]['url']
        baseTitle = descObj['title']
        for item in descObj['other_info']['custom_items_list']:
            desc.append(item[1])
        desc = ' | '.join(desc) + '[/br]' + descObj['text']

        data = ph.find(data, ('<div', '>', 'player-section'), ('<div', '>', 'ratig'), flags=0)[1]
        printDBG(data)
        titles = []
        tmp = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for t in tmp:
            titles.append(ph.clean_html(t))

        data = ph.findall(data, ('<div', '>', 'player-box'), '</div>', flags=0)

        for idx, item in enumerate(data):
            url = self.getFullUrl(ph.search(item, ph.IFRAME)[1])
            if not url:
                continue
            title = baseTitle
            if idx < len(titles):
                title += ' - ' + titles[idx]

            if ('/video/' in url and '/serials/' in url) or 'playlist' in url:
                url = strwithmeta(url, {'Referer': cUrl})
                seasons = self.hdgocc.getSeasonsList(url)
                for item in seasons:
                    self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'prev_url': cUrl, 'category': nextCategory, 'serie_title': baseTitle, 'title': _('Season %s') % item['title'], 'season_id': item['id'], 'url': item['url'], 'icon': icon, 'desc': desc}))

                if 0 == len(seasons):
                    seasonUrl = url
                    episodes = self.hdgocc.getEpiodesList(seasonUrl, -1)
                    for item in episodes:
                        title = '{0} - {1} - s01e{2} '.format(baseTitle, item['title'], str(item['id']).zfill(2))
                        self.addVideo({'good_for_fav': False, 'type': 'video', 'prev_url': cUrl, 'title': title, 'url': item['url'], 'icon': icon, 'desc': desc})
            elif '/video/' in url:
                self.addVideo({'good_for_fav': False, 'prev_url': cUrl, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            else: # trailes ??
                self.addVideo({'good_for_fav': False, 'prev_url': cUrl, 'title': title, 'url': url, 'icon': icon, 'desc': desc})

    def listEpisodes(self, cItem):
        printDBG("HD1080Online.listEpisodes")

        title = cItem['serie_title']
        id = cItem['season_id']

        episodes = self.hdgocc.getEpiodesList(cItem['url'], id)

        for item in episodes:
            self.addVideo(MergeDicts(cItem, {'title': '{0} - s{1}e{2} {3}'.format(title, str(id).zfill(2), str(item['id']).zfill(2), item['title']), 'url': item['url']}))

    def listSearchItems(self, cItem, nextCategory):
        printDBG("HD1080Online.listSearchItems")
        cItem = dict(cItem)
        page = cItem.get('page', 1)
        post_data = cItem['post_data']
        if page > 1:
            post_data.update({'search_start': page, 'full_search': 0, 'result_from': (page - 1) * 10 + 1})

        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = ph.find(data, ('<div', '>', 'pagi-nav'), '</div>', flags=0)[1]
        nextPage = (ph.search(nextPage, '<a[^>]+?>(\s*%d\s*)<' % (page + 1))[0])

        data = ph.findall(data, ('<a', '>', 'sres-wrap'), '</a>')
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            icon = self.getFullIconUrl(ph.search(item, ph.IMG)[1])
            title = self.cleanHtmlStr(ph.find(item, ('<h', '>'), '</h', flags=0)[1])

            desc = []
            desc.append(ph.clean_html(ph.find(item, ('<div', '>', 'date'), '</div>', flags=0)[1]))
            desc.append(ph.clean_html(ph.find(item, ('<div', '>', 'desc'), '</div>', flags=0)[1]))

            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}))

        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'page': page + 1}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        #searchPattern = 'Человек'
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        value = ph.search(data, '''var\s*?dle_login_hash\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
        post_data = {'query': searchPattern, 'user_hash': value, 'do': 'search', 'subaction': 'search', 'story': searchPattern}
        self.listSearchItems(MergeDicts(cItem, {'category': 'list_search_items', 'url': self.getFullUrl('/index.php?do=search'), 'post_data': post_data}), 'explore_item')

    def getLinksForVideo(self, cItem):
        linksTab = self.cacheLinks.get(cItem['url'], [])
        if linksTab:
            return linksTab

        linksTab = self.up.getVideoLinkExt(cItem['url'])
        for item in linksTab:
            item['need_resolve'] = 1

        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("HD1080Online.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        return [{'name': 'direct', 'url': videoUrl}]

    def getArticleContent(self, cItem, data=None):
        printDBG("HD1080Online.getArticleContent [%s]" % cItem)
        retTab = []
        itemsList = []

        if not data:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts:
                return []
            self.setMainUrl(self.cm.meta['url'])

        rating = ph.clean_html(ph.find(data, ('<div', '>', 'aggregateRating'), '</div>', flags=0)[1])

        data = ph.find(data, ('<div', '>', 'dle-content'), ('<', '>', 'kino-online'), flags=0)[1]
        title = self.cleanHtmlStr(ph.find(data, ('<h1', '>'), '</h1>', flags=0)[1])
        icon = self.getFullIconUrl(ph.search(data, ph.IMG)[1])
        desc = self.cleanHtmlStr(ph.find(data, ('<div', '>', 'description'), '</div>', flags=0)[1])

        data = ph.find(data, ('<ul', '>', 'opisanie'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<b', '</b>'), '</li>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            label = ph.clean_html(data[idx - 1])
            value = ph.clean_html(data[idx])
            if label and value:
                itemsList.append((label, value))
        itemsList.append((_('Rating'), rating))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

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

        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'list_search_items':
            self.listSearchItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')

        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, HD1080Online(), True, [])

    def withArticleContent(self, cItem):
        return True if 'explore_item' == cItem.get('category') or 'prev_url' in cItem else False
