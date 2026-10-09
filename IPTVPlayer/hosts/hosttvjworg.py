# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# JW Broadcasting (tv.jw.org / jw.org videos and audio) - JSON API of the jw.org web site:
#   categories: b.jw-cdn.org/apis/mediator/v1/categories/<lang>/<key>?detailed=1 (subcategories, media, limit/offset)
#   one item:   .../media-items/<lang>/<languageAgnosticNaturalKey> (links, also for favourites and search hits)
#   search:     b.jw-cdn.org/apis/search/results/<lang>/videos (public JWT from b.jw-cdn.org/tokens/jworg.jwt)
# 08.10.2026 - new API host (b.jw-cdn.org), languages, search, paging, watched flag, download marker,
#   favourites, INFO, sidecar, VTT subtitles, no duration in the title
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, CSelOneLink, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import time
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
TVJWORG_LANGUAGES = [("E", _("English")), ("X", _("German")), ("F", _("French")), ("S", _("Spanish")),
                     ("I", _("Italian")), ("P", _("Polish")), ("H", _("Hungarian")), ("O", _("Dutch")), ("T", _("Portuguese")),
                     ("U", _("Russian")), ("TK", _("Turkish")), ("A", _("Arabic"))]
config.plugins.iptvplayer.tvjworg_language = ConfigSelection(default="default", choices=[("default", _("Default"))] + TVJWORG_LANGUAGES)
config.plugins.iptvplayer.tvjworg_icontype = ConfigSelection(default="vertical", choices=[("vertical", _('vertical')), ("horizontal", _('horizontal'))])
config.plugins.iptvplayer.tvjworg_default_format = ConfigSelection(default="720", choices=[("0", _("the worst")),
                                                                                               ("240", "240p"),
                                                                                               ("360", "360p"),
                                                                                               ("480", "480p"),
                                                                                               ("720", "720p"),
                                                                                               ("99999999", _("the best"))])
config.plugins.iptvplayer.tvjworg_use_df = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language"), config.plugins.iptvplayer.tvjworg_language))
    optionList.append(getConfigListEntry(_("Default video quality"), config.plugins.iptvplayer.tvjworg_default_format))
    optionList.append(getConfigListEntry(_("Use default video quality"), config.plugins.iptvplayer.tvjworg_use_df))
    optionList.append(getConfigListEntry(_("Icon type"), config.plugins.iptvplayer.tvjworg_icontype))
    return optionList
###################################################


def gettytul():
    return 'https://tv.jw.org/'


class TVJWORG(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API_URL = 'https://b.jw-cdn.org/apis/mediator/v1/'
    SEARCH_URL = 'https://b.jw-cdn.org/apis/search/results/'
    TOKEN_URL = 'https://b.jw-cdn.org/tokens/jworg.jwt'
    PAGE_SIZE = 60
    SEARCH_PAGE_SIZE = 24
    ICONS_KEYS = ["xl", "lg", "md", "sm", "xs"]
    ICONS_TYPES = {'vertical': ['pss', 'psr', 'sqr', 'sqs'], 'horizontal': ['lsr', 'lss', 'wss', 'wsr', 'pnr']}
    # UI locale -> jw.org language code (the rest is looked up in the languages list of the API)
    LOCALE_CODES = {'en': 'E', 'de': 'X', 'fr': 'F', 'es': 'S', 'it': 'I', 'pl': 'P', 'hu': 'H', 'nl': 'O', 'pt': 'T',
                    'ru': 'U', 'tr': 'TK', 'ar': 'A'}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tv.jw.org', 'cookie': 'tvjworg.cookie'})
        self.MAIN_URL = 'https://www.jw.org/'
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/tvjworg135.png')
        self.HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'application/json', 'Referer': self.MAIN_URL}
        self.defaultParams = {'header': self.HEADER}
        self.defaultLangCode = ''
        self.searchToken = ('', 0)
        self.watchedHelper = IPTVWatchedHelper('tvjworg')
        self.wfInitFolderCache()

    ###################################################
    # API
    ###################################################
    def _getJson(self, url, header=None):
        params = dict(self.defaultParams)
        if header:
            params['header'] = dict(self.HEADER, **header)
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG('TVJWORG._getJson: no JSON from %s' % url)
        return None

    def _getLangCode(self):
        langCode = config.plugins.iptvplayer.tvjworg_language.value
        if langCode != 'default':
            return langCode
        if self.defaultLangCode:
            return self.defaultLangCode
        locale = GetDefaultLang()
        langCode = self.LOCALE_CODES.get(locale, '')
        if not langCode:
            data = self._getJson(self.API_URL + 'languages/E/web?clientType=www')
            try:
                for item in (data or {}).get('languages', []):
                    if item.get('locale') == locale:
                        langCode = str(item['code'])
                        break
            except Exception:
                printExc()
        self.defaultLangCode = langCode or 'E'
        return self.defaultLangCode

    def _lang(self, cItem):
        # rows keep their language: a favourite opens in the language it was added in
        return cItem.get('lang') or self._getLangCode()

    def _getIcon(self, iconItem):
        try:
            images = iconItem.get('images') or {}
            for icontype in self.ICONS_TYPES.get(config.plugins.iptvplayer.tvjworg_icontype.value, []):
                icons = images.get(icontype) or {}
                for key in self.ICONS_KEYS:
                    icon = str(icons.get(key) or '')
                    if icon.startswith('http'):
                        return icon
            # an icon of the other orientation is better than none
            for icons in images.values():
                for key in self.ICONS_KEYS:
                    icon = str((icons or {}).get(key) or '')
                    if icon.startswith('http'):
                        return icon
        except Exception:
            printExc()
        return self.DEFAULT_ICON_URL

    @staticmethod
    def _dirCategory(item):
        # "container": subcategories only, "ondemand": videos / tracks (same list function)
        return 'list_category' if item.get('type') == 'container' else 'list_media'

    def _pageUrl(self, lang, lank):
        # stable page of the item on jw.org: watched flag and download marker key
        return 'https://www.jw.org/finder?wtlocale=%s&lank=%s' % (lang, lank)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        lang = self._getLangCode()
        data = self._getJson(self.API_URL + 'categories/%s?clientType=www' % lang)
        seen = set()
        for item in (data or {}).get('categories', []):
            try:
                tags = item.get('tags') or []
                name = self.cleanHtmlStr(item.get('name', ''))
                # web-only / duplicate entries (several "Featured" variants for other site layouts)
                if not name or name in seen or 'Unpub' in item.get('key', '') or 'WWWExclude' in tags or 'WebExclude' in tags:
                    continue
                seen.add(name)
                self.addDir({'name': 'category', 'category': self._dirCategory(item), 'title': name, 'key': item['key'], 'lang': lang,
                             'icon': self._getIcon(item), 'desc': self.cleanHtmlStr(item.get('description', '')), 'good_for_fav': True})
            except Exception:
                printExc()
        if not self.currList:
            SetIPTVPlayerLastHostError(_("Content not available"))
        self.listsTab(self.searchItems(), cItem)

    def listCategory(self, cItem):
        printDBG("TVJWORG.listCategory [%s]" % cItem.get('key', ''))
        lang = self._lang(cItem)
        page = int(cItem.get('page', 1) or 1)
        url = self.API_URL + 'categories/%s/%s?detailed=1&clientType=www&limit=%d&offset=%d' % (lang, cItem['key'], self.PAGE_SIZE, (page - 1) * self.PAGE_SIZE)
        data = self._getJson(url)
        category = (data or {}).get('category') or {}
        catTitle = self.cleanHtmlStr(category.get('name', '')) or cItem.get('title', '')
        if page == 1:
            for item in category.get('subcategories') or []:
                try:
                    self.addDir({'name': 'category', 'category': self._dirCategory(item), 'title': self.cleanHtmlStr(item['name']), 'key': item['key'],
                                 'lang': lang, 'icon': self._getIcon(item), 'desc': self.cleanHtmlStr(item.get('description', '')), 'good_for_fav': True})
                except Exception:
                    printExc()
        for item in category.get('media') or []:
            self._addMedia(item, lang, catTitle)
        try:
            pagination = (data or {}).get('pagination') or {}
            total = int(pagination.get('totalCount') or 0)
        except Exception:
            total = 0
        lastPage = (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        addPagingItems(self, cItem, page, page < lastPage, lastPage, '')

    def _addMedia(self, item, lang, catTitle=''):
        try:
            lank = item.get('languageAgnosticNaturalKey', '')
            title = self.cleanHtmlStr(item.get('title', ''))
            if not lank or not title:
                return
            date = str(item.get('firstPublished') or '')[:10]
            duration = item.get('durationFormattedMinSec') or ''
            plot = self.cleanHtmlStr(item.get('description', ''))
            desc = ' | '.join([x for x in (date, duration, catTitle) if x])
            if plot:
                desc += '[/br]' + plot
            params = {'name': 'category', 'category': 'media', 'title': title, 'url': self._pageUrl(lang, lank), 'lank': lank, 'lang': lang,
                      'icon': self._getIcon(item), 'desc': desc, 'date': date, 'duration': duration, 'cat_title': catTitle,
                      'plot': plot, 'good_for_fav': True}
            if item.get('type') == 'audio':
                self.addAudio(params)
            else:
                self.addVideo(params)
        except Exception:
            printExc()

    ###################################################
    # search
    ###################################################
    def _getSearchToken(self):
        token, validUntil = self.searchToken
        if token and time.time() < validUntil:
            return token
        sts, data = self.cm.getPage(self.TOKEN_URL, {'header': dict(self.HEADER, Accept='*/*')})
        token = data.strip() if sts and data and data.count('.') == 2 else ''
        # the public token is valid for days, ask again after an hour
        self.searchToken = (token, time.time() + 3600)
        return token

    def listSearchResult(self, cItem):
        lang = self._lang(cItem)
        page = int(cItem.get('page', 1) or 1)
        token = self._getSearchToken()
        if not token:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return
        url = self.SEARCH_URL + '%s/videos?q=%s&limit=%d&offset=%d' % (lang, urllib_quote(cItem.get('q', '')), self.SEARCH_PAGE_SIZE, (page - 1) * self.SEARCH_PAGE_SIZE)
        data = self._getJson(url, {'Authorization': 'Bearer ' + token})
        for item in (data or {}).get('results') or []:
            try:
                lank = item.get('lank', '')
                title = self.cleanHtmlStr(item.get('title', ''))
                if item.get('type') != 'item' or not lank or not title:
                    continue
                duration = item.get('duration') or ''
                plot = self.cleanHtmlStr(item.get('snippet', ''))
                params = {'name': 'category', 'category': 'media', 'title': title, 'url': self._pageUrl(lang, lank), 'lank': lank, 'lang': lang,
                          'icon': (item.get('image') or {}).get('url') or self.DEFAULT_ICON_URL, 'duration': duration, 'plot': plot,
                          'desc': duration + ('[/br]' + plot if plot else ''), 'good_for_fav': True}
                if item.get('subtype') == 'audio':
                    self.addAudio(params)
                else:
                    self.addVideo(params)
            except Exception:
                printExc()
        try:
            total = int((((data or {}).get('insight') or {}).get('total') or {}).get('value') or 0)
        except Exception:
            total = 0
        lastPage = (total + self.SEARCH_PAGE_SIZE - 1) // self.SEARCH_PAGE_SIZE
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))
            return
        addPagingItems(self, cItem, page, page < lastPage, lastPage, '')

    ###################################################
    # links
    ###################################################
    def _getMediaItem(self, cItem):
        data = self._getJson(self.API_URL + 'media-items/%s/%s?clientType=www' % (self._lang(cItem), cItem.get('lank', '')))
        media = (data or {}).get('media') or []
        locale = ((data or {}).get('language') or {}).get('locale', '')
        return (media[0] if media else {}), locale

    def getLinksForVideo(self, cItem):
        printDBG("TVJWORG.getLinksForVideo [%s]" % cItem.get('url', ''))
        # the old host version had no favourites: every playable row carries its lank
        item, locale = self._getMediaItem(cItem) if cItem.get('lank') else ({}, '')
        files = item.get('files') or []
        # 3gp only when there is nothing else; a burnt-in subtitled copy only when the plain one is missing
        if any(f.get('mimetype') != 'video/3gpp' for f in files):
            files = [f for f in files if f.get('mimetype') != 'video/3gpp']
        byLabel = {}
        order = []
        for f in files:
            if not f.get('progressiveDownloadURL'):
                continue
            mimetype = f.get('mimetype') or ''
            label = f.get('label') or ('MP3' if mimetype in ('', 'audio/mpeg') else mimetype.split('/')[-1].upper())
            if label not in byLabel:
                order.append(label)
            if label not in byLabel or (byLabel[label].get('subtitled') and not f.get('subtitled')):
                byLabel[label] = f
        urlTab = []
        for label in order:
            f = byLabel[label]
            meta = {'Referer': self.MAIN_URL, 'User-Agent': self.HEADER['User-Agent']}
            sub = (f.get('subtitles') or {}).get('url', '')
            if sub:
                meta['external_sub_tracks'] = [{'title': locale.upper() or _('Subtitles'), 'url': sub, 'lang': locale, 'format': 'vtt'}]
            urlTab.append({'name': label, 'url': strwithmeta(f['progressiveDownloadURL'], meta), 'need_resolve': 0})
        if 1 < len(urlTab):
            def _getLinkQuality(itemLink):
                try:
                    return int(itemLink['name'].rstrip('pP'))
                except Exception:
                    return 0
            oneLink = CSelOneLink(urlTab, _getLinkQuality, int(config.plugins.iptvplayer.tvjworg_default_format.value))
            if config.plugins.iptvplayer.tvjworg_use_df.value:
                urlTab = oneLink.getOneLink()
            else:
                urlTab = oneLink.getSortedLinks()
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO, watched flag
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('date'):
            other['released'] = cItem['date']
        if cItem.get('duration'):
            other['duration'] = cItem['duration']
        if cItem.get('cat_title'):
            other['category'] = cItem['cat_title']
        if cItem.get('lang'):
            other['language'] = dict(TVJWORG_LANGUAGES).get(cItem['lang'], cItem['lang'])
        # many items have no description of their own: the category / date line instead of an empty text
        text = cItem.get('plot', '') or cItem.get('desc', '').split('[/br]')[0] or cItem.get('title', '')
        icon = cItem.get('icon', '')
        images = [{'title': '', 'url': icon}] if icon.startswith('http') else []
        return [{'title': cItem.get('title', ''), 'text': text, 'images': images, 'other_info': other}]

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('category') == 'media' and cItem.get('lank'):
                return 'video:%s/%s' % (cItem.get('lang', ''), cItem['lank'])
            if cItem.get('category') in ('list_category', 'list_media') and cItem.get('key'):
                return 'folder:%s/%s' % (cItem.get('lang', ''), cItem['key'])
        except Exception:
            printExc()
        return ''

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TVJWORG.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("TVJWORG.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category in ('list_category', 'list_media'):
            if 'key' in self.currItem:
                self.listCategory(self.currItem)
        elif category == 'list_search':
            self.listSearchResult(self.currItem)
        elif category in ("search", "search_next_page"):
            self.listSearchResult({'name': 'category', 'category': 'list_search', 'q': searchPattern.strip(), 'lang': self._getLangCode()})
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TVJWORG(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tvjworg')

    def withArticleContent(self, cItem):
        return cItem.get('type') in ('video', 'audio')
