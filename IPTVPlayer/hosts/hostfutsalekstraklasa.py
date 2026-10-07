# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Futsal Ekstraklasa TV (tv.futsalekstraklasa.pl) - official video service of the Polish futsal league:
#   match highlights per season/round, magazine, interviews, statements, press conferences, team pages
# Site: plain HTML, menu = header links, every section has season links (and the highlights section
#   round links), a video tile links to /player/<id>/<slug>.html which carries a direct MP4 <source>
# 03.10.2026 - new host: watched flag, name normalisation, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://tv.futsalekstraklasa.pl/'


class FutsalEkstraklasa(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'raw_title', 'date', 'tag')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'futsalekstraklasa', 'cookie': 'futsalekstraklasa.cookie'})
        self.MAIN_URL = 'https://tv.futsalekstraklasa.pl/'
        self.DEFAULT_ICON_URL = 'https://tv.futsalekstraklasa.pl/static/FOGO_FUTSAL_EKSTRAKLASA_KOLOR.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('futsalekstraklasa')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                vid = self.cm.ph.getSearchGroups(cItem.get('url', ''), r'/player/(\d+)/')[0]
                return 'video:%s' % vid if vid else ''
            if cItem.get('category') in ('list_section', 'list_season', 'list_videos'):
                url = self.wfNormalizeUrlKey(cItem.get('url', ''))
                return 'folder:%s' % url if url else ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _isoDate(text):
        m = re.search(r'(\d{2})/(\d{2})/(\d{4})', text or '')
        return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1)) if m else ''

    def _mediaUrl(self, url):
        # the site stores some paths with Windows backslashes and double slashes, file names with spaces
        if not url:
            return ''
        url = self.getFullUrl(url.replace('\\', '/'))
        url = re.sub(r'(?<!:)//+', '/', url)
        return urllib_quote(url, safe=':/?&=%()+,;@')

    def _normTitle(self, title, tag, date):
        if not IsMediaNamingNormalized():
            return title
        out = title
        if tag and tag.lower() not in title.lower():
            out = '%s - %s' % (title, tag)
        if date:
            out = '%s (%s)' % (out, date)
        return out

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        nav = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="navbar-nav', '</ul>', False)[1]
        seen = set()
        for item in re.findall(r'<a class="header__link" href="([^"]+)"[^>]*>([^<]+)</a>', nav):
            url = self.getFullUrl(item[0])
            title = self.cleanHtmlStr(item[1])
            if not title or not url or item[0] == '#' or url in seen:
                continue
            seen.add(url)
            category = 'list_teams' if '/zespoly' in url else 'list_section'
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': category, 'title': title, 'url': url})
            self.addDir(params)

    def listTeams(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        seen = set()
        for item in re.findall(r'<a href="(/zespol/[^"]+)" class="list__link">(.*?)</a>', data, re.S):
            url = self.getFullUrl(item[0])
            title = self.cleanHtmlStr(item[1])
            if not title:
                title = self.cm.ph.getSearchGroups(item[1], r'title="([^"]+)"')[0]
            if not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item[1], r'src="([^"]+)"')[0]
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_videos', 'title': title, 'url': url,
                           'icon': self.getFullIconUrl(icon) if icon else ''})
            self.addDir(params)

    def _seasonLinks(self, data):
        ret = []
        for url, title in re.findall(r'<a href="([^"]+)" class="subcategory__link[^"]*"\s*>(.*?)</a>', data, re.S):
            title = self.cleanHtmlStr(title)
            if title:
                ret.append((self.getFullUrl(url.replace('&amp;', '&')), title))
        return ret

    def _roundLinks(self, data):
        ret = []
        for url, title in re.findall(r'<a href="([^"]+)" class="subcategory__small__link[^"]*"\s*>(.*?)</a>', data, re.S):
            title = self.cleanHtmlStr(title)
            if title:
                ret.append((self.getFullUrl(url.replace('&amp;', '&')), title))
        return ret

    def listSection(self, cItem):
        # section start page: the season links of the section (if any), otherwise the videos
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        seasons = self._seasonLinks(data)
        if not seasons:
            self._listVideosFromData(cItem, data)
            return
        for url, title in seasons:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_season', 'title': title, 'url': url})
            self.addDir(params)

    def listSeason(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        rounds = self._roundLinks(data)
        if rounds:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': 'list_videos', 'title': _('All videos')})
            self.addDir(params)
            for url, title in rounds:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'list_videos', 'title': title, 'url': url})
                self.addDir(params)
            return
        self._listVideosFromData(cItem, data)

    def listVideos(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self._listVideosFromData(cItem, data)

    def _listVideosFromData(self, cItem, data):
        count = 0
        for item in data.split('<div class="videos__container">')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'href="(/player/[^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2 class="videos__title">', '</h2>', False)[1])
            if not url or not title:
                continue
            title = re.sub(r'\s+-\s+', ' - ', title)
            date = self._isoDate(self.cm.ph.getSearchGroups(item, r'Data dodania:\s*([0-9/]+)')[0])
            tags = [self.cleanHtmlStr(t).lstrip('#') for t in re.findall(r'class="videos__link">([^<]+)<', item)]
            tag = tags[0] if tags else ''
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            desc = [d for d in (date, ' | '.join(tags)) if d]
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'video', 'title': self._normTitle(title, tag, date), 'raw_title': title,
                           'url': self.getFullUrl(url), 'icon': self._mediaUrl(icon), 'date': date, 'tag': tag,
                           'desc': '[/br]'.join(desc)})
            self.addVideo(params)
            count += 1
        if not count:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        # pager: "?page=N", <span class="last"> = the last page
        page = cItem.get('page', 1)
        base = re.sub(r'[?&]page=\d+', '', cItem['url'])
        hasNext = bool(self.cm.ph.getSearchGroups(data, r'<span class="next"><a href="([^"]+)"')[0])
        lastPage = self.cm.ph.getSearchGroups(data, r'<span class="last"><a href="[^"]*[?&]page=(\d+)')[0]
        lastPage = int(lastPage) if lastPage else (page if not hasNext else 0)
        params = dict(cItem)
        params['category'] = 'list_videos'
        addPagingItems(self, params, page, hasNext, lastPage, base + ('&' if '?' in base else '?') + 'page={page}')

    ###################################################
    # links
    ###################################################
    def _playerData(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None, ''
        return data, self.cm.ph.getSearchGroups(data, r'''<source[^>]+src=['"]([^'"]+)['"]''')[0]

    def getLinksForVideo(self, cItem):
        printDBG("FutsalEkstraklasa.getLinksForVideo [%s]" % cItem.get('url'))
        data, src = self._playerData(cItem['url'])
        if data is None:
            return []
        urlTab = []
        if src:
            src = self._mediaUrl(src)
            urlTab.append({'name': 'MP4', 'url': self.up.decorateUrl(src, {'Referer': self.getMainUrl(), 'User-Agent': self.HEADER['User-Agent']}), 'need_resolve': 0})
        else:
            frame = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=['"]([^'"]+)['"]''')[0]
            if frame and 1 == self.up.checkHostSupport(self.getFullUrl(frame)):
                urlTab.append({'name': self.up.getHostName(self.getFullUrl(frame)), 'url': self.getFullUrl(frame), 'need_resolve': 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'class="player__title">', '</h1>', False)[1])
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), title or cItem.get('raw_title', '')))

    def getVideoLinks(self, videoUrl):
        printDBG("FutsalEkstraklasa.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('date'):
            other['released'] = cItem['date']
        if cItem.get('tag'):
            other['genre'] = cItem['tag']
        title = cItem.get('raw_title', '') or cItem.get('title', '')
        sts, data = self.getPage(cItem.get('url', '')) if cItem.get('type') == 'video' else (False, '')
        if sts:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'class="player__title">', '</h1>', False)[1]) or title
        icon = cItem.get('icon', '')
        return [{'title': title, 'text': cItem.get('desc', ''), 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("FutsalEkstraklasa.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_section':
            self.listSection(self.currItem)
        elif category == 'list_season':
            self.listSeason(self.currItem)
        elif category == 'list_videos':
            self.listVideos(self.currItem)
        elif category == 'list_teams':
            self.listTeams(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FutsalEkstraklasa(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('futsalekstraklasa')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
