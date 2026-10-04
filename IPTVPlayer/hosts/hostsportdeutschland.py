# -*- coding: utf-8 -*-
# SPORTEUROPE.TV (formerly sportdeutschland.tv): live streams and replays of German/European club and
# association sport. Free content only - pay-per-view / pass content is left out of the lists and
# answered with a message when it is opened anyway (favourite, search).
# API: https://api.sporteurope.tv/api/web/public/... (lists), web-player/personal/assets/<id> (playback,
# works anonymously for free content), search.sporteurope.tv/api/v1 (search). Streams: Mux HLS.
# Last Modified: 03.10.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from datetime import datetime, timedelta
import calendar
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://sporteurope.tv/'


class SportDeutschland(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API = 'https://api.sporteurope.tv/api/'
    SEARCH_API = 'https://search.sporteurope.tv/api/v1/'
    IMG_CDN = 'https://img-cdn.do.sporteurope.tv/images/'
    PER_PAGE = 30
    # stable identity of a row: enough to open it again from the favourites
    FAV_FIELDS = ('name', 'category', 'type', 'asset_id', 'asset_type', 'profile_id', 'tag_id', 'url', 'title', 's_title', 'icon',
                  'desc', 'txt', 'start', 'duration', 'station', 'sport')

    def __init__(self):
        printDBG("SportDeutschland.__init__")
        CBaseHostClass.__init__(self, {'history': 'SportDeutschland', 'cookie': 'sportdeutschland.cookie'})
        self.MAIN_URL = 'https://sporteurope.tv/'
        self.DEFAULT_ICON_URL = 'https://sporteurope.tv/web-app-manifest-512x512.png'
        self.USER_AGENT = self.cm.getDefaultUserAgent('chrome')
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'application/json',
                            'Origin': 'https://sporteurope.tv', 'Referer': 'https://sporteurope.tv/'}
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.watchedHelper = IPTVWatchedHelper('sportdeutschland')
        self.wfInitFolderCache()

    ###################################################
    # watched flag: only replays, never live / upcoming streams
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            if cItem.get('type') == 'video' and cItem.get('asset_type') == 'VIDEO' and cItem.get('asset_id'):
                return 'video:%s' % cItem['asset_id']
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('asset_id') or cItem.get('profile_id') or cItem.get('tag_id'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def _json(self, url, extraHeader=None, ignoreCodes=False):
        header = dict(self.HTTP_HEADER)
        if extraHeader:
            header.update(extraHeader)
        params = {'header': header}
        if ignoreCodes:
            # the player API answers paid / geo-blocked content with 403 + JSON error
            params['ignore_http_code_ranges'] = [(400, 499)]
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG('SportDeutschland._json: no JSON from %s' % url)
        return None

    def _img(self, imageId, size='640x360'):
        # CDN path = images/<first uuid group split into single chars>/<other groups>/<size>.jpg
        try:
            if not imageId:
                return ''
            if imageId.startswith('http'):
                return imageId
            parts = imageId.split('-')
            if len(parts) != 5:
                return ''
            return self.IMG_CDN + '/'.join(list(parts[0])) + '/' + '/'.join(parts[1:]) + '/' + size + '.jpg'
        except Exception:
            return ''

    @staticmethod
    def _utc2local(isoDate):
        try:
            t = calendar.timegm(time.strptime(str(isoDate)[:19], '%Y-%m-%dT%H:%M:%S'))
            return datetime.fromtimestamp(t)
        except Exception:
            return None

    @staticmethod
    def _fmtDuration(secs):
        try:
            secs = int(secs or 0)
            if secs <= 0:
                return ''
            return '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)
        except Exception:
            return ''

    @staticmethod
    def _isFree(asset):
        return not (asset.get('monetizations') or asset.get('product_names') or asset.get('price_in_cents'))

    def _addAsset(self, cItem, asset):
        try:
            if not isinstance(asset, dict) or not asset.get('id') or not self._isFree(asset):
                return False
            name = self.cleanHtmlStr(asset.get('name') or '')
            if not name:
                return False
            aType = asset.get('type') or 'VIDEO'
            live = bool(asset.get('currently_live'))
            start = self._utc2local(asset.get('content_start_date') or '')
            profile = asset.get('profile') or {}
            station = self.cleanHtmlStr(profile.get('name') or '')
            sport = self.cleanHtmlStr(((profile.get('sport_type') or {}).get('name')) or '')
            duration = self._fmtDuration(asset.get('duration_in_seconds') or asset.get('video_duration'))
            upcoming = aType == 'LIVESTREAM' and not live and start is not None and start > datetime.now()

            descParts = []
            if live:
                descParts.append(_('On Air'))
            elif upcoming:
                descParts.append(_('Live stream starts %s') % start.strftime('%d.%m.%Y %H:%M'))
            elif start:
                descParts.append(start.strftime('%d.%m.%Y %H:%M'))
            if duration:
                descParts.append(duration)
            if station:
                descParts.append(station)
            sub = self.cleanHtmlStr(asset.get('subtitle') or '')
            if sub:
                descParts.append(sub)
            text = self.cleanHtmlStr(asset.get('description') or '')
            desc = ' | '.join(descParts)
            if text:
                desc += '[/br]' + text

            title = name
            if aType == 'VIDEO' and not live:
                title = normalizeMediathekTitle(name, date=start.strftime('%Y-%m-%d') if start else '')
            elif upcoming:
                title = '%s %s' % (start.strftime('%H:%M'), name)

            params = {'name': 'category', 'category': 'play', 'good_for_fav': True, 'title': title, 's_title': name,
                      'asset_id': asset['id'], 'asset_type': aType, 'live': live,
                      'icon': self._img(asset.get('image_id') or asset.get('image_url')),
                      'desc': desc, 'txt': text, 'start': start.strftime('%d.%m.%Y %H:%M') if start else '', 'duration': duration,
                      'station': station, 'sport': sport,
                      'url': self.MAIN_URL + '%s/%s' % (profile.get('slug') or '-', asset.get('slug') or asset['id'])}
            if upcoming:
                # not started yet: no stream to play, the row opens the INFO view with the start time
                self.addArticle(params)
            else:
                self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    def _addProfile(self, cItem, prof):
        try:
            if not isinstance(prof, dict) or not prof.get('id'):
                return False
            name = self.cleanHtmlStr(prof.get('name') or '')
            if not name:
                return False
            imageId = prof.get('image_id') or prof.get('image_url')
            if 'category' in prof:
                # search mixes tags (sport types / hashtags) into the profile list
                title = name if prof.get('category') in ('SportType', 'SPORT_TYPE') else '#' + name
                self.addDir({'name': 'category', 'category': 'tag_menu', 'title': title, 'tag_id': prof['id'], 'icon': self._img(imageId), 'good_for_fav': True})
                return True
            sport = self.cleanHtmlStr(((prof.get('sport_type') or {}).get('name')) or '')
            desc = ' | '.join([x for x in (sport, _('On Air') if prof.get('currently_live') else '') if x])
            text = self.cleanHtmlStr(prof.get('description') or '')
            if text:
                desc = (desc + '[/br]' if desc else '') + text
            self.addDir({'name': 'category', 'category': 'profile_menu', 'title': name, 'profile_id': prof['id'],
                         'icon': self._img(imageId, '300x300'), 'desc': desc, 'good_for_fav': True})
            return True
        except Exception:
            printExc()
        return False

    def _listPaged(self, cItem, path, addFunc):
        # the list API pages with page/per_page and meta.last_page; paid assets are dropped, so a page that
        # only held paid content is skipped forward instead of showing an empty list
        page = int(cItem.get('page', 1) or 1)
        tpl = self.API + path + ('&' if '?' in path else '?') + 'page={page}&per_page=%d' % self.PER_PAGE
        lastPage = page
        added = 0
        tries = 0
        while True:
            data = self._json(tpl.format(page=page))
            if not isinstance(data, dict):
                return
            for it in (data.get('data') or []):
                if addFunc(cItem, it):
                    added += 1
            try:
                lastPage = int((data.get('meta') or {}).get('last_page') or page)
            except Exception:
                lastPage = page
            tries += 1
            if added or page >= lastPage or tries >= 4:
                break
            page += 1
        if added:
            addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, tpl)

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        tab = [{'category': 'list_days', 'title': _('Live streams by day')},
               {'category': 'list_tags', 'title': _('Popular sports'), 'path': 'web/public/header-tags'},
               {'category': 'list_tags', 'title': _('All Sports'), 'path': 'frontend/public/menu/sport-types'},
               {'category': 'list_profiles', 'title': _('Top leagues and clubs'), 'path': 'web/public/top-profiles'}] + self.searchItems()
        self.listsTab(tab, cItem)

    def listDays(self, cItem):
        today = datetime.now()
        for i in range(8):
            d = today + timedelta(days=i)
            title = _('Today') if i == 0 else (_('Tomorrow') if i == 1 else d.strftime('%d.%m.%Y'))
            params = dict(cItem)
            params.update({'category': 'list_assets', 'title': title, 'path': 'web/public/next-livestreams/%s' % d.strftime('%Y-%m-%d')})
            self.addDir(params)

    def listTags(self, cItem):
        # header-tags is one plain list, the full sport-type menu is paged by 20 (~7 pages): show it in one list
        items = []
        url = self.API + cItem['path']
        for _i in range(10):
            data = self._json(url)
            if isinstance(data, dict):
                items.extend(data.get('data') or [])
                url = (data.get('links') or {}).get('next') or ''
            else:
                items.extend(data if isinstance(data, list) else [])
                url = ''
            if not url or not self.cm.isValidUrl(url):
                break
        for tag in items:
            if not isinstance(tag, dict) or not tag.get('id'):
                continue
            title = self.cleanHtmlStr(tag.get('name') or '')
            if title:
                self.addDir({'name': 'category', 'category': 'tag_menu', 'title': title, 'tag_id': tag['id'],
                             'icon': self._img(tag.get('image_id')), 'good_for_fav': True})

    def _subMenu(self, cItem, tab):
        for cat, title, path in tab:
            params = dict(cItem)
            params.update({'category': cat, 'title': title, 'path': path, 'good_for_fav': False})
            params.pop('page', None)
            self.addDir(params)

    def listTagMenu(self, cItem):
        tid = cItem['tag_id']
        self._subMenu(cItem, (('list_assets', _('Videos'), 'web/public/tags/%s/assets' % tid),
                              ('list_assets', _('Upcoming'), 'web/public/tags/%s/next-livestreams' % tid),
                              ('list_profiles', _('Leagues, clubs and events'), 'web/public/tags/%s/profiles' % tid)))

    def listProfileMenu(self, cItem):
        pid = cItem['profile_id']
        self._subMenu(cItem, (('list_assets', _('Videos'), 'web/public/profiles/%s/assets' % pid),
                              ('list_assets', _('Upcoming'), 'web/public/profiles/%s/next-livestreams' % pid),
                              ('list_profiles', _('Clubs and athletes'), 'web/public/profiles/%s/clubs-athletes' % pid)))

    def listAssets(self, cItem):
        self._listPaged(cItem, cItem['path'], self._addAsset)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No free videos or live streams here at the moment.'))

    def listProfiles(self, cItem):
        if cItem['path'].endswith('top-profiles'):
            data = self._json(self.API + cItem['path'])
            for it in ((data or {}).get('data') or []):
                self._addProfile(cItem, it)
        else:
            self._listPaged(cItem, cItem['path'], self._addProfile)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    def listSearch(self, cItem, searchPattern, searchType):
        page = int(cItem.get('page', 1) or 1)
        q = urllib_quote_plus(searchPattern)
        if page == 1:
            data = self._json(self.SEARCH_API + 'search/profiles?q=%s' % q)
            profs = (data or {}).get('data') or []
            if profs:
                params = stripPagerKeys(dict(cItem))
                params.update({'category': 'search_profiles', 'title': _('Leagues, clubs and events') + ' (%d)' % len(profs), 'good_for_fav': False})
                self.addDir(params)
        tpl = self.SEARCH_API + 'search/assets?q=%s&page={page}&per_page=%d' % (q, self.PER_PAGE)
        data = self._json(tpl.format(page=page))
        if not isinstance(data, dict):
            return
        assets = data.get('assets') or []
        for it in assets:
            self._addAsset(cItem, it)
        try:
            total = int(data.get('assets_count') or 0)
        except Exception:
            total = 0
        # the search API serves at most 900 hits
        lastPage = (min(total, 900) + self.PER_PAGE - 1) // self.PER_PAGE
        addPagingItems(self, cItem, page, bool(assets) and page < lastPage, lastPage, tpl)

    def listSearchProfiles(self, cItem):
        data = self._json(self.SEARCH_API + 'search/profiles?q=%s' % urllib_quote_plus(cItem.get('search_pattern', '')))
        for it in ((data or {}).get('data') or []):
            self._addProfile(cItem, it)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("SportDeutschland.getLinksForVideo [%s]" % cItem.get('asset_id', ''))
        aid = cItem.get('asset_id', '')
        if not aid:
            return []
        data = self._json(self.API + 'web-player/personal/assets/%s' % aid, {'x-version': '2'}, ignoreCodes=True)
        if not isinstance(data, dict):
            SetIPTVPlayerLastHostError(_('Content not available'))
            return []
        err = data.get('error') or ''
        if err:
            if 'PURCHASED' in err or 'PAYWALL' in err:
                SetIPTVPlayerLastHostError(_('This video is Premium-only content.'))
            elif 'REGION' in err or 'GEO' in err:
                SetIPTVPlayerLastHostError(_('This content is not available in your region.'))
            elif 'LOGIN' in err:
                SetIPTVPlayerLastHostError(_('This content needs a login - not supported.'))
            else:
                SetIPTVPlayerLastHostError(_('Content not available') + ' (%s)' % err)
            return []

        sources = []
        for tr in (data.get('tracks') or []):
            lang = tr.get('audio_language') or tr.get('label') or ''
            for src in (tr.get('sources') or []):
                if src.get('hls'):
                    sources.append((lang, src))
        if not sources:
            start = self._utc2local(data.get('content_start_date') or '')
            if start and start > datetime.now():
                SetIPTVPlayerLastHostError(_('Live stream starts %s') % start.strftime('%d.%m.%Y %H:%M'))
            else:
                SetIPTVPlayerLastHostError(_('No stream available'))
            return []

        live = bool(data.get('currently_live')) or any(src.get('type') == 'LIVESTREAM' for lang, src in sources)
        multiLang = len(set(lang for lang, src in sources)) > 1
        meta = {'iptv_proto': 'm3u8', 'iptv_livestream': live, 'User-Agent': self.USER_AGENT,
                'Referer': 'https://sporteurope.tv/', 'Origin': 'https://sporteurope.tv'}
        urlTab = []
        for lang, src in sources:
            name = self.cleanHtmlStr(src.get('title') or ('Live' if live else 'HLS'))
            if multiLang and lang:
                name += ' [%s]' % lang
            url = strwithmeta(src['hls'], meta)
            if len(sources) == 1 and not live:
                # single replay: offer the qualities, best first
                variants = getDirectM3U8Playlist(url, checkExt=False, checkContent=True)
                variants.sort(key=lambda x: int(x.get('bitrate', 0) or 0), reverse=True)
                for v in variants:
                    v['need_resolve'] = 0
                    urlTab.append(v)
                if variants:
                    continue
            urlTab.append({'name': name, 'url': url, 'need_resolve': 0})
        if not live:
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('txt', '')))
        return urlTab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        title = cItem.get('s_title') or cItem.get('title', '')
        text = cItem.get('txt') or cItem.get('desc', '')
        other = {}
        if cItem.get('station'):
            other['station'] = cItem['station']
        if cItem.get('sport'):
            other['category'] = cItem['sport']
        if cItem.get('start'):
            other['broadcast'] = cItem['start']
        if cItem.get('duration'):
            other['duration'] = cItem['duration']
        if cItem.get('live'):
            other['status'] = _('Live')
        elif cItem.get('asset_type') == 'LIVESTREAM':
            other['status'] = _('Upcoming')
        images = [{'title': '', 'url': cItem['icon']}] if cItem.get('icon') else []
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(text), 'images': images, 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('SportDeutschland.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("SportDeutschland.handleService: name[%s] category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_days':
            self.listDays(self.currItem)
        elif category == 'list_tags':
            self.listTags(self.currItem)
        elif category == 'tag_menu':
            self.listTagMenu(self.currItem)
        elif category == 'profile_menu':
            self.listProfileMenu(self.currItem)
        elif category == 'list_assets':
            self.listAssets(self.currItem)
        elif category == 'list_profiles':
            self.listProfiles(self.currItem)
        elif category == 'search_profiles':
            self.listSearchProfiles(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page', 'search_pattern': searchPattern})
            self.listSearch(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SportDeutschland(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('sportdeutschland')

    def withArticleContent(self, cItem):
        return cItem.get('type') in ('video', 'article')
