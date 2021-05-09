# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
#from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2helper import CaptchaHelper

from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry

###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.api_key_9kweu = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_2captcha = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.cineto_bypassrecaptcha = ConfigSelection(default="", choices=[("", _("None")),
                                                                                          ("9kw.eu", "https://9kw.eu/"),
                                                                                          ("2captcha.com", "http://2captcha.com/")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Captcha solving service"), config.plugins.iptvplayer.cineto_bypassrecaptcha))
    if config.plugins.iptvplayer.cineto_bypassrecaptcha.value == '9kw.eu':
        optionList.append(getConfigListEntry(_("%s API KEY") % '    ', config.plugins.iptvplayer.api_key_9kweu))
    elif config.plugins.iptvplayer.cineto_bypassrecaptcha.value == '2captcha.com':
        optionList.append(getConfigListEntry(_("%s API KEY") % '    ', config.plugins.iptvplayer.api_key_2captcha))
    return optionList
###################################################


def gettytul():
    return 'https://cine.to/'


class CineTO(CBaseHostClass, CaptchaHelper):
    LINKS_CACHE = {}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cine.to', 'cookie': 'cine.to.cookie'})
        self.DEFAULT_ICON_URL = 'https://cine.to/opengraph.jpg'
        self.USER_AGENT = 'Mozilla / 5.0 (SMART-TV; Linux; Tizen 2.4.0) AppleWebkit / 538.1 (KHTML, podobnie jak Gecko) SamsungBrowser / 1.1 TV Safari / 538.1'
        self.MAIN_URL = 'https://cine.to/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Accept-Language': GetDefaultLang()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheFilters = {}
        self.cacheLinks = {}
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'raw_post_data': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def _getStr(self, item, key, default=''):
        if key not in item:
            val = default
        if item[key] == None:
            val = default
        val = str(item[key])
        return self._(val)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getSearchParams(self, cItem, count=1):
        post_data = {}
        post_data['kind'] = cItem.get('f_kind', 'all')
        post_data['genre'] = cItem.get('f_genres', '0')
        post_data['rating'] = cItem.get('f_rating', '1')

        sYear = cItem.get('f_year', self.cacheFilters['year'][-1]['f_year'])
        eYear = cItem.get('f_year', self.cacheFilters['year'][1]['f_year'])

        post_data['term'] = cItem.get('f_term', '')
        post_data['page'] = cItem.get('page', 1)
        post_data['count'] = count

        post_data = urllib.urlencode(post_data) + '&year%5B%5D={0}&year%5B%5D={1}'.format(sYear, eYear)
        printDBG(post_data)
        return post_data

    def listMainMenu(self, cItem, nextCategory):
        self.cacheFilters = {'kind': [], 'genres': [], 'rating': [], 'year': []}

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return []

        try:
            # kind
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="kind">', '</ul>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<label', '</label>')
            for item in tmp:
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                title = self.cleanHtmlStr(item)
                self.cacheFilters['kind'].append({'f_kind': value, 'title': title})

            # genres
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="genres"', '</ul>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            for item in tmp:
                value = self.cm.ph.getSearchGroups(item, '''data-id=['"]([^'^"]+?)['"]''')[0]
                title = self.cleanHtmlStr(item)
                self.cacheFilters['genres'].append({'f_genres': value, 'title': title})

            # rating
            for idx in range(10, 0, -1):
                value = str(idx)
                title = _('Rating %s') % idx
                self.cacheFilters['rating'].append({'f_rating': value, 'title': title})
            self.cacheFilters['rating'].insert(0, {'f_rating': 1, 'title': _('Any')})

            # year
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="year"', '</ul>')[1]
            end = int(self.cm.ph.getSearchGroups(tmp, '''data-end=['"]([0-9]+?)['"]''')[0])
            start = int(self.cm.ph.getSearchGroups(tmp, '''data-start=['"]([0-9]+?)['"]''')[0])
            for idx in range(end, start - 1, -1):
                value = str(idx)
                title = _('Year %s') % idx
                self.cacheFilters['year'].append({'f_year': value, 'title': title})
            self.cacheFilters['year'].insert(0, {'title': _('Any')})
        except Exception:
            printExc()
            return

        params = dict(cItem)
        params['category'] = nextCategory
        self.listsTab(self.cacheFilters['kind'], params)
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listGenres(self, cItem, nextCategory):
        printDBG("CineTO.listGenres")

        url = self.getFullUrl('/request/search')
        post_data = self._getSearchParams(cItem)
        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return []

        cItem = dict(cItem)
        cItem['category'] = nextCategory

        try:
            data = json_loads(data, '', True)['genres']
            for item in self.cacheFilters['genres']:
                params = dict(cItem)
                params.update(item)
                if item['f_genres'] in data:
                    params['title'] = item['title'] + (' (%s)' % data.get(item['f_genres'], '0'))
                self.addDir(params)
        except Exception:
            printExc()

    def listRating(self, cItem, nextCategory):
        printDBG("CineTO.listRating")

        params = dict(cItem)
        params['category'] = nextCategory
        self.listsTab(self.cacheFilters['rating'], params)

    def listYear(self, cItem, nextCategory):
        printDBG("CineTO.listYear")

        params = dict(cItem)
        params['category'] = nextCategory
        self.listsTab(self.cacheFilters['year'], params)

    def _addItem(self, item, cItem, nextCategory):
        printDBG("------------------------------------")
        printDBG(item)
        title = self.cleanHtmlStr(item['title'])
        if 'cover' in item:
            icon = self.getFullIconUrl(item['cover'])
        else:
            icon = 'https://s.cine.to/cover/%s.jpg' % str(item['imdb']).zfill(7)

        descTab = []
        for it in ['year', 'quality', 'language']:
            tmp = item.get(it, '')
            if it == 'language':
                tmp = ', '.join(re.compile('\-([^\,]+?)\,').findall(tmp + ','))
            if tmp != '':
                descTab.append(tmp)
        desc = ' | '.join(descTab)

        params = dict(cItem)
        params.update({'good_for_fav': True, 'title': title, 'imdb': item['imdb'], 'icon': icon, 'desc': desc})
        params['category'] = nextCategory
        self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("CineTO.listItems [%s]" % cItem)
        ITEMS_PER_PAGE = 30
        page = cItem.get('page', 1)

        url = self.getFullUrl('/request/search')
        post_data = self._getSearchParams(cItem, count=ITEMS_PER_PAGE)
        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return []

        try:
            data = json_loads(data, noneReplacement='', baseTypesAsString=True)
            for item in data['entries']:
                self._addItem(item, cItem, nextCategory)
        except Exception:
            printExc()

        nextPage = False
        try:
            if int(data['pages']) > (page + 1):
                nextPage = True
        except Exception:
            printExc()

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("CineTO.exploreItem")

        url = self.getFullUrl('/request/entry')
        post_data = 'ID=%s' % cItem['imdb']

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return []

        try:
            data = json_loads(data, noneReplacement='', baseTypesAsString=True)['entry']
            icon = self.getFullIconUrl(data.get('cover', cItem.get('icon', '')))
            printDBG("+++++++++++++++++++++++++++++++++++++++")
            printDBG(data)
            printDBG("+++++++++++++++++++++++++++++++++++++++")

            descTab = []
            tmp = data.get('year', '')
            if tmp != '':
                descTab.append(tmp)

            tmp = data.get('duration', '')
            if tmp != '':
                descTab.append('~%s min.' % tmp)

            tmp = data.get('rating', '')
            if tmp != '':
                descTab.append(tmp)

            tmp = ', '.join(data.get('genres', []))
            if tmp != '':
                descTab.append(tmp)

            langIdsTab = []
            for lang in data['lang']:
                langIdsTab.append(str(lang))
            langsIdDict = {'en': '1', 'de': '2'}
            langsDict = {'1': 'en', '2': 'de'}

            # move better language at top
            defIdLang = langsIdDict.get(GetDefaultLang(), '1')
            if defIdLang not in langIdsTab:
                defIdLang = '1'

            if defIdLang in langIdsTab:
                langIdsTab.remove(defIdLang)
                langIdsTab.insert(0, defIdLang)

            for langId in langIdsTab:
                lang = langsDict.get(langId, langId)
                langName = lang
                trailerUrl = data.get('trailer_%s' % lang, '')
                desc = ' | '.join(descTab) + '[/br]' + data.get('plot_%s' % lang, '')
                baseTitle = data['title']

                if trailerUrl != '':
                    url = 'https://www.youtube.com/watch?v=%s' % trailerUrl
                    title = '[TRAILER] [%s] %s' % (langName, baseTitle)
                    params = {'title': title, 'imdb': cItem['imdb'], 'f_lang_id': langId, 'f_lang': lang, 'url': url, 'icon': icon, 'desc': desc}
                    self.addVideo(params)

                title = '[%s] %s (%s)' % (langName, baseTitle, data.get('year', ''))
                params = {'title': title, 'imdb': cItem['imdb'], 'f_lang_id': langId, 'f_lang': lang, 'icon': icon, 'desc': desc}
                self.addVideo(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CineTO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['f_term'] = searchPattern
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("CineTO.getLinksForVideo [%s]" % cItem)
        retTab = []
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = 'ID=%s&lang=%s' % (cItem.get('imdb'), cItem.get('f_lang_id'))
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        qualityMap = {'0': "CAM", '1': "TS", '2': "DVD", '3': "HD"}
        try:
            url = self.getFullUrl('/request/links')
            post_data = 'ID=%s&lang=%s' % (cItem['imdb'], cItem['f_lang_id'])

            sts, data = self.getPage(url, post_data=post_data)
            if not sts:
                return []

            data = json_loads(data, '', True)['links']
            printDBG(data)

            for hosting in data:
                links = data[hosting]
                if len(links) < 2:
                    continue

                quality = str(links[0])
                quality = qualityMap.get(quality, quality)
                for idx in range(1, len(links), 1):
                    name = '[%s] %s' % (quality, hosting)
                    url = self.getFullUrl('/out/' + links[idx])
                    retTab.append({'name': name, 'url': url, 'need_resolve': 1})
        except Exception:
            printExc()

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab

        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("CineTO.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        returnCode = 200
        errorMsgTab = []
        sts, data = self.getPage(videoUrl)
        if sts:
            videoUrl = data.meta['url']
            cacheKey = videoUrl
            if 1 != self.up.checkHostSupport(videoUrl) and 'gcaptchaSetup' in data:
                if cacheKey in CineTO.LINKS_CACHE:
                    videoUrl = CineTO.LINKS_CACHE[cacheKey]
                else:
                    sitekey = self.cm.ph.getSearchGroups(data, '''gcaptchaSetup\s*?\(\s*?['"]([^'^"]+?)['"]''')[0]
                    if sitekey != '':
                        token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'], bypassCaptchaService=config.plugins.iptvplayer.cineto_bypassrecaptcha.value)

                        if token != '':
                            params = MergeDicts(self.defaultParams, {'max_data_size': 0})
                            params['header'] = MergeDicts(params['header'], {'Referer': self.cm.meta['url']})
                            sts, data = self.getPage(videoUrl + '?token=' + token, params)
                            if sts:
                                videoUrl = self.cm.meta['url']
                    if 1 == self.up.checkHostSupport(videoUrl):
                        CineTO.LINKS_CACHE[cacheKey] = videoUrl
            returnCode = self.cm.meta.get('status_code', 200)
            urlTab = self.up.getVideoLinkExt(videoUrl)
        else:
            returnCode = self.cm.meta.get('status_code', 200)
            urlTab = self.up.getVideoLinkExt(videoUrl)

        if 0 == len(urlTab):
            if returnCode == 404:
                errorMsgTab = [_("Server return 404 - Not Found.")]
                errorMsgTab.append(_("It looks like some kind of protection. Try again later."))

            if len(errorMsgTab):
                SetIPTVPlayerLastHostError('\n'.join(errorMsgTab))

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("CineTO.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = self.getFullUrl('/request/entry')
        post_data = 'ID=%s' % cItem['imdb']

        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return []

        title = ''
        desc = ''
        icon = ''

        try:
            data = json_loads(data, noneReplacement='', baseTypesAsString=True)['entry']
            icon = self.getFullIconUrl(data.get('cover', cItem.get('icon', '')))
            title = self.cleanHtmlStr(data['title'])

            lang = cItem.get('f_lang', '')
            if lang == '':
                # move better language at top
                langKeys = list(data['lang'].keys())
                defLang = GetDefaultLang()
                if defLang not in langKeys:
                    defLang = 'en'
                if defLang in langKeys:
                    lang = defLang
                else:
                    lang = langKeys[0]

            desc = self.cleanHtmlStr(data.get('plot_' + lang, ''))

            tmp = data.get('year', '')
            if tmp != '':
                otherInfo['year'] = tmp

            tmp = data.get('date', '')
            if tmp != '':
                otherInfo['released'] = tmp

            tmp = data.get('duration', '')
            if tmp != '':
                otherInfo['duration'] = tmp + ' min.'

            for item in [('genres', 'genres'), ('producer', 'producers'), ('director', 'directors'), ('actor', 'actors')]:
                tmp = ', '.join(data.get(item[0], []))
                if tmp != '':
                    otherInfo[item[1]] = tmp

            tmp = data['rating']
            if tmp != '':
                otherInfo['imdb_rating'] = '%s/10' % (data['rating'])

        except Exception:
            printExc()

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_genres':
            self.listGenres(self.currItem, 'list_rating')
        elif category == 'list_rating':
            self.listRating(self.currItem, 'list_year')
        elif category == 'list_year':
            self.listYear(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem, 'explore_item')
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
        CHostBase.__init__(self, CineTO(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('imdb', '') != '':
            return True
        return False
