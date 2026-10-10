# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Nuteczki.eu: Polish music portal (tracks, sets / mixes by genre), played from the site's KrakenFiles /
#   SoundFiles uploads or YouTube; optional login with the user's own account
# 02.07.2026 - damagic
# 10.10.2026 - host standard: genre menu from the site (club logo entries got their names), tracks as audio rows
#   keyed on the post url (watched flag, downloaded marker, favourites), INFO from the post page (cover, genre,
#   quality, size, date, views), First/Jump/Next paging with the last page, search paging, SoundFiles and YouTube
#   sources, sidecar, current user agent, English labels; removed the unused filter code
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
###################################################
# FOREIGN import
###################################################
import re
import time
from Components.config import config, getConfigListEntry
###################################################
# E2 GUI COMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

config.plugins.iptvplayer.nuteczki_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.nuteczki_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.nuteczki_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.nuteczki_password))
    return optionList


def gettytul():
    return 'https://nuteczki.eu/'


class NuteczkiEU(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a track row (views / comments in desc change)
    TRACK_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'nuteczki.eu', 'cookie': 'nuteczki.eu.cookie'})
        self.HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        self.MAIN_URL = 'https://nuteczki.eu/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/736x/2d/07/83/2d0783d156a48860691667dadd8de458--note-music-music-wallpaper.jpg'
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.watchedHelper = IPTVWatchedHelper('nuteczki')
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _isTrack(self, cItem):
        return cItem.get('type') == 'audio' and '.html' in cItem.get('url', '')

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and self._isTrack(cItem):
                return 'video:%s' % cItem['url']
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            if self._isTrack(cItem):
                return json_dumps(dict((key, cItem[key]) for key in self.TRACK_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("NuteczkiEU.listMainMenu")
        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Latest'), 'url': self.getFullUrl('/muzyka/'), 'good_for_fav': True},
                        {'category': 'categories', 'title': _('Categories'), 'url': self.getFullUrl('/muzyka/')}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def _linkTitle(self, link):
        title = self.cleanHtmlStr(link)
        if not title:
            # club entries are logos only
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(link, r'''\s(?:title|alt)=['"]([^'^"]+?)['"]''')[0])
        return title

    def _categoryTree(self):
        # [(title, url, [(sub title, url), ...]), ...] from the genre menu of the site
        sts, data = self.getPage(self.getFullUrl('/muzyka/'))
        if not sts:
            return []
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'drop-cat'), ('</span', '>'), False)[1]
        tree = []
        dropdown = None
        for m in re.finditer(r'(<li[^>]+?dropdown[^>]*?>)|(</ul>)|(<a\s[^>]*?>.*?</a>)', data, re.S):
            if m.group(1):
                dropdown = ['', []]
            elif m.group(2):
                if dropdown is not None:
                    if dropdown[0] and dropdown[1]:
                        tree.append((dropdown[0], '', dropdown[1]))
                    dropdown = None
            else:
                link = m.group(3)
                title = self._linkTitle(link)
                url = self.cm.ph.getSearchGroups(link, r'''href=['"]([^'^"]+?)['"]''')[0]
                if dropdown is not None and not dropdown[0]:
                    dropdown[0] = title
                elif title and url and url != '#':
                    if dropdown is not None:
                        dropdown[1].append((title, self.getFullUrl(url)))
                    else:
                        tree.append((title, self.getFullUrl(url), []))
        return tree

    def listCategories(self, cItem):
        printDBG("NuteczkiEU.listCategories [%s]" % cItem.get('f_group', ''))
        for title, url, subs in self._categoryTree():
            if cItem.get('f_group'):
                if title != cItem['f_group']:
                    continue
                for subTitle, subUrl in subs:
                    self.addDir({'name': 'category', 'category': 'list_items', 'title': subTitle, 'url': subUrl, 'good_for_fav': True})
                break
            if subs:
                self.addDir({'name': 'category', 'category': 'categories', 'title': title, 'f_group': title, 'good_for_fav': True})
            else:
                self.addDir({'name': 'category', 'category': 'list_items', 'title': title, 'url': url, 'good_for_fav': True})

    def _listBaseUrl(self, url):
        url = re.sub(r'/page/\d+/?$', '/', url)
        if not url.endswith('/') and '?' not in url:
            url += '/'
        return url

    def _itemDesc(self, item):
        desc = []
        stats = []
        tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'news-meta'), ('<form', '>'), False)[1]
        for span in self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>'):
            value = self.cleanHtmlStr(span)
            if not value:
                continue
            if 'fa-eye' in span:
                stats.append('Views: %s' % value)
            elif 'fa-download' in span:
                stats.append(_('Downloads: %s') % value)
            elif 'fa-comment' in span:
                continue
            elif 'fa-user' in span:
                desc.append(_('Uploader: %s') % value)
            else:
                desc.append(value)
        desc = ' | '.join(desc)
        if stats:
            desc += ('[/br]' if desc else '') + ' | '.join(stats)
        return desc

    def _icon(self, url):
        url = self.getFullIconUrl(url.replace('&amp;', '&'))
        # covers linked from Facebook carry a signature that expires ("oe" = hex timestamp)
        oe = self.cm.ph.getSearchGroups(url, r'[?&]oe=([0-9A-Fa-f]{8})')[0] if 'fbcdn.net' in url else ''
        if oe and int(oe, 16) < time.time():
            return ''
        return url

    def _addTracks(self, cItem, data):
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'dle-content'), ('<div', '>', 'clearfix'), False)[1]
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'main-shortstory'), ('<span', '>', 'music-btn'), False):
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>', 'news-title'), ('</h2', '>'), False)[1]
            title = self.cleanHtmlStr(tmp)
            url = self.cm.ph.getSearchGroups(tmp, r'''href=['"]([^'^"]+?)['"]''')[0]
            if not title or not url or url == '#':
                continue
            icon = self._icon(self.cm.ph.getSearchGroups(item, r'''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
            self.addAudio({'name': 'category', 'good_for_fav': True, 'title': title, 'url': self.getFullUrl(url), 'icon': icon, 'desc': self._itemDesc(item)})

    def listItems(self, cItem):
        printDBG("NuteczkiEU.listItems [%s]" % cItem.get('url', ''))
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = self._listBaseUrl(cItem.get('url', '') or self.getFullUrl('/muzyka/'))
        url = baseUrl if page == 1 else baseUrl + 'page/%d/' % page
        sts, data = self.getPage(url)
        if not sts:
            return
        self._addTracks(cItem, data)
        pagination = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</center', '>'), False)[1]
        pages = [int(x) for x in re.findall(r'/page/(\d+)/', pagination)]
        lastPage = max(pages) if pages else page
        if self.currList:
            params = dict(cItem)
            params['url'] = baseUrl
            addPagingItems(self, params, page, page < lastPage, max(lastPage, page), baseUrl + 'page/{page}/')

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("NuteczkiEU.listSearchResult [%s]" % searchPattern)
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        url = self.getFullUrl('/index.php?do=search')
        post_data = {'do': 'search', 'subaction': 'search', 'story': searchPattern}
        if page > 1:
            post_data.update({'search_start': page, 'full_search': '0', 'result_from': (page - 1) * 10 + 1})
        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return
        self._addTracks(cItem, data)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))
            return
        hasNext = ('list_submit(%d)' % (page + 1)) in data
        params = dict(cItem)
        params['url'] = url
        addPagingItems(self, params, page, hasNext, 0, url)

    ###################################################
    # links
    ###################################################
    def _sourceUrls(self, data):
        urls = []
        # player of the post
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>', caseSensitive=False):
            urls.append(self.cm.ph.getSearchGroups(item, r'''\ssrc=['"]([^"^']+?)['"]''', 1, True)[0])
        # YouTube player in the post text
        urls.extend(re.findall(r'''data-type=['"]youtube['"]\s+data-url=['"]([^"^']+?)['"]''', data))
        # download links (engine/go.php?url=base64 / getmp3=base64 "id|+|url")
        for b64 in re.findall(r'''(?:go\.php\?url=|getmp3=)([A-Za-z0-9+/=]+)''', data):
            try:
                urls.append(b64Decode(b64).split('|+|')[-1])
            except Exception:
                printExc()
        outTab = []
        for url in urls:
            url = url.replace('&amp;', '&').strip()
            if url.startswith('//'):
                url = 'https:' + url
            if not self.cm.isValidUrl(url) or 'radioftb' in url or 'facebook' in url:
                continue
            m = re.search(r'krakenfiles\.com/(?:view|embed-audio)/([A-Za-z0-9]+)', url)
            if m:
                url = 'https://krakenfiles.com/embed-audio/%s' % m.group(1)
            m = re.search(r'(https?://soundfiles\.eu/[A-Za-z0-9]+)', url)
            if m:
                url = m.group(1) + '/file'
            if url not in outTab:
                outTab.append(url)
        return outTab

    def getLinksForVideo(self, cItem):
        printDBG("NuteczkiEU.getLinksForVideo [%s]" % cItem.get('url', ''))
        self.tryTologin()
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        linksTab = []
        for url in self._sourceUrls(data):
            if 'krakenfiles.com' in url:
                name = 'KrakenFiles'
            elif 'soundfiles.eu' in url:
                name = 'SoundFiles'
            elif self.up.checkHostSupport(url) == 1:
                name = self.up.getHostName(url)
            else:
                continue
            linksTab.append({'name': name, 'url': url, 'need_resolve': 1})
        if not linksTab:
            # older posts: a direct audio file in the page
            for url in re.findall(r'''https?://[^"'\s<>]+?\.(?:mp3|m4a)(?=["'\s<>?])''', data):
                if url not in [item['url'] for item in linksTab]:
                    linksTab.append({'name': 'mp3' if url.endswith('mp3') else 'm4a', 'url': strwithmeta(url, {'User-Agent': self.HEADER['User-Agent'], 'Referer': cItem['url']}),
                                     'need_resolve': 0})
        if not linksTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("NuteczkiEU.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if 'krakenfiles.com' in videoUrl or 'soundfiles.eu' in videoUrl:
            sts, data = self.getPage(videoUrl)
            if not sts:
                if self.cm.meta.get('status_code') == 404:
                    # KrakenFiles: "File has been deleted"
                    SetIPTVPlayerLastHostError(_('The video has been removed.'))
                return []
            urlTab = []
            if 'krakenfiles.com' in videoUrl:
                for key in ('m4a', 'mp3'):
                    url = self.cm.ph.getSearchGroups(data, r'''%s\s*:\s*['"]([^'^"]+?)['"]''' % key)[0]
                    if url:
                        urlTab.append({'name': key, 'url': self.getFullUrl(url, videoUrl)})
            else:
                url = self.cm.ph.getSearchGroups(data, r'''sfaudio\s*=\s*['"]([^'^"]+?)['"]''')[0].replace('\\/', '/')
                if self.cm.isValidUrl(url):
                    urlTab.append({'name': 'mp3', 'url': url})
            for item in urlTab:
                item['url'] = strwithmeta(item['url'], {'User-Agent': self.HEADER['User-Agent'], 'Referer': videoUrl})
            if not urlTab:
                SetIPTVPlayerLastHostError(self.cleanHtmlStr(data)[:200] if len(data) < 500 else _('No stream available'))
            return decorateResolvedLinkItems(urlTab, sidecar)
        if self.up.checkHostSupport(videoUrl) == 1:
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("NuteczkiEU.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        otherInfo = {}
        sts, data = self.getPage(cItem.get('url', ''))
        if sts:
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h1', '>'), ('</h1', '>'), False)[1])
            if tmp:
                title = tmp
            tmp = self.cm.ph.getSearchGroups(data, r'''<img[^>]+?xfieldimage[^>]+?src=['"]([^"^']+?)['"]''')[0]
            if tmp:
                icon = self._icon(tmp) or icon
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'badge'), ('</span', '>'), False)[1])
            if genre:
                otherInfo['genre'] = genre
            fields = {}
            for label, value in re.findall(r'''overline-title-alt">([^<]+)</span>\s*(?:<span[^>]*>)?([^<]*)<''', data):
                label = self.cleanHtmlStr(label).rstrip(':')
                value = self.cleanHtmlStr(value)
                if value:
                    fields[label] = value
            uploader = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'author'), ('</span', '>'), False)[1])
            if fields.get('Jakość'):
                otherInfo['quality'] = fields['Jakość']
            if fields.get('Data'):
                otherInfo['released'] = fields['Data']
            if fields.get('Wyświetleń'):
                otherInfo['views'] = fields['Wyświetleń']
            lines = []
            if uploader:
                lines.append(_('Uploader: %s') % uploader)
            if fields.get('Rozmiar'):
                lines.append('Size: %s' % fields['Rozmiar'])
            if fields.get('Pobrań'):
                lines.append(_('Downloads: %s') % fields['Pobrań'])
            keywords = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''name=['"]news_keywords['"]\s+content=['"]([^"^']*?)['"]''')[0])
            if keywords:
                lines.append(keywords)
            if lines:
                text = ' | '.join(lines)
        return [{'title': title, 'text': text or title, 'images': [{'title': '', 'url': icon or self.DEFAULT_ICON_URL}], 'other_info': otherInfo}]

    ###################################################
    # login
    ###################################################
    def tryTologin(self):
        printDBG('NuteczkiEU.tryTologin start')
        login = config.plugins.iptvplayer.nuteczki_login.value
        password = config.plugins.iptvplayer.nuteczki_password.value
        if self.loggedIn is not None and self.login == login and self.password == password:
            return self.loggedIn
        self.login = login
        self.password = password
        self.loggedIn = False
        if not login.strip() or not password.strip():
            return False
        rm(self.COOKIE_FILE)
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header']['Referer'] = self.getMainUrl()
        sts, data = self.getPage(self.getMainUrl(), params, {'login_name': login, 'login_password': password, 'login': 'submit'})
        if sts and 'action=logout' in data:
            printDBG('NuteczkiEU.tryTologin OK')
            self.loggedIn = True
        else:
            msgTab = [_('Login failed.')]
            if sts:
                msgTab.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'alert'), ('</div', '>'), False)[1]))
            self.sessionEx.open(MessageBox, '\n'.join([x for x in msgTab if x]), type=MessageBox.TYPE_ERROR, timeout=10)
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            searchPattern = self.currItem.get('search_pattern', searchPattern)
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page', 'search_pattern': searchPattern})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, NuteczkiEU(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('nuteczki')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'audio' and '.html' in cItem.get('url', '')
