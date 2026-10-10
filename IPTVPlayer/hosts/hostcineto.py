# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 03.10.2026 - brought to the current host standard
#   - covers from cine.to/public/cover/<8-digit id>.jpg (s.cine.to is gone -> 502)
#   - INFO: site plot/genres/director/cast/rating merged with libs/moviemeta (the site's
#     ids are not reliable IMDb ids, so the lookup goes by title + year)
#   - one folder per movie, one VIDEO row per audio language (+ trailer), keyed on a stable
#     page url; watched flag with movie folder propagation, favourites, sidecar, name
#     normalisation ("Title (Year)"), First page / Jump / Next page
# 10.10.2026 - links are no longer renamed to "*name*" after use - that broke the link list's own used mark (tick + colour)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigSecret
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
###################################################
# FOREIGN import
###################################################
import re
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.api_key_9kweu = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_2captcha = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.cineto_bypassrecaptcha = ConfigSelection(default="mye2i", choices=[("mye2i", _("MyE2i (solve on your phone/PC)")),
                                                                                            ("9kw.eu", "https://9kw.eu/"),
                                                                                            ("2captcha.com", "https://2captcha.com/")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Captcha solving service"), config.plugins.iptvplayer.cineto_bypassrecaptcha))
    if config.plugins.iptvplayer.cineto_bypassrecaptcha.value == '9kw.eu':
        optionList.append(getConfigListEntry('    ' + _("API Key"), config.plugins.iptvplayer.api_key_9kweu))
    elif config.plugins.iptvplayer.cineto_bypassrecaptcha.value == '2captcha.com':
        optionList.append(getConfigListEntry('    ' + _("API Key"), config.plugins.iptvplayer.api_key_2captcha))
    return optionList
###################################################


def gettytul():
    return 'https://cine.to/'


ITEMS_PER_PAGE = 30
# the site's audio language ids (data-lid of its language selector)
LANGS = {'1': 'en', '2': 'de', '3': 'es', '4': 'fr', '5': 'it', '6': 'tr'}
LANG_IDS = dict((v, k) for k, v in LANGS.items())
QUALITIES = {'0': 'CAM', '1': 'TS', '2': 'DVD', '3': 'HD'}
# the search API takes a year range; the whole catalogue lies inside this one
YEAR_MIN, YEAR_MAX = '1900', '2100'


class CineTO(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    LINKS_CACHE = {}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cine.to', 'cookie': 'cine.to.cookie'})
        self.DEFAULT_ICON_URL = 'https://cine.to/opengraph.jpg'
        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.MAIN_URL = gettytul()
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Accept-Language': GetDefaultLang()}

        self.cacheFilters = {}
        self.cacheLinks = {}
        self.cacheEntries = {}
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'raw_post_data': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = self.searchItems()
        self.watchedHelper = IPTVWatchedHelper('cineto')
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)

        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getJson(self, path, post_data):
        sts, data = self.getPage(self.getFullUrl(path), post_data=post_data)
        if not sts:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    @staticmethod
    def _cid(imdb):
        # the site pads its ids to 8 digits (covers, "#tt<id>" anchors)
        return str(imdb or '').strip().zfill(8)

    def _coverUrl(self, imdb):
        return self.MAIN_URL + 'public/cover/%s.jpg' % self._cid(imdb)

    def _iconUrl(self, url, imdb=''):
        url = (url or '').strip()
        if url.startswith('//'):
            return 'https:' + url
        if url:
            return self.getFullIconUrl(url)
        return self._coverUrl(imdb) if imdb else ''

    def _videoUrl(self, imdb, lang):
        # stable page url of one language version (downloaded marker, favourites)
        return self.MAIN_URL + '#tt%s/%s' % (self._cid(imdb), lang)

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year:
            return '%s (%s)' % (title, year)
        return title

    def _getEntry(self, imdb):
        imdb = str(imdb or '')
        if imdb in self.cacheEntries:
            return self.cacheEntries[imdb]
        entry = self._getJson('/request/entry', 'ID=%s' % imdb).get('entry')
        if not isinstance(entry, dict):
            return {}
        self.cacheEntries[imdb] = entry
        return entry

    @staticmethod
    def _entryLangIds(entry):
        # "lang" is a list of ids ([1, 2]); older answers had a dict keyed by id
        langs = entry.get('lang') or []
        if isinstance(langs, dict):
            langs = list(langs.keys())
        return [str(x) for x in langs]

    @staticmethod
    def _plot(entry, lang=''):
        # plot in the requested language, else in the GUI language, English, any
        for code in (lang, GetDefaultLang(), 'en', 'de'):
            plot = entry.get('plot_%s' % code) if code else ''
            if plot:
                return plot
        for key in entry:
            if key.startswith('plot_') and entry[key]:
                return entry[key]
        return ''

    def _loadFilters(self):
        if self.cacheFilters.get('kind'):
            return True
        self.cacheFilters = {'kind': [], 'genres': [], 'rating': [], 'year': []}
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return False
        try:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="kind">', '</ul>')[1]
            for item in self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<label', '</label>'):
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                self.cacheFilters['kind'].append({'f_kind': value, 'title': self.cleanHtmlStr(item)})

            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="genres"', '</ul>')[1]
            for item in self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>'):
                value = self.cm.ph.getSearchGroups(item, '''data-id=['"]([^'^"]+?)['"]''')[0]
                self.cacheFilters['genres'].append({'f_genres': value, 'title': self.cleanHtmlStr(item)})

            self.cacheFilters['rating'].append({'f_rating': '1', 'title': _('Any')})
            for idx in range(10, 0, -1):
                self.cacheFilters['rating'].append({'f_rating': str(idx), 'title': _('Rating %s') % idx})

            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="year"', '</ul>')[1]
            end = int(self.cm.ph.getSearchGroups(tmp, '''data-end=['"]([0-9]+?)['"]''')[0])
            start = int(self.cm.ph.getSearchGroups(tmp, '''data-start=['"]([0-9]+?)['"]''')[0])
            self.cacheFilters['year'].append({'title': _('Any')})
            for idx in range(end, start - 1, -1):
                self.cacheFilters['year'].append({'f_year': str(idx), 'title': _('Year %s') % idx})
        except Exception:
            printExc()
        return bool(self.cacheFilters['kind'])

    def _getSearchParams(self, cItem, count=1):
        post_data = {'kind': cItem.get('f_kind', 'all'), 'genre': cItem.get('f_genres', '0'), 'rating': cItem.get('f_rating', '1'),
                     'term': cItem.get('f_term', ''), 'page': cItem.get('page', 1), 'count': count}
        sYear = cItem.get('f_year', YEAR_MIN)
        eYear = cItem.get('f_year', YEAR_MAX)
        return urllib_urlencode(post_data) + '&year%5B%5D={0}&year%5B%5D={1}'.format(sYear, eYear)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get('imdb'):
                return ''
            category = cItem.get('category', '')
            if category == 'explore_item':
                return 'movie:%s' % self._cid(cItem['imdb'])
            if category == 'cine_video':
                return 'video:%s:%s' % (self._cid(cItem['imdb']), cItem.get('f_lang_id', ''))
        except Exception:
            printExc()
        return ''

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem, nextCategory):
        if self._loadFilters():
            params = dict(cItem)
            params['category'] = nextCategory
            self.listsTab(self.cacheFilters['kind'], params)
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listGenres(self, cItem, nextCategory):
        printDBG("CineTO.listGenres")
        if not self._loadFilters():
            return
        counts = self._getJson('/request/search', self._getSearchParams(cItem)).get('genres', {})
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        for item in self.cacheFilters['genres']:
            params = dict(cItem)
            params.update(item)
            if isinstance(counts, dict) and item['f_genres'] in counts:
                params['title'] = '%s (%s)' % (item['title'], counts[item['f_genres']])
            self.addDir(params)

    def listFilter(self, cItem, key, nextCategory):
        if not self._loadFilters():
            return
        params = dict(cItem)
        params['category'] = nextCategory
        self.listsTab(self.cacheFilters[key], params)

    def _addItem(self, item):
        imdb = str(item.get('imdb', '') or '')
        title = self.cleanHtmlStr(item.get('title', ''))
        if not imdb or not title:
            return False
        year = str(item.get('year', '') or '')
        if year == '0':
            year = ''
        descTab = []
        if year:
            descTab.append(year)
        quality = str(item.get('quality', '') or '')
        if quality:
            descTab.append(QUALITIES.get(quality, quality))
        langs = [LANGS.get(x.strip(), x.strip()).upper() for x in str(item.get('language', '') or '').split(',') if x.strip()]
        if langs:
            descTab.append(', '.join(langs))
        self.addDir({'name': 'category', 'category': 'explore_item', 'good_for_fav': True, 'title': self._movieTitle(title, year),
                     'imdb': imdb, 'icon': self._iconUrl(item.get('cover', ''), imdb), 'desc': ' | '.join(descTab),
                     's_title': title, 'meta_type': 'movie', 'meta_title': title, 'meta_year': year})
        return True

    def listItems(self, cItem):
        printDBG("CineTO.listItems [%s]" % cItem)
        try:
            page = int(cItem.get('page', 1) or 1)
        except Exception:
            page = 1
        cItem = dict(cItem, page=page)
        data = self._getJson('/request/search', self._getSearchParams(cItem, count=ITEMS_PER_PAGE))
        count = 0
        for item in data.get('entries', []) or []:
            if isinstance(item, dict) and self._addItem(item):
                count += 1
        try:
            lastPage = int(data.get('pages', 0) or 0)
        except Exception:
            lastPage = 0
        addPagingItems(self, cItem, page, count > 0 and page < lastPage, lastPage, self.MAIN_URL + '#page={page}')

    def exploreItem(self, cItem):
        printDBG("CineTO.exploreItem")
        imdb = cItem.get('imdb', '')
        entry = self._getEntry(imdb)
        if not entry:
            return
        icon = self._iconUrl(entry.get('cover', ''), imdb) or cItem.get('icon', '')
        baseTitle = self.cleanHtmlStr(entry.get('title', '')) or cItem.get('s_title', '')
        year = str(entry.get('year', '') or cItem.get('meta_year', ''))
        if year == '0':
            year = ''

        descTab = []
        if year:
            descTab.append(year)
        if entry.get('duration'):
            descTab.append('~%s min.' % entry['duration'])
        if entry.get('rating'):
            descTab.append(str(entry['rating']))
        genres = ', '.join(entry.get('genres') or [])
        if genres:
            descTab.append(genres)

        langIds = self._entryLangIds(entry)
        # the GUI language first
        defId = LANG_IDS.get(GetDefaultLang(), '1')
        if defId in langIds:
            langIds.remove(defId)
            langIds.insert(0, defId)

        normalize = IsMediaNamingNormalized()
        base = {'name': 'category', 'good_for_fav': True, 'imdb': imdb, 'icon': icon, 's_title': baseTitle,
                'meta_type': 'movie', 'meta_title': baseTitle, 'meta_year': year}
        for langId in langIds:
            lang = LANGS.get(langId, langId)
            desc = ' | '.join(descTab) + '[/br]' + self.cleanHtmlStr(self._plot(entry, lang))
            if normalize:
                title = normalizeMediathekTitle(baseTitle, year=year, isMovie=True, lang=lang.upper() if len(langIds) > 1 else '')
            else:
                title = '[%s] %s (%s)' % (lang, baseTitle, year) if year else '[%s] %s' % (lang, baseTitle)

            trailer = entry.get('trailer_%s' % lang) or ''
            if trailer:
                trailerTitle = '%s - %s' % (title, _('Trailer')) if normalize else '[%s] [%s] %s' % (_('Trailer'), lang, baseTitle)
                self.addVideo(dict(base, category='cine_trailer', title=trailerTitle, f_lang_id=langId, f_lang=lang, desc=desc,
                                   url='https://www.youtube.com/watch?v=%s' % trailer))
            self.addVideo(dict(base, category='cine_video', title=title, f_lang_id=langId, f_lang=lang, desc=desc,
                               url=self._videoUrl(imdb, lang)))
        if not langIds:
            self.addMarker({'title': _('No stream available'), 'desc': ' | '.join(descTab) + '[/br]' + self.cleanHtmlStr(self._plot(entry))})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CineTO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        # further pages are plain list pages of the search term
        self.listItems({'name': 'category', 'category': 'list_items', 'f_term': searchPattern, 'page': 1})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("CineTO.getLinksForVideo [%s]" % cItem)
        sidecar = buildSidecarFromItem(cItem, IsSidecarEnabled())
        url = cItem.get('url', '')
        if cItem.get('category') == 'cine_trailer' or 'youtube.com/' in url or 'youtu.be/' in url:
            videoUrl = url.replace('youtu.be/', 'youtube.com/watch?v=')
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

        imdb = cItem.get('imdb', '')
        langId = cItem.get('f_lang_id', '')
        if not imdb or not langId:
            # a row known only by its page url ("#tt<id>/<lang>")
            m = re.search(r'#tt0*(\d+)/(\w+)', url)
            if not m:
                return []
            imdb, langId = m.group(1), LANG_IDS.get(m.group(2), m.group(2))

        cacheKey = 'ID=%s&lang=%s' % (imdb, langId)
        retTab = self.cacheLinks.get(cacheKey, [])
        if not retTab:
            links = self._getJson('/request/links', cacheKey).get('links', {})
            if isinstance(links, dict):
                for hosting in links:
                    # [quality, link id, link id, ...]
                    item = links[hosting]
                    if not isinstance(item, list) or len(item) < 2:
                        continue
                    quality = str(item[0])
                    quality = QUALITIES.get(quality, quality)
                    for linkId in item[1:]:
                        retTab.append({'name': '[%s] %s' % (quality, hosting), 'url': self.getFullUrl('/out/%s' % linkId), 'need_resolve': 1})
            if retTab:
                self.cacheLinks[cacheKey] = retTab
        return applySidecarToLinks(retTab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("CineTO.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())

        errorMsgTab = []
        sts, data = self.getPage(videoUrl)
        if sts:
            videoUrl = data.meta['url']
            cacheKey = videoUrl
            if 1 != self.up.checkHostSupport(videoUrl) and 'gcaptchaSetup' in data:
                if cacheKey in CineTO.LINKS_CACHE:
                    videoUrl = CineTO.LINKS_CACHE[cacheKey]
                else:
                    sitekey = self.cm.ph.getSearchGroups(data, r'''gcaptchaSetup\s*?\(\s*?['"]([^'^"]+?)['"]''')[0]
                    if sitekey != '':
                        # cine.to's reCAPTCHA v2 can't be solved by CaptchaHelper's
                        # internal fallback, so a bypass service is mandatory -> MyE2i
                        token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'], bypassCaptchaService=config.plugins.iptvplayer.cineto_bypassrecaptcha.value or 'mye2i')

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

        if 0 == len(urlTab):
            if returnCode == 404:
                errorMsgTab = [_("Server return 404 - Not Found."), _("It looks like some kind of protection. Try again later.")]
            if len(errorMsgTab):
                SetIPTVPlayerLastHostError('\n'.join(errorMsgTab))

        return decorateResolvedLinkItems(urlTab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CineTO.getArticleContent [%s]" % cItem)
        entry = self._getEntry(cItem.get('imdb', ''))
        title = self.cleanHtmlStr(entry.get('title', '')) or cItem.get('meta_title', '') or cItem.get('title', '')
        year = str(entry.get('year', '') or cItem.get('meta_year', ''))
        if year == '0':
            year = ''

        info = {}
        if year:
            info['year'] = year
        if entry.get('date'):
            info['released'] = entry['date']
        if entry.get('duration'):
            info['duration'] = '%s min.' % entry['duration']
        if entry.get('genres'):
            info['genres'] = ', '.join(entry['genres'])
        if entry.get('director'):
            info['directors'] = ', '.join(entry['director'][:3])
        if entry.get('actor'):
            info['actors'] = ', '.join(entry['actor'][:8])
        if entry.get('rating'):
            info['rating'] = '%s/10' % entry['rating']
        langs = [LANGS.get(x, x).upper() for x in self._entryLangIds(entry)]
        if langs:
            info['language'] = ', '.join(langs)

        meta = {}
        if title:
            try:
                meta = getMeta('movie', title, year)
            except Exception:
                printExc()
        info.update(meta.get('info', {}))

        story = self.cleanHtmlStr(self._plot(entry, cItem.get('f_lang', '')))
        plot = meta.get('plot', '')
        text = plot or story or self.cleanHtmlStr(cItem.get('desc', ''))
        if plot and story and story != plot:
            text = '%s[/br][/br]%s' % (plot, story)
        icon = self._iconUrl(entry.get('cover', ''), cItem.get('imdb', '')) or meta.get('poster') or cItem.get('icon', '') or self.DEFAULT_ICON_URL
        return [{'title': self._movieTitle(title, year) if title else cItem.get('title', ''), 'text': text,
                 'images': [{'title': '', 'url': icon}], 'other_info': info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_genres':
            self.listGenres(self.currItem, 'list_rating')
        elif category == 'list_rating':
            self.listFilter(self.currItem, 'rating', 'list_year')
        elif category == 'list_year':
            self.listFilter(self.currItem, 'year', 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, CineTO(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('cineto')

    def withArticleContent(self, cItem):
        return cItem.get('imdb', '') != ''
