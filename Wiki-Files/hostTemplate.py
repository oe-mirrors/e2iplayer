# -*- coding: utf-8 -*-
# Template of a movie/series host that follows the current host standard:
#   - movies and series (series -> seasons -> episodes), search with history
#   - "First page" / "Jump" / "Next page" (with "(2/12)" when the last page is known)
#   - watched flag (episode -> season -> series), favourites with a stable identity
#   - "downloaded" marker (works by itself: VIDEO rows with a stable page url)
#   - media name normalisation ("Title (Year)", "Show - S01E02 - Name")
#   - sidecar .txt/.jpg next to downloads, INFO key with libs/moviemeta
#   - runs on Python 2.7 and 3 (p2p3 imports, no f-strings)
#
# How to use it: copy it to IPTVPlayer/hosts/host<name>.py, replace "template"/"Template" by the
# host name, set gettytul() and adapt the markers/regular expressions in the list functions to
# the site. The site it is written for is made up - the HTML it expects is shown above each
# list function. Explained step by step in the wiki:
# https://github.com/oe-mirrors/e2iplayer/wiki/Index-on-how-to-create-hosts-and-handle-urlparser
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getArticleContent as getMetaArticleContent
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
except ImportError:
    # E2iPlayer without tools/iptvpaging.py (older python3 or the zadmario fork): only "Next page"
    addPagingItems = isJumpItem = jumpTarget = None
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    # options shown with the BLUE key in the host list; [] when the host has none. Example:
    #   config.plugins.iptvplayer.template_login = ConfigLogin(default="", fixed_size=False)
    #   config.plugins.iptvplayer.template_password = ConfigSecret(default="", fixed_size=False)
    #   optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.template_login))
    # (ConfigLogin/ConfigSecret from components/configsecret.py hide the password on screen)
    return []


def gettytul():
    # main url of the site, also shown as the host title
    return 'https://www.example.com/'


class Template(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # the fields of a row that identify it as a favourite: what is needed to open it again, nothing that
    # changes between two visits (title with year/quality, plot, icon, page number ...)
    FAV_FIELDS = ('name', 'type', 'category', 'url', 's_title', 'season', 'meta_type', 'meta_title', 'meta_year')

    def __init__(self):
        # names of the search history file and the cookie file of this host
        CBaseHostClass.__init__(self, {'history': 'template', 'cookie': 'template.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl('/images/logo.png')
        # one header for the whole host - a random UA per request breaks session cookies
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        # "{page}" is replaced by the page number (tools/iptvpaging.py does the same for "Jump")
        self.MENU = [
            {'category': 'list_items', 'title': _('Movies'), 'url_tpl': self.getFullUrl('/movies/page/{page}/')},
            {'category': 'list_items', 'title': _('Series'), 'url_tpl': self.getFullUrl('/series/page/{page}/')},
        ] + self.searchItems()  # Search, Search history, Edit search history, Delete search history

        # watched flag: files under the "watched" folder of E2iPlayer, one subfolder per host name
        self.watchedHelper = IPTVWatchedHelper('template')
        self.wfInitFolderCache()

    ###################################################
    # HTTP
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        # behind Cloudflare: return self.cm.getPageCFProtection(url, addParams, post_data)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # watched flag and favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        # a stable id per movie / episode / season / series ('' = no flag): the page url, never a signed
        # stream url; menus, "Next page", search and live streams get none
        try:
            if not isinstance(cItem, dict):
                return ''
            url = str(cItem.get('url', '') or '').strip()
            category = cItem.get('category', '')
            if url == '':
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                return 'video:%s' % url
            if category == 'list_seasons':
                return 'folder:%s' % url
            if category == 'list_episodes':
                return 'folder:%s|%s' % (url, cItem.get('season', ''))
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # paging
    ###################################################
    def addPaging(self, cItem, page, hasNext, lastPage):
        if addPagingItems is not None:
            # "First page" (from page 2 on), "Jump" (asks for the page) and "Next page"
            addPagingItems(self, cItem, page, hasNext, lastPage, cItem.get('url_tpl', ''))
        elif hasNext:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            if lastPage:
                params['last_page'] = lastPage
            self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        # <article class="item movie"><a href="/movie/the-general-1926/"><img src="/img/general.jpg" alt="The General"></a>
        #   <h3 class="title">The General</h3><span class="year">1926</span><p class="plot">...</p></article>
        # <div class="pagination"> ... <a class="page-numbers" href="/movies/page/12/">12</a>
        #   <a class="next page-numbers" href="/movies/page/2/">Next</a></div>
        printDBG('Template.listItems [%s]' % cItem)
        page = int(cItem.get('page', 1) or 1)
        url = cItem['url_tpl'].format(page=page)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()

        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, ('<article', '>', 'item'), '</article>'):
            itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            if itemUrl == '' or title == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'''src=['"]([^'"]+)['"]''')[0])
            year = self.cm.ph.getSearchGroups(item, r'class="year">\s*(\d{4})')[0]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'plot'), ('</p', '>'), False)[1])
            isSeries = '/series/' in itemUrl
            # a new dict per row instead of dict(cItem): nothing of the list (page, url_tpl ...) sticks to the row
            params = {'name': 'category', 'good_for_fav': True, 'url': itemUrl, 'icon': icon, 'desc': desc,
                      's_title': title, 'meta_type': 'tv' if isSeries else 'movie', 'meta_title': title, 'meta_year': year}
            if isSeries:
                params.update({'category': 'list_seasons', 'title': title})
                self.addDir(params)
            else:
                # "Title (Year)" only when the user wants normalised names - it is also the download file name
                params.update({'category': 'video', 'title': '%s (%s)' % (title, year) if (normalize and year) else title})
                self.addVideo(params)

        pagination = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'), False)[1]
        hasNext = 'class="next' in pagination
        lastPage = max([int(x) for x in re.findall(r'>\s*(\d+)\s*<', pagination)] or [0])
        self.addPaging(cItem, page, hasNext, lastPage)

    def listSeasons(self, cItem):
        # <div class="season" data-season="1"> ... </div> on the page of the series
        printDBG('Template.listSeasons [%s]' % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        sTitle = cItem.get('s_title', cItem.get('title', ''))
        for season in re.findall(r'class="season"\s+data-season="(\d+)"', data):
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_episodes', 'season': season,
                           'title': '%s - %s %s' % (sTitle, _('Season'), season)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        # <div class="season" data-season="1"><ul>
        #   <li class="episode"><a href="/episode/sherlock-1x1/">A Study in Pink</a><span class="num">1x1</span></li>
        printDBG('Template.listEpisodes [%s]' % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get('s_title', '')
        season = cItem.get('season', '')
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'data-season="%s"' % season), ('</ul', '>'), False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, ('<li', '>', 'episode'), '</li>'):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+)['"]''')[0])
            if url == '':
                continue
            epName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>'), ('</a', '>'), False)[1])
            numLabel = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'num'), ('</span', '>'), False)[1])
            epNum = self.cm.ph.getSearchGroups(numLabel, r'\d+x(\d+)')[0]
            if normalize and epNum:
                # "Show - S01E02 - Name"
                title = ' - '.join([x for x in (sTitle, formatSxxExx(season, epNum), epName) if x])
            else:
                # the site's own label: "Show - 1x2 Name"
                title = '%s - %s' % (sTitle, ('%s %s' % (numLabel, epName)).strip())
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'video', 'title': title, 'url': url, 'episode': epNum})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('Template.listSearchResult [%s]' % searchPattern)
        # the result list is an ordinary list_items list, so paging works the same way
        self.listItems({'name': 'category', 'category': 'list_items',
                        'url_tpl': self.getFullUrl('/page/{page}/?s=') + urllib_quote_plus(searchPattern)})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        # <div class="plot">...</div>
        # <ul class="mirrors"><li data-link="https://voe.sx/e/abc">VOE</li> ... </ul>
        printDBG('Template.getLinksForVideo [%s]' % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        plot = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'plot'), ('</div', '>'), False)[1])
        linksTab = []
        for url in re.findall(r'''data-link=['"]([^'"]+)['"]''', data):
            url = self.getFullUrl(url)
            if self.up.checkHostSupport(url) != 1:
                printDBG('Template: hoster not supported by urlparser [%s]' % url)
                continue
            # need_resolve=1: getVideoLinks() asks urlparser for the stream when the user picks the link
            linksTab.append({'name': self.up.getHostName(url, True), 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})
        if not linksTab:
            # shown to the user below "No valid links available." instead of a silent empty list
            SetIPTVPlayerLastHostError(_('This video is only on hosters E2iPlayer cannot play.'))
            return []
        # sidecar: plot + poster written next to a download (when switched on in the settings)
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot))

    def getVideoLinks(self, videoUrl):
        printDBG('Template.getVideoLinks [%s]' % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO key
    ###################################################
    def getArticleContent(self, cItem):
        # plot, poster, rating, cast ... from the services switched on in the settings (TMDb, IMDb, ...);
        # the row's own desc and icon when none of them knows the title
        return getMetaArticleContent(cItem)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Template.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem is not None and isJumpItem(self.currItem):
            # "Jump": asks for the page number and turns the row into the list item of that page
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('handleService: name[%s], category[%s]' % (name, category))
        self.currList = []

        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_seasons':
            self.listSeasons(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        # True = the host has a search history
        CHostBase.__init__(self, Template(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('template')

    def withArticleContent(self, cItem):
        # INFO key only for rows moviemeta can look up
        return 'meta_title' in cItem
