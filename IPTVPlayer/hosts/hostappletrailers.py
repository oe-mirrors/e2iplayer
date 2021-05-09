# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://trailers.apple.com/'


class TrailersApple(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'TrailersApple', 'cookie': 'TrailersApple.cookie'})
        self.MAIN_URL = 'https://trailers.apple.com/'
        self.DEFAULT_ICON_URL = 'http://www.userlogos.org/files/logos/mafi0z/apple%20trailers.png'
        self.cacheLinks = {}

    def getFullUrl(self, url, baseUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace('&#038;', '&'), baseUrl)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG("TrailersApple.listMain")

        MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'Just Added', 'url': self.getFullUrl('/trailers/home/feeds/just_added.json')},
                        {'category': 'list_items', 'title': 'Exclusive', 'url': self.getFullUrl('/trailers/home/feeds/exclusive.json')},
                        {'category': 'list_items', 'title': 'Just HD', 'url': self.getFullUrl('/trailers/home/feeds/just_hd.json')},
                        {'category': 'list_items', 'title': 'Most Popular', 'url': self.getFullUrl('/trailers/home/feeds/most_pop.json')},
                        {'category': 'list_items', 'title': 'Movie Studios', 'url': self.getFullUrl('/trailers/home/feeds/studios.json')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCatItems(self, cItem, nextCategory):
        printDBG("TrailersApple.listCatItems")
        printDBG(cItem['c_tree'])
        try:
            cTree = cItem['c_tree']
            url = self.getFullUrl(self.cm.ph.getSearchGroups(cTree['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
            if url != '':
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('--All--'), 'url': url})
                self.addDir(params)

            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat'])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'list' not in item:
                    if url != '' and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    item['list'][0]['dat'] = item['dat']
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listSubItems(self, cItem):
        printDBG("TrailersApple.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("TrailersApple.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        try:
            data = byteify(json.loads(data))
            if 'results' in data:
                data = data['results']
            for item in data:
                printDBG(item)
                if len(item['trailers']) == 0:
                    continue
                title = self.cleanHtmlStr(item['title'])
                url = self.getFullUrl(item['location'])
                icon = self.getFullIconUrl(item['poster'])
                desc = []
                if 'releasedate' in item:
                    desc.append(item['releasedate'][:16])

                for it in [(_('Studio:'), 'studio'), (_('Director:'), 'director'), (_('Directors:'), 'directors'), (_('Genres:'), 'genres'), (_('Genre:'), 'genre'), (_('Actors:'), 'actors')]:
                    if it[1] not in item:
                        continue
                    if isinstance(item[it[1]], list):
                        value = ', '.join(item[it[1]])
                    else:
                        value = item[it[1]]
                    desc.append('%s %s' % (it[0], value))
                params = {'good_for_fav': True, 'name': 'category', 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                self.addDir(params)
        except Exception:
            printExc()

    def exploreItem(self, cItem):
        printDBG("TrailersApple.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        filmId = self.cm.ph.getSearchGroups(data, '''FilmId\s*=\s*['"](\d+)['"]''')[0]

        sts, data = self.getPage(self.getFullUrl('/trailers/feeds/data/%s.json' % filmId))
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            key = 0
            for item in data['clips']:
                title = item['title']
                desc = item['runtime']
                icon = self.getFullIconUrl(item['thumb'])

                urls = []
                for version, versionData in item.get('versions', {}).iteritems():
                    for size, sizeData in versionData.get('sizes', {}).iteritems():
                        url = sizeData.get('src')
                        if not url:
                            continue
                        urls.append({
                            'name': '%s-%s' % (version, size),
                            'url': self.getFullUrl(re.sub(r'_(\d+p\.mov)', r'_h\1', url)),
                            'width': int(sizeData.get('width')),
                            'height': int(sizeData.get('height')),
                            'language': version[:2],
                            'need_resolve': 1,
                        })
                key += 1
                url = cItem['url'] + '#clip_' + str(key)
                self.cacheLinks[url] = urls
                params = dict(cItem)
                params.update({'good_for_fav': False, 'url': url, 'title': cItem['title'] + ': ' + title, 'icon': icon, 'desc': desc})
                self.addVideo(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)

        url = self.getFullUrl('/trailers/home/scripts/quickfind.php?q=') + urllib.quote_plus(searchPattern)
        self.listItems({'url': url}, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("TrailersApple.getLinksForVideo [%s]" % cItem)
        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("TrailersApple.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        return [{'name': 'direct', 'url': videoUrl}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

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
        CHostBase.__init__(self, TrailersApple(), True, [])
