# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Watch Wrestling (watchwrestling.ae, formerly watchwrestling.la / .uno) - WWE / AEW / TNA / ROH / NJPW / UFC show replays
# Site: WordPress (menu categories, /page/N/ paging, ?s= search). The server buttons of a show are in a hidden
#   <textarea> ("episodeRepeater": server name + Part 1..N) -> away.php?to=post.php?id=..&part=.. -> <iframe>
#   fastvid.xyz/watch?.. -> hoster <iframe> (dailymotion, ok.ru, ...) or an own JW Player with a base64 HLS url.
# 03.10.2026 - revived for watchwrestling.ae: watched flag, name normalisation, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
###################################################

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
MONTH_RE = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
EN_DASH = '–'  # utf-8 literal: bytes on py2, a character on py3 - like the titles cleanHtmlStr returns


def GetConfigList():
    return []


def gettytul():
    return 'https://watchwrestling.ae/'


class WatchwrestlingUNO(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'raw_title')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'watchwrestling.la', 'cookie': 'watchwrestling.uno.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = ''  # the site has a text logo only
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('watchwrestlinguno')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            url = self._stableUrl(cItem.get('url', ''))
            if not url:
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                return 'video:%s' % url
            if cItem.get('category') == 'list_items':
                return 'folder:%s' % url
        except Exception:
            printExc()
        return ''

    def _stableUrl(self, url):
        # path only (the site moves between domains), without the /page/N/ paging
        url = str(url or '').strip()
        if not url or '?s=' in url:
            return ''
        url = re.sub(r'^https?://[^/]+', '', url)
        url = re.sub(r'/page/\d+/?$', '/', url)
        return url

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

    ###################################################
    # naming
    ###################################################
    def _parseDate(self, text):
        # "2nd October 2026" (title tail), else "October 2nd, 2026"
        m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+' + MONTH_RE + r',?\s+(\d{4})', text or '', re.I)
        if m:
            return '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
        m = re.search(r'\b' + MONTH_RE + r'\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', text or '', re.I)
        if m:
            return '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
        return ''

    def _normTitle(self, title):
        # "WWE Smackdown 10/2/26 - 2nd October 2026" -> "WWE Smackdown (2026-10-02)"
        if not IsMediaNamingNormalized():
            return title
        try:
            date = self._parseDate(title)
            if not date:
                return title
            out = title.replace(EN_DASH, '-')
            out = re.sub(r'\s*-\s*\d{1,2}(?:st|nd|rd|th)?\s+' + MONTH_RE + r',?\s+\d{4}\s*$', '', out, flags=re.I)
            out = re.sub(r'\s+\d{1,2}/\d{1,2}/\d{2,4}\b', '', out).strip(' -')
            return '%s (%s)' % (out or title, date)
        except Exception:
            printExc()
        return title

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(data.meta.get('url', self.getMainUrl()))
        params = dict(cItem)
        params.update({'category': 'list_items', 'title': _('Latest'), 'url': self.getMainUrl()})
        self.addDir(params)
        menu = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu-primary-menu'), ('</ul', '>'), False)[1]
        for url, title in re.findall(r'<li[^>]+menu-item-object-category[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>', menu):
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'good_for_fav': True})
            self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listItems(self, cItem):
        printDBG("WatchwrestlingUNO.listItems [%s]" % cItem['url'])
        base = cItem.get('base_url') or cItem['url']
        page = int(cItem.get('page', 1) or 1)
        # WordPress paging: <path>/page/N/[?s=...]
        path, query = (base.split('?', 1) + [''])[:2]
        tpl = path.rstrip('/') + '/page/{page}/' + ('?' + query if query else '')
        sts, data = self.getPage(base if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        hasNext = bool(self.cm.ph.getSearchGroups(data, r'<a class="next" href="([^"]+)"')[0])
        content = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'loop-content'), ('<div', '>', 'id="sidebar"'), False)[1] or data
        items = self.cm.ph.getAllItemsBeetwenMarkers(content, '<div id="', '<!-- end #post-')
        for item in items:
            if 'class="clip-link"' not in item:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'class="clip-link"[^>]+href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="clip-link"[^>]+title="([^"]+)"')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'entry-summary'), ('</p', '>'), False)[1])
            if not url or not title:
                continue
            params = {'name': 'category', 'good_for_fav': True, 'category': 'video', 'title': self._normTitle(title), 'raw_title': title,
                      'url': url, 'icon': icon, 'desc': desc}
            self.addVideo(params)
        if items:
            addPagingItems(self, dict(cItem, base_url=base), page, hasNext, 0, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        if not cItem.get('url'):
            cItem['url'] = self.getFullUrl('/?s=%s' % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("WatchwrestlingUNO.getLinksForVideo [%s]" % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        urlTab = []
        seen = set()
        names = {}
        for server, block in re.findall(r"<div class=.episodeRepeater.>\s*<h1>([^<]+)</h1>(.*?)</div>", data, re.S):
            server = re.sub(r'^Watch\s+', '', self.cleanHtmlStr(server), flags=re.I) or _('Server')
            names[server] = names.get(server, 0) + 1
            if names[server] > 1:
                server = '%s #%d' % (server, names[server])
            parts = re.findall(r"<a[^>]+href=.([^'\"]+).[^>]*>(.*?)</a>", block, re.S)
            for url, text in parts:
                url = url.replace('&amp;', '&')
                if 'to=' in url:
                    url = urllib_unquote(url.split('to=', 1)[1].split('&', 1)[0])
                if not self.cm.isValidUrl(url) or url in seen:
                    continue
                seen.add(url)
                text = self.cleanHtmlStr(text)
                name = '%s - %s' % (server, text) if len(parts) > 1 and text else server
                urlTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})
        if not urlTab:
            # older posts embed the player directly
            body = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'entry-content'), ('<div', '>', 'id="extras"'), False)[1]
            for url in re.findall(r'<iframe[^>]+src=["\']([^"\']+)', body, re.I):
                url = 'https:' + url if url.startswith('//') else url
                if self.cm.isValidUrl(url) and url not in seen:
                    seen.add(url)
                    urlTab.append({'name': self.up.getHostName(url), 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', ''))))

    def _playerMedia(self, data, url):
        # own JW Player of the link page: file:window.atob("..") or a plain file:"..."
        media = self.cm.ph.getSearchGroups(data, r'''file\s*:\s*window\.atob\(\s*["']([^"']+)["']''')[0]
        if media:
            try:
                media = b64Decode(media)
            except Exception:
                printExc()
                media = ''
        else:
            media = self.cm.ph.getSearchGroups(data, r'''file\s*:\s*["'](https?://[^"']+)["']''')[0]
        if not self.cm.isValidUrl(media):
            return []
        meta = {'Referer': url, 'Origin': self.cm.getBaseUrl(url)[:-1], 'User-Agent': self.HEADER['User-Agent']}
        if '.m3u8' in media:
            links = getDirectM3U8Playlist(strwithmeta(media, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        else:
            links = [{'name': 'MP4', 'url': strwithmeta(media, meta)}]
        for it in links:
            it['need_resolve'] = 0
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("WatchwrestlingUNO.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = videoUrl
        referer = videoUrl.meta.get('Referer', self.getMainUrl())
        # post.php -> fastvid player page -> hoster iframe or own JW Player
        for _level in range(3):
            if 1 == self.up.checkHostSupport(url):
                return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(url, {'Referer': referer})), sidecar)
            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER, Referer=referer)
            sts, data = self.getPage(url, params)
            if not sts:
                return []
            links = self._playerMedia(data, url)
            if links:
                return decorateResolvedLinkItems(links, sidecar)
            frame = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']([^"']+)["']''', ignoreCase=True)[0].replace('&amp;', '&')
            if frame.startswith('//'):
                frame = 'https:' + frame
            if not self.cm.isValidUrl(frame):
                break
            referer, url = url, frame
        SetIPTVPlayerLastHostError(_("Content not available"))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WatchwrestlingUNO.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('raw_title') or cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        sts, data = self.getPage(cItem['url'])
        if sts:
            body = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'entry-content'), ('<div', '>', 'id="extras"'), False)[1]
            body = re.sub(r'<div class=.counter-wrapper.*?(?=<h1)', '', body, flags=re.S)
            lines = []
            for tag, para in re.findall(r'<(p|h1|li)[^>]*>(.*?)</\1>', body, re.S):
                para = self.cleanHtmlStr(para)
                if para:
                    lines.append(('- ' + para) if tag == 'li' else para)
            if lines:
                text = '[/br]'.join(lines)
            big = self.cm.ph.getSearchGroups(body, r'<img[^>]+src="([^"]+)"')[0]
            icon = self.getFullIconUrl(big) if big else icon
            cats = re.findall(r'rel="category tag">([^<]+)<', data)
            if cats:
                other['genres'] = ', '.join(self.cleanHtmlStr(c) for c in cats)
        date = self._parseDate(title)
        if date:
            other['released'] = date
        return [{'title': self.cleanHtmlStr(title), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("WatchwrestlingUNO.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'list_items'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WatchwrestlingUNO(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('watchwrestlinguno')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
