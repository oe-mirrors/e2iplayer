# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# PZPN+ (pzpnplus.pl) - the digital platform of the Polish football federation: free live streams and
#   replays of Betclic 2. Liga, Ekstraliga Kobiet, STS Puchar Polski, youth national teams, highlights,
#   magazines and archive matches; team / league pages
# Site: React app of the BetterMedia OTT platform (api-2e87.bettermedia.tv, tenant pzpnplus.pl): anonymous
#   sign-in token, the menu rows come from the web configuration (Screens -> LIST components = media lists),
#   streams via Media/GetMediaPlayInfo (MUX / internal HLS). Only free content - paid items get a message.
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
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
# FOREIGN import
###################################################
import re
import time
import uuid
from datetime import datetime, timedelta
###################################################

API_URL = 'https://api-2e87.bettermedia.tv'
TENANT = 'https://pzpnplus.pl'
# lists that need a logged-in user (favourites, recently watched, recommendations)
PRIVATE_LISTS = (98, 201, 225, 267, 269)
SCREEN_LISTS = {'LEAGUE': 'LEAGUE_DETAILS', 'TEAM': 'TEAM_DETAILS'}
PLAYABLE_TYPES = ('VOD', 'EPISODE', 'MATCH', 'EVENT', 'LIVE', 'CHANNEL', 'PROGRAM')


def GetConfigList():
    return []


def gettytul():
    return 'https://pzpnplus.pl/'


class PZPNPlus(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'media_id', 'title', 'raw_title', 'icon', 'desc', 'date', 'paid', 'live')
    PAGE_SIZE = 30

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'pzpnpluspl', 'cookie': 'pzpnpluspl.cookie'})
        self.MAIN_URL = TENANT + '/'
        self.DEFAULT_ICON_URL = TENANT + '/images/icons/icon-1200x630.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Origin': TENANT, 'Referer': TENANT + '/', 'X-TenantOrigin': TENANT})
        self.token = ''
        self.deviceId = str(uuid.uuid4())
        self.screens = None
        self.watchedHelper = IPTVWatchedHelper('pzpnpluspl')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                if cItem.get('live'):
                    return ''
                return 'video:%s' % cItem['media_id'] if cItem.get('media_id') else ''
            if cItem.get('category') in ('list_media', 'list_series', 'list_screen') and cItem.get('media_id'):
                return 'folder:%s:%s' % (cItem['media_id'], cItem.get('list_id', ''))
        except Exception:
            printExc()
        return ''

    ###################################################
    # API
    ###################################################
    def _signIn(self):
        header = dict(self.HEADER)
        header['Content-Type'] = 'application/json; charset=UTF-8'
        post = json_dumps({'Device': {'PlatformCode': 'WEB', 'Name': 'E2iPlayer', 'DeviceId': self.deviceId}})
        sts, data = self.cm.getPage(API_URL + '/Authorization/SignIn', {'header': header, 'raw_post_data': True}, post)
        self.token = ''
        if sts:
            try:
                self.token = (json_loads(data).get('AuthorizationToken') or {}).get('Token') or ''
            except Exception:
                printExc()
        return bool(self.token)

    def _post(self, path, payload):
        for attempt in (0, 1):
            if not self.token and not self._signIn():
                return None
            header = dict(self.HEADER)
            header.update({'Content-Type': 'application/json; charset=UTF-8', 'Authorization': 'Bearer %s' % self.token})
            sts, data = self.cm.getPage(API_URL + path, {'header': header, 'raw_post_data': True}, json_dumps(payload))
            if sts:
                try:
                    return json_loads(data)
                except Exception:
                    printExc()
                    return None
            # expired token -> sign in again once
            self.token = ''
        return None

    def _screens(self):
        if self.screens is None:
            header = dict(self.HEADER)
            sts, data = self.cm.getPage(API_URL + '/Configurations/GetConfiguration?platformCode=WEB', {'header': header})
            screens = {}
            if sts:
                try:
                    screens = json_loads(data).get('Screens') or {}
                except Exception:
                    printExc()
            if not screens:
                return {}
            self.screens = screens
        return self.screens

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _image(entity, order=('FRAME', 'HIGHLIGHTS', 'COVER', 'SQUARE', 'ROUND', 'BACKGROUND', 'LOGO')):
        images = entity.get('Images') or []
        for code in order:
            for img in images:
                if isinstance(img, dict) and img.get('ImageTypeCode') == code and img.get('Url'):
                    return img['Url']
        for img in images:
            if isinstance(img, dict) and img.get('Url'):
                return img['Url']
        return ''

    @staticmethod
    def _parseTime(value):
        try:
            return datetime.strptime(value[:19], '%Y-%m-%dT%H:%M:%S')
        except Exception:
            return None

    def _isLive(self, entity):
        if entity.get('MediaTypeCode') not in ('MATCH', 'EVENT', 'LIVE', 'CHANNEL'):
            return False
        start = self._parseTime(entity.get('StartDateTime') or '')
        end = self._parseTime(entity.get('EndDateTime') or '')
        now = datetime(*time.gmtime()[:6])
        if entity.get('MediaTypeCode') in ('LIVE', 'CHANNEL'):
            return True
        return bool(start and start <= now and (end is None or end > now))

    def _title(self, title, date):
        if not IsMediaNamingNormalized() or not date:
            return title
        if date[:4] in title or re.search(r'\d{1,2}\.\d{2}\.\d{4}', title):
            # archive matches carry their match date in the title already
            return title
        return '%s (%s)' % (title, date)

    @staticmethod
    def _duration(ms):
        try:
            secs = int(ms or 0) // 1000
            return str(timedelta(seconds=secs)) if secs > 0 else ''
        except Exception:
            return ''

    def _addEntity(self, cItem, e):
        if not isinstance(e, dict) or not e.get('Id') or not e.get('Title'):
            return False
        mtype = e.get('MediaTypeCode') or ''
        title = self.cleanHtmlStr(e['Title'])
        icon = self._image(e)
        desc = self.cleanHtmlStr(e.get('ShortDescription') or e.get('Description') or '')
        params = stripPagerKeys(dict(cItem), ('list_id', 'url'))
        if mtype in SCREEN_LISTS:
            params.update({'good_for_fav': True, 'category': 'list_screen', 'title': title, 'media_id': e['Id'], 'screen': SCREEN_LISTS[mtype],
                           'icon': icon, 'desc': desc})
            self.addDir(params)
            return True
        if mtype == 'SERIES':
            params.update({'good_for_fav': True, 'category': 'list_series', 'title': title, 'media_id': e['Id'], 'icon': icon, 'desc': desc})
            self.addDir(params)
            return True
        if mtype not in PLAYABLE_TYPES:
            return False
        live = self._isLive(e)
        if not e.get('IsPlayable') and not live:
            # upcoming broadcast / not yet available
            return False
        when = e.get('StartDateTime') or e.get('AvailableFrom') or ''
        date = when[:10] if len(when) >= 10 else ''
        info = [x for x in (self._duration(e.get('Duration')), date, e.get('MediaTypeDisplayName') or '') if x]
        paid = not e.get('IsFree', True)
        if paid:
            info.insert(0, _('Paid content'))
        if live:
            info.insert(0, _('Live'))
        params.update({'good_for_fav': True, 'category': 'video', 'type': 'video', 'title': title if live else self._title(title, date), 'raw_title': title,
                       'media_id': e.get('PlayableMediaId') or e['Id'], 'url': '%s/movie-details/%s' % (TENANT, e['Id']), 'icon': icon,
                       'date': date, 'paid': paid, 'live': live, 'desc': ' | '.join(info) + ('[/br]' + desc if desc else '')})
        self.addVideo(params)
        return True

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        screens = self._screens()
        seen = set()
        titles = set()
        components = [('', c) for c in ((screens.get('HOME') or {}).get('Components') or [])]
        custom = screens.get('CUSTOM') or {}
        for key in sorted(custom.keys()):
            screenName = self.cleanHtmlStr((custom[key] or {}).get('Name') or '')
            components.extend([(screenName, c) for c in ((custom[key] or {}).get('Components') or [])])
        for screenName, c in components:
            sid = c.get('SourceId')
            if c.get('ComponentTypeCode') != 'LIST' or not sid or sid in seen or sid in PRIVATE_LISTS:
                continue
            seen.add(sid)
            title = self.cleanHtmlStr(c.get('Title') or '') or re.sub(r'^(?:Home|Common|Fan zone)\s*-\s*', '', self.cleanHtmlStr(c.get('SourceName') or ''))
            if not title:
                continue
            if title in titles and screenName:
                # e.g. two "Druzyny" rows: the Ekstraliga Kobiet clubs (home) and all teams ("Strefa kibica")
                title = '%s (%s)' % (title, screenName)
            titles.add(title)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_media', 'title': title, 'list_id': sid})
            self.addDir(params)
        if not seen:
            SetIPTVPlayerLastHostError(_("Loading failed."))
        for item in self.searchItems():
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listMedia(self, cItem):
        page = cItem.get('page', 1)
        payload = {'MediaListId': cItem['list_id'], 'IncludeCount': True, 'IncludeImages': True, 'PageNumber': page, 'PageSize': self.PAGE_SIZE}
        if cItem.get('media_id'):
            payload['MediaId'] = cItem['media_id']
        self._listEntities(cItem, page, lambda pg: self._post('/Media/GetMediaList', dict(payload, PageNumber=pg)))

    def _listEntities(self, cItem, page, fetch):
        # upcoming (not yet playable) broadcasts are left out, so a page can turn out empty -> read on
        # (max. 5 pages) instead of showing an empty list / a "Next page" into nothing
        count = 0
        lastPage = 0
        more = False
        for _i in range(5):
            data = fetch(page)
            if not isinstance(data, dict):
                return
            entities = data.get('Entities') or []
            for e in entities:
                if self._addEntity(cItem, e):
                    count += 1
            try:
                total = int(data.get('TotalCount') or 0)
            except Exception:
                total = 0
            lastPage = (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE
            more = page < lastPage and len(entities) > 0
            if count or not more:
                break
            page += 1
        if count:
            # POST API: the template only serves "Jump" (the list is fetched by cItem['page'])
            tpl = '%s/#list=%s&media=%s&page={page}' % (TENANT, cItem.get('list_id', 'search'), cItem.get('media_id', ''))
            addPagingItems(self, cItem, page, more, lastPage, tpl)
        else:
            SetIPTVPlayerLastHostError(_("Nothing available here at the moment (only upcoming broadcasts)."))

    def listScreen(self, cItem):
        # league / team page: its lists (ongoing, replays, teams, ...) scoped to this media
        for c in ((self._screens().get(cItem.get('screen', '')) or {}).get('Components') or []):
            sid = c.get('SourceId')
            if c.get('ComponentTypeCode') != 'LIST' or not sid or sid in PRIVATE_LISTS:
                continue
            title = self.cleanHtmlStr(c.get('Title') or c.get('SourceName') or '')
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_media', 'title': title, 'list_id': sid})
            self.addDir(params)

    def listSeries(self, cItem):
        data = self._post('/Media/GetMedia', {'MediaId': cItem['media_id'], 'IncludeImages': True})
        if not isinstance(data, dict):
            return
        icon = self._image(data) or cItem.get('icon', '')
        count = 0
        for e in (data.get('Media') or []):
            if not e.get('Images') and icon:
                e = dict(e, Images=[{'ImageTypeCode': 'FRAME', 'Url': icon}])
            if e.get('MediaTypeCode') == 'EPISODE' and e.get('Title') and data.get('Title') and data['Title'] not in e['Title']:
                e = dict(e, Title='%s - %s' % (data['Title'], e['Title']))
            if self._addEntity(cItem, e):
                count += 1
        if not count:
            SetIPTVPlayerLastHostError(_("Nothing available here at the moment (only upcoming broadcasts)."))

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = cItem.get('page', 1)
        payload = {'FullTextSearch': searchPattern, 'IncludeImages': True, 'IncludeCategories': True, 'ExcludeChildren': True,
                   'IncludeCount': True, 'PageNumber': page, 'PageSize': self.PAGE_SIZE}
        self._listEntities(cItem, page, lambda pg: self._post('/Media/SearchMedia', dict(payload, PageNumber=pg)))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("PZPNPlus.getLinksForVideo [%s]" % cItem.get('media_id'))
        if cItem.get('paid'):
            SetIPTVPlayerLastHostError(_("This is paid content of PZPN+, it needs a purchase on the website."))
            return []
        mediaId = cItem.get('media_id') or self.cm.ph.getSearchGroups(cItem.get('url', ''), r'/(\d+)$')[0]
        if not mediaId:
            return []
        data = self._post('/Media/GetMediaPlayInfo', {'MediaId': int(mediaId), 'StreamType': 'MAIN'})
        if not isinstance(data, dict):
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        if data.get('MessageKey') or data.get('IsRestricted'):
            SetIPTVPlayerLastHostError(_("Content not available") + " (%s)" % (data.get('MessageKey') or 'restricted'))
            return []
        entries = data.get('Playlist') if isinstance(data.get('Playlist'), list) and data.get('Playlist') else [data]
        live = bool(cItem.get('live'))
        urlTab = []
        for idx, entry in enumerate(entries):
            url = entry.get('ContentUrl') or ''
            if not self.cm.isValidUrl(url):
                continue
            if entry.get('DrmType') or entry.get('Drm') or entry.get('LicenseUrl'):
                continue
            meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': TENANT + '/', 'Origin': TENANT, 'iptv_livestream': live}
            ctype = (entry.get('ContentType') or '').lower()
            if 'mpegurl' in ctype or '.m3u8' in url:
                meta['iptv_proto'] = 'm3u8'
            name = 'HLS' if meta.get('iptv_proto') else (url.split('?')[0].rsplit('.', 1)[-1].upper() or 'MP4')
            if len(entries) > 1:
                # several entries = the same match with different commentators
                name = self.cleanHtmlStr(entry.get('Title') or '') or '%s %d' % (name, idx + 1)
            urlTab.append({'name': name, 'url': self.up.decorateUrl(url, meta), 'need_resolve': 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if live:
            return urlTab
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('raw_title', '')))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        text = cItem.get('desc', '')
        data = self._post('/Media/GetMedia', {'MediaId': int(cItem['media_id']), 'IncludeImages': True}) if cItem.get('media_id') else None
        title = cItem.get('raw_title', '') or cItem.get('title', '')
        icon = cItem.get('icon', '')
        if isinstance(data, dict) and data.get('Id'):
            title = self.cleanHtmlStr(data.get('Title') or title)
            text = self.cleanHtmlStr(data.get('LongDescription') or data.get('Description') or '') or text
            icon = self._image(data) or icon
            if data.get('Year'):
                other['year'] = str(data['Year'])
            if data.get('Duration'):
                other['duration'] = self._duration(data['Duration'])
            cats = [self.cleanHtmlStr(c.get('CategoryName') or '') for c in (data.get('Categories') or []) if isinstance(c, dict)]
            if cats:
                other['categories'] = ', '.join([c for c in cats if c])
        if cItem.get('date'):
            other['released'] = cItem['date']
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("PZPNPlus.handleService name[%s] category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_media':
            self.listMedia(self.currItem)
        elif category == 'list_screen':
            self.listScreen(self.currItem)
        elif category == 'list_series':
            self.listSeries(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PZPNPlus(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('pzpnpluspl')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
