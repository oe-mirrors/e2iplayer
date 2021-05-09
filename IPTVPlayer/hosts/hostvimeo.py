# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from datetime import timedelta
###################################################


def gettytul():
    return 'https://vimeo.com/'


class SuggestionsProvider:

    def __init__(self):
        self.cm = common()
        self.cm.HEADER = {'User-Agent': self.cm.getDefaultHeader()['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}

    def getName(self):
        return _("Vimeo Suggestions")

    def getSuggestions(self, text, locale):
        lang = locale.split('-', 1)[0]
        url = 'https://vimeo.com/search/autocomplete?q=' + urllib.quote(text)
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
            for item in json_loads(data)['options']:
                retList.append(item['text'])
            return retList
        return None


class VimeoCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'vimeo.com', 'cookie': 'vimeo.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://vimeo.com/'
        self.DEFAULT_ICON_URL = 'https://avemariaradio.net/wp-content/uploads/2017/03/vimeo_logo_header.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/vnd.vimeo.*+json;version=3.3', 'Origin': self.getMainUrl()[:-1]})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.api = {}
        self.typeMaps = {'clip': 'videos', 'ondemand': '', 'people': 'peoples', 'group': 'groups', 'channel': 'channels'}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("VimeoCom.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories'), 'url': self.getFullUrl('/categories')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]

        self.listsTab(MAIN_CAT_TAB, cItem)

    def _fillApiData(self, data):
        apiObj = re.compile('''vimeo\.config\.api\.([^\s^=]+?)\s*=\s*['"]([^'^"]+?)['"]''').findall(data)
        for item in apiObj:
            key = item[0]
            val = item[1]
            if key == 'url' and val != '':
                val = 'https://%s/' % val
            if key != '' and val != '':
                self.api[key] = val

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('vimeo\.config\s*?='), re.compile('};'))[1]
        jwt = self.cm.ph.getSearchGroups(data, '''['"]jwt['"]\s*:\s*['"]([^'^"]+?)['"]''')[0]
        if '' != jwt:
            self.api['jwt'] = jwt
        url = self.cm.ph.getSearchGroups(data, '''['"]url['"]\s*:\s*['"]([^'^"]+?)['"]''')[0]
        if '' != url:
            self.api['url'] = 'https://%s/' % url

    def listCategories(self, cItem, nextCategory):
        printDBG("VimeoCom.listLang [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'category category'), ('</a', '>'))
        for item in data:
            icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0]
            url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
            cat = url.split('/')
            if url.endswith('/'):
                cat = cat[-2]
            else:
                cat = cat[-1]
            title = self.cleanHtmlStr(item)
            params = {'good_for_fav': False, 'name': 'category', 'category': nextCategory, 'f_cat': cat, 'title': title, 'url': self.getFullUrl(url), 'icon': self.getFullIconUrl(icon)}
            self.addDir(params)

    def listTypes(self, cItem, nextCategory):
        printDBG("VimeoCom.listTypes [%s]" % cItem)

        if self.api.get('url', '') == '':
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            self._fillApiData(data)

        sts, data = self.getPage(cItem['url'] + '/videos')
        if not sts:
            return
        self._fillApiData(data)

        url = self.api.get('url', '') + 'search?_video_override=true&filter_type=clip&c=b&filter_category=%s&fields=facets.type' % cItem.get('f_cat', '')
        params = dict(self.defaultParams)
        params['header'] = self.AJAX_HEADER
        params['header']['Authorization'] = 'jwt %s' % (self.api.get('jwt', ''))

        sts, data = self.getPage(url, params)
        if not sts:
            return

        try:
            data = json_loads(data)
            for item in data['facets']['type']['options'][::-1]:
                if item['total'] == 0:
                    continue
                if item['name'] == 'ondemand':
                    continue

                title = self.cleanHtmlStr(item['text'])
                type = item['name']
                desc = str(item['total'])
                url = cItem['url'] + '/' + self.typeMaps.get(type, '')
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title, 'f_type': type, 'desc': desc})
                self.addDir(params)
        except Exception:
            printExc()

    def listSubCategories(self, cItem, nextCategory):
        printDBG("VimeoCom.listSubCategories [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self._fillApiData(data)

        url = self.api.get('url', '') + 'search?_video_override=true&filter_type=%s&page=1&per_page=1&c=b&facets=true&filter_category=%s&fields=search_web' % (cItem.get('f_type', ''), cItem.get('f_cat', ''))
        params = dict(self.defaultParams)
        params['header'] = self.AJAX_HEADER
        params['header']['Authorization'] = 'jwt %s' % (self.api.get('jwt', ''))

        sts, data = self.getPage(url, params)
        if not sts:
            return

        params = dict(cItem)
        params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('Any')})
        self.addDir(params)

        try:
            data = json_loads(data)
            for item in data['facets']['subcategory']['options']:
                title = self.cleanHtmlStr(item['text'])
                type = item['name']
                desc = str(item['total'])
                url = cItem['url'] + '?subcategory=' + type
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'f_subcategory': type, 'desc': desc})
                self.addDir(params)
        except Exception:
            printExc()

    def listSort(self, cItem, nextCategory):
        printDBG("VimeoCom.listSort [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self._fillApiData(data)

        data = self.cm.ph.getSearchGroups(data, '''"%s"\:\{"identifier"[^;]+?"sorts"\:\{([^;]+?\})\},''' % cItem.get('f_type', ''))[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '{', '}')
        try:
            data = json_loads('[%s]' % ','.join(data))
            for item in data:
                title = self.cleanHtmlStr(item['label'])
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'f_sort': item['identifier']})
                self.addDir(params)
        except Exception:
            printExc()

    def listItems(self, cItem):
        printDBG("VimeoCom.listItems [%s]" % cItem)
        ITEMS_PER_PAGE = 20

        page = cItem.pop('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self._fillApiData(data)

        url = self.api.get('url', '') + 'search?_video_override=true&filter_type=%s&page=%s&per_page=%s&sizes=250x115&fields=search_web' % (cItem.get('f_type', ''), page, ITEMS_PER_PAGE)
        sortMap = {'shortest': 'duration&direction=asc', 'longest': 'duration&direction=desc', 'alphabetical_desc': 'alphabetical&direction=desc', 'alphabetical_asc': 'alphabetical&direction=asc'}
        if cItem.get('f_type') == 'clip':
            url += '&filter_price=free'
        if cItem.get('f_query', '') != '':
            url += '&query=%s' % urllib.quote(cItem['f_query'])
        if cItem.get('f_sort', '') != '':
            url += '&sort=%s' % sortMap.get(cItem['f_sort'], cItem['f_sort'])
        if cItem.get('f_cat', '') != '':
            url += '&filter_category=%s' % cItem['f_cat']
        url += '&c=%s' % cItem.get('f_c', 'b')

        params = dict(self.defaultParams)
        params['header'] = self.AJAX_HEADER
        params['header']['Authorization'] = 'jwt %s' % (self.api.get('jwt', ''))

        sts, data = self.getPage(url, params)
        if not sts:
            return

        try:
            data = json_loads(data)
            printDBG(data)
            for item in data['data']:
                type = item['type']
                item = item[type]
                title = self.cleanHtmlStr(item['name'])
                url = self.getFullUrl(item['link'])
                icon = self.getFullIconUrl(item['pictures']['sizes'][-1]['link'])
                if 'channel' == type:
                    videosCounts = item['metadata']['connections']['videos']['total']
                    usersCounts = item['metadata']['connections']['users']['total']
                    desc = ['%s videos' % videosCounts, '%s followers' % usersCounts]
                    desc = ' | '.join(desc)
                elif 'group' == type:
                    videosCounts = item['metadata']['connections']['videos']['total']
                    usersCounts = item['metadata']['connections']['users']['total']
                    desc = ['%s videos' % videosCounts, '%s members' % usersCounts]
                    desc = ' | '.join(desc)
                elif 'people' == type:
                    videosCounts = item['metadata']['connections']['videos']['total']
                    usersCounts = item['metadata']['connections']['followers']['total']
                    desc = ['%s videos' % videosCounts, '%s followers' % usersCounts]
                    desc = ' | '.join(desc)
                elif 'clip' == type:
                    likesCounts = item['metadata']['connections']['likes']['total']
                    commentsCounts = item['metadata']['connections']['comments']['total']
                    duration = str(timedelta(seconds=item['duration']))
                    if duration.startswith('0:'):
                        duration = duration[2:]
                    desc = [duration, '%s likes' % likesCounts, '%s comments' % commentsCounts]
                    desc = ' | '.join(desc)
                    desc = self.cleanHtmlStr(item['user']['name']) + '[/br]' + desc
                    pass

                params = dict(cItem)
                params.pop('page', None)
                params.update({'good_for_fav': True, 'category': type, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
                if type == 'clip':
                    self.addVideo(params)
                else:
                    self.addDir(params)

            if data['total'] > data['page'] * data['per_page']:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listSort2(self, cItem, nextCategory):
        printDBG("VimeoCom.listSort2 [%s]" % cItem)

        sts, data = self.getPage(cItem['url'] + '/videos/format:detail')
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'js-sort'), ('</div', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            title = self.cleanHtmlStr(item)
            sort = self.cm.ph.getSearchGroups(item, '''/sort\:([^/]+?)/''')[0]
            params = dict(cItem)
            params.pop('page', None)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'f_sort': sort})
            self.addDir(params)

    def listItems2(self, cItem):
        printDBG("VimeoCom.listItems2 [%s]" % cItem)
        page = cItem.pop('page', 1)

        url = cItem['url'] + '/videos'
        if page > 1:
            url += '/page:%s' % page
        if cItem.get('f_sort', '') != '':
            url += '/sort:%s' % cItem['f_sort']
        url += '/format:detail'

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        if ('/page:%s/' % (page + 1)) in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'id="clip_'), ('</li', '>'))
        for item in data:
            icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0]
            url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
            url = url.split('/')[-1]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'title'), ('</p', '>'))[1])
            duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'duration'), ('</div', '>'))[1])
            desc = [duration]
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'meta'), ('</p', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
            for t in tmp:
                if '<time' in t:
                    t = t
                else:
                    label = self.cm.ph.getSearchGroups(t, '''\stitle=['"]([^'^"]+?)['"]''')[0]
                    t = '%s: %s' % (label, t)
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            desc = ' | '.join(desc)
            desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'description'), ('</p', '>'))[1])
            params = dict(cItem)
            params.pop('page', None)
            params.update({'good_for_fav': True, 'title': title, 'url': self.getFullUrl(url), 'icon': self.getFullIconUrl(icon), 'desc': desc})
            self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("VimeoCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        url = self.getFullUrl('/search?q=%s' % (urllib.quote(searchPattern)))
        params = dict(cItem)
        params.update({'url': url, 'category': 'list_items', 'f_type': searchType, 'f_c': 's', 'f_query': searchPattern})
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("VimeoCom.getLinksForVideo [%s]" % cItem)
        return self.up.getVideoLinkExt(cItem['url'])

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_types')
        elif category == 'list_types':
            self.listTypes(self.currItem, 'list_sub_cats')
        elif category == 'list_sub_cats':
            self.listSubCategories(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ['people', 'group', 'channel']:
            self.listSort2(self.currItem, 'list_items2')
        elif category == 'list_items2':
            self.listItems2(self.currItem)
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

    def getSuggestionsProvider(self, index):
        printDBG('Vimeo.getSuggestionsProvider')
        return SuggestionsProvider()


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, VimeoCom(), True, [])

        {'clip': 'videos', 'ondemand': '', 'people': 'peoples', 'group': 'groups', 'channel': 'channels'}

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_('Videos'), "clip"))
        searchTypesOptions.append((_('People'), "people"))
        searchTypesOptions.append((_('Channels'), "channel"))
        searchTypesOptions.append((_('Groups'), "group"))
        return searchTypesOptions
