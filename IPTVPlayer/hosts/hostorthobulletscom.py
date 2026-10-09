# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# 09.08.2025 - Codermik (codermik@tuta.io)
# Orthobullets (orthobullets.com) - orthopaedic video library. The lists are public, every video page
# needs a (free) Medbullets account: without one only videos with a YouTube cover play (the YouTube video).
# 08.10.2026 - paging (First page / Jump / Next page with the last page), watched flag, download marker,
#   favourites of the category lists, INFO (date, views, topic, authors), sidecar, YouTube videos without
#   an account, login only when a video is opened (once more when the session has expired), no colour codes,
#   current user agent
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
###################################################

###################################################
# FOREIGN import
###################################################
import re
from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.orthobulletscom_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.orthobulletscom_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.orthobulletscom_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.orthobulletscom_password))
    return optionList
###################################################


def gettytul():
    return 'https://orthobullets.com/'


class OrthoBullets(GenericFolderWatchedScraperMixin, CBaseHostClass):
    PAGE_SIZE = 50  # videos per list page of the site

    def __init__(self):
        printDBG("..:: E2iStream ::..   __init__(self):")
        CBaseHostClass.__init__(self, {'history': 'orthobullets.com', 'cookie': 'orthobullets.com.cookie'})

        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

        self.MAIN_URL = 'https://www.orthobullets.com/'
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/orthobulletscom135.png')

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.watchedHelper = IPTVWatchedHelper('orthobulletscom')
        self.wfInitFolderCache()

        self.MAIN_CAT_TAB = [
                            {'category': 'categories', 'title': _('Categories'), 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                            {'category': 'subspeciality', 'title': _('Subspecialities'), 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL}
                            ] + self.searchItems()

        self.CATEGORIES_TAB = [
                                    {'category': 'list_categories', 'title': _('All'), 'url': self.MAIN_URL + 'video/list.aspx'},
                                    {'category': 'list_categories', 'title': _('Board Review'), 'url': self.MAIN_URL + 'video/list.aspx?c=7'},
                                    {'category': 'list_categories', 'title': _('CME SAE'), 'url': self.MAIN_URL + 'video/list.aspx?c=20'},
                                    {'category': 'list_categories', 'title': _('Educational Animation'), 'url': self.MAIN_URL + 'video/list.aspx?c=109'},
                                    {'category': 'list_categories', 'title': _('Ethical & Legal'), 'url': self.MAIN_URL + 'video/list.aspx?c=10'},
                                    {'category': 'list_categories', 'title': _('Exam Review'), 'url': self.MAIN_URL + 'video/list.aspx?c=19'},
                                    {'category': 'list_categories', 'title': _('Humanitarian'), 'url': self.MAIN_URL + 'video/list.aspx?c=8'},
                                    {'category': 'list_categories', 'title': _('Industry'), 'url': self.MAIN_URL + 'video/list.aspx?c=107'},
                                    {'category': 'list_categories', 'title': _('Interactive Learning Center(ILC)'), 'url': self.MAIN_URL + 'video/list.aspx?c=17'},
                                    {'category': 'list_categories', 'title': _('Jobs & Positions'), 'url': self.MAIN_URL + 'video/list.aspx?c=14'},
                                    {'category': 'list_categories', 'title': _('Journal Club'), 'url': self.MAIN_URL + 'video/list.aspx?c=9'},
                                    {'category': 'list_categories', 'title': _('Medtryx Marketing'), 'url': self.MAIN_URL + 'video/list.aspx?c=24'},
                                    {'category': 'list_categories', 'title': _('Meetings'), 'url': self.MAIN_URL + 'video/list.aspx?c=12'},
                                    {'category': 'list_categories', 'title': _('Pathology Rounds'), 'url': self.MAIN_URL + 'video/list.aspx?c=16'},
                                    {'category': 'list_categories', 'title': _('Physical Exam'), 'url': self.MAIN_URL + 'video/list.aspx?c=5'},
                                    {'category': 'list_categories', 'title': _('Powerpoint Presentation'), 'url': self.MAIN_URL + 'video/list.aspx?c=108'},
                                    {'category': 'list_categories', 'title': _('Practice Management'), 'url': self.MAIN_URL + 'video/list.aspx?c=11'},
                                    {'category': 'list_categories', 'title': _('Professional Networks'), 'url': self.MAIN_URL + 'video/list.aspx?c=13'},
                                    {'category': 'list_categories', 'title': _('Radiology Rounds'), 'url': self.MAIN_URL + 'video/list.aspx?c=15'},
                                    {'category': 'list_categories', 'title': _('Study Plan'), 'url': self.MAIN_URL + 'video/list.aspx?c=21'},
                                    {'category': 'list_categories', 'title': _('Surgical Approaches'), 'url': self.MAIN_URL + 'video/list.aspx?c=3'},
                                    {'category': 'list_categories', 'title': _('Surgical Cases'), 'url': self.MAIN_URL + 'video/list.aspx?c=100'},
                                    {'category': 'list_categories', 'title': _('Surgical Complications'), 'url': self.MAIN_URL + 'video/list.aspx?c=4'},
                                    {'category': 'list_categories', 'title': _('Surgical Techniques'), 'url': self.MAIN_URL + 'video/list.aspx?c=2'},
                                    {'category': 'list_categories', 'title': _('Techniques'), 'url': self.MAIN_URL + 'video/list.aspx?c=106'},
                                    {'category': 'list_categories', 'title': _('Treatment Consult'), 'url': self.MAIN_URL + 'video/list.aspx?c=1'},
                                    {'category': 'list_categories', 'title': _('Written Boards Review'), 'url': self.MAIN_URL + 'video/list.aspx?c=102'}
                                ]

        self.SPECIALITY_TAB = [
                                    {'category': 'list_speciality', 'title': _('Trauma'), 'url': self.MAIN_URL + 'video/list.aspx?s=1'},
                                    {'category': 'list_speciality', 'title': _('Spine'), 'url': self.MAIN_URL + 'video/list.aspx?s=2'},
                                    {'category': 'list_speciality', 'title': _('Shoulder & Elbow'), 'url': self.MAIN_URL + 'video/list.aspx?s=3'},
                                    {'category': 'list_speciality', 'title': _('Knee & Sports'), 'url': self.MAIN_URL + 'video/list.aspx?s=225'},
                                    {'category': 'list_speciality', 'title': _('Pediatrics'), 'url': self.MAIN_URL + 'video/list.aspx?s=4'},
                                    {'category': 'list_speciality', 'title': _('Recon'), 'url': self.MAIN_URL + 'video/list.aspx?s=5'},
                                    {'category': 'list_speciality', 'title': _('Hand'), 'url': self.MAIN_URL + 'video/list.aspx?s=6'},
                                    {'category': 'list_speciality', 'title': _('Foot & Ankle'), 'url': self.MAIN_URL + 'video/list.aspx?s=7'},
                                    {'category': 'list_speciality', 'title': _('Pathology'), 'url': self.MAIN_URL + 'video/list.aspx?s=8'},
                                    {'category': 'list_speciality', 'title': _('Basic Science'), 'url': self.MAIN_URL + 'video/list.aspx?s=9'},
                                    {'category': 'list_speciality', 'title': _('Anatomy'), 'url': self.MAIN_URL + 'video/list.aspx?s=10'},
                                    {'category': 'list_speciality', 'title': _('Approaches'), 'url': self.MAIN_URL + 'video/list.aspx?s=12'},
                                    {'category': 'list_speciality', 'title': _('General'), 'url': self.MAIN_URL + 'video/list.aspx?s=13'},
                                ]
        # the category lists are static urls: favourites reopen them as they are
        for item in self.CATEGORIES_TAB + self.SPECIALITY_TAB:
            item['good_for_fav'] = True

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    @staticmethod
    def _baseListUrl(url):
        # the list url without its page parameter ("...list.aspx?c=7&p=3" -> "...list.aspx?c=7")
        url = re.sub(r'([?&])p=\d+(&|$)', lambda m: m.group(1) if m.group(2) else '', url)
        return url.rstrip('?&')

    @staticmethod
    def _videoId(url):
        return re.search(r'[?&]id=(\d+)', url or '')

    def listItems(self, cItem):
        printDBG("..:: E2iStream ::.. -  listItems(self, cItem): [%s]" % cItem)
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        baseUrl = self._baseListUrl(cItem['url'])
        pageUrlTpl = baseUrl + ('&' if '?' in baseUrl else '?') + 'p={page}'
        url = pageUrlTpl.format(page=page) if page > 1 else baseUrl

        sts, data = self.getPage(url)
        if not sts:
            return

        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videos ', 'group-items-list__bottom-paging', False)[1]
        for video in block.split('dashboard-item--video')[1:]:
            self._addVideoRow(video)

        total = self.cm.ph.getSearchGroups(data, r'''([0-9][0-9,.]*)\s+matches\s+found''')[0]
        try:
            lastPage = (int(re.sub(r'[,.]', '', total)) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        except ValueError:
            lastPage = 0
        hasNext = page < lastPage if lastPage else ('p=%d' % (page + 1)) in data
        addPagingItems(self, cItem, page, hasNext, lastPage, pageUrlTpl)

    def _addVideoRow(self, video):
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(video, ('<div', '>', 'dashboard-item__title'), ('</div', '>'), False)[1])
        videoUrl = self.cm.ph.getSearchGroups(video, '''<a[^>]+?href=['"]([^'"]+?)['"]''')[0]
        if not title or not videoUrl:
            return
        videoUrl = self.getFullUrl(videoUrl.replace('&amp;', '&'))
        icon = self.cm.ph.getSearchGroups(video, r'''background-image:\s*url\(['"]?([^'")]+)''')[0].replace('&amp;', '&')
        if icon.startswith('//'):
            icon = 'https:' + icon
        date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(video, ('<div', '>', 'dashboard-item__date'), ('</div', '>'), False)[1])
        views = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(video, ('<div', '>', 'dashboard-item__views'), ('</div', '>'), False)[1])
        authors = [self.cleanHtmlStr(x) for x in self.cm.ph.getAllItemsBeetwenNodes(video, ('<div', '>', 'user-profile-popup'), ('</div', '>'), False)]
        authors = [x for x in authors if x]
        topic = ' '.join([self.cleanHtmlStr(x) for x in self.cm.ph.getAllItemsBeetwenNodes(video, ('<span', '>', 'dashboardBreadcrumbs-link'), ('</span', '>'), False)])
        ytId = self.cm.ph.getSearchGroups(icon, r'(?:img\.youtube\.com|i\.ytimg\.com)/vi/([A-Za-z0-9_-]{11})/')[0]
        desc = ' | '.join([x for x in (date, views, topic) if x])
        if authors:
            desc += '[/br]' + ', '.join(authors)
        self.addVideo({'name': 'category', 'category': 'video', 'good_for_fav': True, 'title': title, 'url': videoUrl, 'icon': icon,
                       'desc': desc, 'date': date, 'views': views, 'topic': topic, 'authors': ', '.join(authors), 'yt_id': ytId})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OrthoBullets.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/video/list.aspx?search=') + urllib_quote(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("OrthoBullets.getLinksForVideo [%s]" % cItem)
        urlTab = []
        for _attempt in range(2):
            if not self.tryTologin():
                break
            sts, data = self.getPage(cItem['url'])
            if not sts:
                break
            if not self._isSiteUrl(self.cm.meta.get('url', '')):
                # redirected to the medbullets login: the session has expired, log in once more
                self.loggedIn = None
                continue
            frames = re.findall(r'''<iframe[^>]+?src=['"]([^"']+?)['"]''', data, re.I)
            frames = [self.getFullUrl(x.replace('&amp;', '&')) for x in frames]
            players = [x for x in frames if re.search(r'vimeo|youtu|wistia|jwplayer|brightcove|vidyard', x, re.I)]
            for url in (players or frames)[:1]:
                urlTab = self.up.getVideoLinkExt(strwithmeta(url, {'Referer': self.cm.meta['url']}))
            break
        if not urlTab and cItem.get('yt_id'):
            # the YouTube cover of the list is the video itself - it plays without an account
            urlTab = [{'name': 'YouTube', 'url': 'https://www.youtube.com/watch?v=' + cItem['yt_id'], 'need_resolve': 1}]
        if not urlTab:
            if self.loggedIn:
                SetIPTVPlayerLastHostError(_("Content not available"))
            else:
                SetIPTVPlayerLastHostError(_('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.') % 'orthobullets.com')
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("OrthoBullets.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('date'):
            other['released'] = cItem['date']
        if cItem.get('views'):
            other['views'] = cItem['views']
        if cItem.get('topic'):
            other['category'] = cItem['topic']
        if cItem.get('authors'):
            other['creators'] = cItem['authors']
        icon = cItem.get('icon', '')
        images = [{'title': '', 'url': icon}] if icon.startswith('http') else []
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', '').replace('[/br]', '\n') or cItem.get('title', ''),
                 'images': images, 'other_info': other}]

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                m = self._videoId(cItem.get('url', ''))
                return 'video:%s' % m.group(1) if m else ''
            if cItem.get('category') in ('list_categories', 'list_speciality'):
                url = self._baseListUrl(cItem.get('url', ''))
                return 'folder:%s' % re.sub(r'^https?://[^/]+', '', url) if url else ''
        except Exception:
            printExc()
        return ''

    def _isSiteUrl(self, url):
        # the host itself, not a medbullets login url that only carries orthobullets.com in its return url
        domain = self.cm.getBaseUrl(url or '', True).lower()
        return domain == 'orthobullets.com' or domain.endswith('.orthobullets.com')

    def _getFormData(self, data, cUrl):
        # the first form of the page: (action url, its named input / button values); ('', {}) without a form
        sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
        if not sts:
            return '', {}
        action = self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&')
        actionUrl = urljoin(cUrl, action) if action else cUrl
        post_data = {}
        inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
        inputData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
        for item in inputData:
            name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
            if name:
                post_data[name] = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&')
        return actionUrl, post_data

    def tryTologin(self):
        printDBG('tryTologin start')
        if None is self.loggedIn or self.login != config.plugins.iptvplayer.orthobulletscom_login.value or\
                self.password != config.plugins.iptvplayer.orthobulletscom_password.value:

            self.login = config.plugins.iptvplayer.orthobulletscom_login.value
            self.password = config.plugins.iptvplayer.orthobulletscom_password.value

            self.loggedIn = False

            # the lists are public: without an account nothing is asked here, a video tells the user
            if '' == self.login.strip() or '' == self.password.strip():
                return False

            rm(self.COOKIE_FILE)

            # orthobullets.com/login redirects to the login form of accounts.medbullets.com
            sts, data = self.getPage(self.getFullUrl('/login'))
            if not sts:
                self.loggedIn = None  # no answer: try again with the next video
                return False
            cUrl = self.cm.meta['url']

            actionUrl, post_data = self._getFormData(data, cUrl)
            if actionUrl:
                post_data.update({'Username': self.login, 'Password': self.password, 'RememberLogin': 'true'})
                httpParams = dict(self.defaultParams)
                httpParams['header'] = dict(httpParams['header'], Referer=cUrl)
                sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
                if sts:
                    # response_mode=form_post: the callback page posts the tokens back to orthobullets.com/signin-oidc
                    # (a wrong password shows the login form again, its second post fails the check below)
                    cUrl = self.cm.meta['url']
                    actionUrl, post_data = self._getFormData(data, cUrl)
                    if actionUrl:
                        httpParams['header']['Referer'] = cUrl
                        sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
                        if sts and '/logout' in data and self._isSiteUrl(self.cm.meta['url']):
                            printDBG('tryTologin OK')
                            self.loggedIn = True

            if not self.loggedIn:
                self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name [%s], category [%s], mode [%s] " % (name, category, mode))

        self.currList = []

        # First Menu

        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, self.currItem)
        elif category == 'categories':
            self.listsTab(self.CATEGORIES_TAB, self.currItem)
        elif category == 'subspeciality':
            self.listsTab(self.SPECIALITY_TAB, self.currItem)
        elif category in ('list_items', 'list_categories', 'list_speciality'):
            self.listItems(self.currItem)

        # Searching / Search History

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
        CHostBase.__init__(self, OrthoBullets(), True, favouriteTypes=[])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('orthobulletscom')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
