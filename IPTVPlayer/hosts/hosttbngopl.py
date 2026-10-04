# -*- coding: utf-8 -*-
# TBN GO (tbngo.pl) - free platform of the Christian channel TBN Polska
# Live: /get-live-hls -> HLS of the TBN Polska channel (no account needed).
# VOD: /api/v2/videos (programmes), /api/v2/categories (category -> programmes), /api/v2/vod/<id> (episodes).
#   Playback needs a free TBN GO account: POST /login {email, password} -> token,
#   POST /api/v2/vod/<id>/playback {episodeNumber} with "Authorization: Bearer <token>" -> playbackUrl + subtitles.
# Last Modified: 03.10.2026 - new host: live, categories, programmes/episodes, login, watched flag, naming, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Components.config import config, getConfigListEntry
###################################################

config.plugins.iptvplayer.tbngopl_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.tbngopl_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("E-mail (free TBN GO account):"), config.plugins.iptvplayer.tbngopl_login),
            getConfigListEntry(_("Password:"), config.plugins.iptvplayer.tbngopl_password)]


def gettytul():
    return 'https://tbngo.pl/'


class TBNGoPL(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'vod_id', 'episode', 'show_title', 'live')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tbngopl', 'cookie': 'tbngopl.cookie'})
        self.MAIN_URL = 'https://tbngo.pl/'
        self.DEFAULT_ICON_URL = ''  # the site has no logo image (only favicon.ico)
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Origin': 'https://tbngo.pl', 'Referer': 'https://tbngo.pl/'})
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True}
        self.token = ''
        self.tokenFor = None
        self.loginError = ''
        self.videosCache = None
        self.watchedHelper = IPTVWatchedHelper('tbngopl')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live') or not cItem.get('vod_id'):
                return ''
            if cItem.get('type') == 'video':
                return 'video:%s:%s' % (cItem['vod_id'], cItem.get('episode', 1))
            if cItem.get('category') == 'list_episodes':
                return 'folder:%s' % cItem['vod_id']
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, path, post=None, token=''):
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER, Accept='application/json')
        # 4xx answers carry the reason as JSON ({"code": ..., "message": ...})
        params['ignore_http_code_ranges'] = [(400, 499)]
        if token:
            params['header']['Authorization'] = 'Bearer %s' % token
        if post is not None:
            params['header']['Content-Type'] = 'application/json'
            params['raw_post_data'] = True
            post = json_dumps(post)
        sts, data = self.getPage(self.getFullUrl(path), params, post)
        if not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG('TBNGoPL._json no JSON from %s' % path)
        return None

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video' or cItem.get('category') == 'list_episodes':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _icon(self, item, wide=True):
        fname = item.get('filename') if wide else (item.get('filenameMobile') or item.get('filename'))
        if fname:
            return self.getFullUrl('/uploads/' + fname)
        return item.get('thumbnail') or ''

    @staticmethod
    def _duration(secs):
        try:
            secs = int(secs or 0)
        except Exception:
            return ''
        if secs <= 0:
            return ''
        return '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)

    def _getVideos(self):
        if self.videosCache is None:
            data = self._json('/api/v2/videos')
            self.videosCache = data if isinstance(data, list) else []
        return self.videosCache

    ###################################################
    # login
    ###################################################
    def _getToken(self):
        login = ensure_str(config.plugins.iptvplayer.tbngopl_login.value).strip()
        password = ensure_str(config.plugins.iptvplayer.tbngopl_password.value)
        if not login or not password:
            self.loginError = _("TBN GO needs a free account to play programmes.\nRegister on https://tbngo.pl/ and enter the e-mail and password in the host settings.")
            return ''
        if self.token and self.tokenFor == (login, password):
            return self.token
        self.token = ''
        self.tokenFor = (login, password)
        data = self._json('/login', {'email': login, 'password': password})
        if isinstance(data, dict) and data.get('token'):
            self.token = ensure_str(data['token'])
            self.loginError = ''
        else:
            msg = data.get('message') if isinstance(data, dict) else ''
            self.loginError = _("Login failed.") + ('\n%s' % ensure_str(msg) if msg else '')
        return self.token

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        params = dict(cItem)
        params.update({'title': 'TBN Polska - ' + _('Live'), 'live': True, 'url': self.getFullUrl('/get-live-hls'),
                       'desc': _('Live stream of the %s channel') % 'TBN Polska', 'good_for_fav': True})
        self.addVideo(params)
        params = dict(cItem)
        params.update({'category': 'list_programs', 'title': _('All programmes')})
        self.addDir(params)
        data = self._json('/api/v2/categories')
        for cat in data if isinstance(data, list) else []:
            if not isinstance(cat, dict):
                continue
            for name in cat.keys():
                params = dict(cItem)
                title = ensure_str(name)
                params.update({'category': 'list_programs', 'title': title[:1].upper() + title[1:], 'cat': title})
                self.addDir(params)

    def listPrograms(self, cItem):
        catName = cItem.get('cat', '')
        for item in self._getVideos():
            try:
                if catName and catName not in [ensure_str(c) for c in (item.get('category') or [])]:
                    continue
                vid = item.get('_id')
                title = self.cleanHtmlStr(item.get('title') or '')
                if not vid or not title:
                    continue
                desc = self.cleanHtmlStr(item.get('info') or '')
                params = dict(cItem)
                params.pop('cat', None)
                params.update({'category': 'list_episodes', 'title': title, 'vod_id': vid, 'url': self.getFullUrl('/vod/%s' % vid),
                               'icon': self._icon(item), 'desc': desc, 'show_title': title, 'good_for_fav': True})
                self.addDir(params)
            except Exception:
                printExc()

    def _episodeTitle(self, show, num, epTitle):
        epTitle = self.cleanHtmlStr(epTitle or '')
        if IsMediaNamingNormalized():
            # the episode title goes into the description (listEpisodes)
            return '%s - %s' % (show, formatSxxExx(1, num))
        return epTitle or '%s - %s %d' % (show, _('Episode'), num)

    def listEpisodes(self, cItem):
        vid = cItem.get('vod_id', '')
        data = self._json('/api/v2/vod/%s' % vid)
        if not isinstance(data, dict):
            return
        show = self.cleanHtmlStr(data.get('title') or cItem.get('show_title', ''))
        info = self.cleanHtmlStr(data.get('info') or '')
        icon = self._icon(data) or cItem.get('icon', '')
        episodes = [{'episodeNumber': 1, 'title': data.get('firstEpisodeTitle') or '', 'duration': data.get('duration'),
                     'availableDate': data.get('availableDate'), 'thumbnail': ''}]
        episodes.extend([e for e in (data.get('episodes') or []) if isinstance(e, dict)])
        for ep in episodes:
            try:
                num = int(ep.get('episodeNumber') or 1)
            except Exception:
                continue
            if ep.get('availableDate'):
                # premiere scheduled - the API refuses playback until then
                continue
            dur = self._duration(ep.get('duration'))
            epTitle = self.cleanHtmlStr(ep.get('title') or '')
            if epTitle.lower() == show.lower():
                epTitle = ''
            params = {'name': 'category', 'type': 'video', 'vod_id': vid, 'episode': num, 'show_title': show,
                      'title': self._episodeTitle(show, num, ep.get('title')),
                      'url': self.getFullUrl('/vod/%s?episode=%d' % (vid, num)),
                      'icon': ep.get('thumbnail') or icon,
                      'desc': (epTitle + '[/br]' if epTitle else '') + ((_('Duration: %s') % dur) + '[/br]' if dur else '') + info,
                      'good_for_fav': True}
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _liveLinks(self):
        data = self._json('/get-live-hls')
        hls = data.get('hls') if isinstance(data, dict) else ''
        if not hls:
            SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))
            return []
        url = strwithmeta(hls, {'iptv_livestream': True, 'Referer': self.getMainUrl(), 'Origin': 'https://tbngo.pl'})
        urlTab = getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        for item in urlTab:
            item['need_resolve'] = 0
        return urlTab or [{'name': 'HLS', 'url': url, 'need_resolve': 0}]

    def getLinksForVideo(self, cItem):
        printDBG("TBNGoPL.getLinksForVideo [%s]" % cItem.get('url', ''))
        if cItem.get('live'):
            return self._liveLinks()
        vid = cItem.get('vod_id') or self.cm.ph.getSearchGroups(cItem.get('url', ''), r'/vod/([0-9a-f]+)')[0]
        if not vid:
            return []
        token = self._getToken()
        if not token:
            SetIPTVPlayerLastHostError(self.loginError or _("Login failed."))
            return []
        num = int(cItem.get('episode', 1) or 1)
        data = self._json('/api/v2/vod/%s/playback' % vid, {} if num == 1 else {'episodeNumber': num}, token)
        if isinstance(data, dict) and data.get('code') in ('AUTHENTICATION_REQUIRED', 'INVALID_TOKEN', 'TOKEN_EXPIRED'):
            # token expired - log in once more
            self.token = ''
            token = self._getToken()
            data = self._json('/api/v2/vod/%s/playback' % vid, {} if num == 1 else {'episodeNumber': num}, token) if token else None
        playUrl = data.get('playbackUrl') if isinstance(data, dict) else ''
        if not playUrl:
            msg = data.get('message') if isinstance(data, dict) else ''
            SetIPTVPlayerLastHostError(ensure_str(msg) if msg else _("No stream available"))
            return []
        subTracks = []
        for sub in data.get('subtitles') or []:
            if not isinstance(sub, dict):
                continue
            surl = sub.get('url') or sub.get('src') or sub.get('file') or ''
            if not self.cm.isValidUrl(surl):
                surl = self.getFullUrl(surl) if surl else ''
            if not surl:
                continue
            lang = ensure_str(sub.get('lang') or sub.get('language') or sub.get('srclang') or 'pl')
            fmt = 'srt' if surl.split('?')[0].lower().endswith('.srt') else 'vtt'
            subTracks.append({'title': ensure_str(sub.get('label') or lang), 'url': surl, 'lang': lang, 'format': fmt})
        meta = {'Referer': self.getMainUrl(), 'Origin': 'https://tbngo.pl'}
        if subTracks:
            meta['external_sub_tracks'] = subTracks
        playUrl = strwithmeta(ensure_str(playUrl), meta)
        urlTab = []
        if '.m3u8' in playUrl or 'm3u8' in playUrl.split('?')[0]:
            urlTab = getDirectM3U8Playlist(playUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
            for item in urlTab:
                item['need_resolve'] = 0
        if not urlTab:
            urlTab = [{'name': 'TBN GO', 'url': playUrl, 'need_resolve': 0}]
        # the programme info is the last part of the description (after episode title / duration)
        synopsis = cItem.get('desc', '').rsplit('[/br]', 1)[-1]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        title = self.cleanHtmlStr(cItem.get('show_title') or cItem.get('title', ''))
        icon = cItem.get('icon', '')
        text = cItem.get('desc', '')
        other = {}
        vid = cItem.get('vod_id', '')
        if vid:
            data = self._json('/api/v2/vod/%s' % vid)
            if isinstance(data, dict):
                text = self.cleanHtmlStr(data.get('info') or '') or text
                icon = self._icon(data) or icon
                cats = [ensure_str(c) for c in (data.get('category') or [])]
                if cats:
                    other['genre'] = ', '.join(cats)
                age = (data.get('contentRating') or {}).get('age')
                if age:
                    other['age_limit'] = ensure_str(age)
                if cItem.get('type') == 'video':
                    other['episodes'] = str(len(data.get('episodes') or []) + 1)
                    title = self.cleanHtmlStr(cItem.get('title', ''))
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("TBNGoPL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_programs':
            self.listPrograms(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TBNGoPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tbngopl')

    def withArticleContent(self, cItem):
        return (cItem.get('type') == 'video' and not cItem.get('live')) or cItem.get('category') == 'list_episodes'
