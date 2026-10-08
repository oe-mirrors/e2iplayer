# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# SRG SSR (SRF / RTS / RSI / RTR)
# Rewritten for the il.srgssr.ch integrationlayer 2.0 JSON API
# 07.10.2026 - INFO (media details, moviemeta for films), First/Next
# paging, own url per media (download marker), watched flag for podcast episodes,
# new portal logos, default user agent.
# 08.10.2026 - default icon from the own tile (upload.wikimedia.org answered with HTTP 429).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
import re
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
###################################################

config.plugins.iptvplayer.playrtsiw_hls = ConfigYesNo(default=True)


def GetConfigList():
    return [getConfigListEntry(_("Use HLS streams (adaptive):"), config.plugins.iptvplayer.playrtsiw_hls)]


def gettytul():
    return 'https://www.srgssr.ch/'


class PlayRTSIW(GenericFolderWatchedScraperMixin, CBaseHostClass):

    IL = 'https://il.srgssr.ch/integrationlayer/2.0/'
    TOKEN_URL = 'https://tp.srgssr.ch/akahd/token?acl='

    BU = [
        ('srf', 'SRF', 'https://www.srf.ch/play/v3/images/appIcons/srf/play-srf_384x384.png'),
        ('rts', 'RTS', 'https://www.rts.ch/play/v3/images/appIcons/rts/play-rts_384x384.png'),
        ('rsi', 'RSI', 'https://www.rsi.ch/play/v3/images/appIcons/rsi/play-rsi_384x384.png'),
        ('rtr', 'RTR', 'https://www.rtr.ch/play/v3/images/appIcons/rtr/play-rtr_384x384.png'),
    ]
    # show names the portals use for their feature films (show "Film", title "<<Vortex>> - French drama")
    FILM_SHOWS = ('film', 'films', 'spielfilm', 'cinema')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'PlayRTSIW', 'cookie': 'srgssr.cookie'})
        # Wikimedia only serves its standard thumbnail widths (1200px answers 400)
        # the own tile: upload.wikimedia.org answers hotlinked thumbnails with HTTP 429
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/playrtsiw135.png')
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'application/json'}

        self.watchedHelper = IPTVWatchedHelper('srgssr')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            itemType = cItem.get('type', '')
            if itemType in ('video', 'audio'):
                urn = str(cItem.get('urn', '') or '').strip()
                if urn:
                    return 'media:%s' % urn
                # podcast episodes (RSS) have no urn, only their file
                direct = str(cItem.get('direct_url', '') or '').strip()
                return 'media:url:%s' % direct if direct else ''
            if itemType in ('more', 'marker'):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('category', '') in ('list_portal', 'list_radio', 'list_portals',
                                             'search', 'search_next_page', 'search_history'):
                return ''
            # "next=N" only pages the list (page 2 keys like page 1)
            url = self.wfNormalizeUrlKey(re.sub(r'([?&])next=[^&]*&?', r'\1', cItem.get('url', '') or '').rstrip('?&'))
            return 'folder:%s' % url if url else ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, params=None, post_data=None):
        if params is None:
            params = {}
        params['header'] = dict(self.HTTP_HEADER)
        return self.cm.getPage(url, params, post_data)

    def _json(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    def _icon(self, url):
        url = url or ''
        if url.lower().endswith('.svg'):
            # channel logos are SVG (not drawable on the box, and /scale/ answers 404): let the image service render a PNG
            return 'https://il.srgssr.ch/images/?imageUrl=%s&format=png&width=480' % urllib_quote(url, safe='')
        if url and '/scale/' not in url and url.lower().rsplit('.', 1)[-1] not in ('png', 'jpg', 'jpeg', 'webp'):
            url += '/scale/width/480'
        return url

    def _fmtDur(self, ms):
        try:
            s = int(ms) // 1000
            h, s = divmod(s, 3600)
            m, s = divmod(s, 60)
            return '%d:%02d:%02d' % (h, m, s) if h else '%d:%02d' % (m, s)
        except Exception:
            return ''

    ###################################################
    def _addMedia(self, cItem, media):
        try:
            if not isinstance(media, dict):
                return
            urn = media.get('urn') or ''
            if not urn:
                return
            title = self.cleanHtmlStr(media.get('title') or '')
            show = self.cleanHtmlStr((media.get('show') or {}).get('title') or '')
            isAudio = str(media.get('mediaType') or '').upper() == 'AUDIO'
            isFilm = show.lower() in self.FILM_SHOWS and not isAudio
            # a film with media naming on: no "Film - " show prefix (and no broadcast date below)
            filmName = isFilm and IsMediaNamingNormalized()
            if show and show.lower() not in title.lower() and not filmName:
                title = '%s - %s' % (show, title)
            descTab = []
            dur = self._fmtDur(media.get('duration'))
            date = (media.get('date') or '')[:10]
            meta = ', '.join([x for x in (dur, date) if x])
            if meta:
                descTab.append(meta)
            for key in ('lead', 'description'):
                if media.get(key):
                    descTab.append(self.cleanHtmlStr(media[key]))
                    break
            block = str(media.get('blockReason') or '').upper()
            if block:
                title = '%s [%s]' % (title, 'GEO' if 'GEOBLOCK' in block else block)
                descTab.insert(0, _('This content is not available in your region.') if 'GEOBLOCK' in block else block)
            params = stripPagerKeys(dict(cItem), ('base_url', 'meta_type', 'meta_title', 'live', 'direct_url'))
            # the media's own Play page as the row url: the download marker is keyed on it
            # (the watched key stays the urn)
            parts = urn.split(':')
            bu = parts[1] if len(parts) > 2 else (cItem.get('bu') or 'srf')
            ownUrl = 'https://www.%s.ch/play/%s/-/%s/-?urn=%s' % (bu, 'radio' if isAudio else 'tv', 'audio' if isAudio else 'video', urn)
            params.update({'good_for_fav': True, 'title': title or urn, 'urn': urn, 'url': ownUrl,
                           'icon': self._icon(media.get('imageUrl')), 'desc': '[/br]'.join(descTab)})
            if str(media.get('type') or '').upper() in ('LIVESTREAM', 'SCHEDULED_LIVESTREAM'):
                params['live'] = True
            else:
                if not filmName:
                    params['title'] = normalizeMediathekTitle(params['title'], date=media.get('date') or '', sxeHint=title)
                if isFilm:
                    # "<<Vortex>> - French drama" (French quotation marks) -> "Vortex"
                    m = re.search(u'\u00ab([^\u00bb]+)\u00bb', media.get('title') or '')
                    params.update({'meta_type': 'movie', 'meta_title': self.cleanHtmlStr(m.group(1) if m else (media.get('title') or ''))})
            if isAudio:
                self.addAudio(params)
            else:
                self.addVideo(params)
        except Exception:
            printExc()

    def _mediaList(self, cItem, key='mediaList'):
        data = self._json(cItem['url'])
        if not data:
            return
        for m in (data.get(key) or data.get('mediaList') or []):
            self._addMedia(cItem, m)
        self._addPaging(cItem, data.get('next') or '')

    def _addPaging(self, cItem, nextUrl, baseUrl=''):
        # the integration layer pages with an opaque "next" link (page index or offset): First page + Next page
        page = int(cItem.get('page') or 1)
        baseUrl = cItem.get('base_url') or baseUrl or cItem.get('url', '')
        pagerItem = dict(cItem, url=baseUrl, base_url=baseUrl)
        addPagingItems(self, pagerItem, page, bool(nextUrl), nextParams={'url': nextUrl} if nextUrl else None)

    ###################################################
    def listPortals(self, cItem):
        for bu, title, icon in self.BU:
            params = dict(cItem)
            params.update({'category': 'list_portal', 'title': title, 'bu': bu, 'icon': icon, 'desc': title})
            self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listPortal(self, cItem):
        bu = cItem['bu']
        entries = [
            ('list_media', _('Live'), self.IL + '%s/mediaList/video/livestreams' % bu),
            ('list_media', _('Latest'), self.IL + '%s/mediaList/video/latestEpisodes?pageSize=40' % bu),
            ('list_media', _('Most popular'), self.IL + '%s/mediaList/video/trending?pageSize=40&onlyEpisodes=true' % bu),
            ('list_topics', _('Categories'), self.IL + '%s/topicList/tv' % bu),
            ('list_az', _('Shows A-Z'), self.IL + '%s/showList/tv/alphabetical?pageSize=100' % bu),
            ('list_radio', _('Radio'), ''),
        ]
        for cat, title, url in entries:
            params = dict(cItem)
            params.update({'category': cat, 'title': title, 'url': url})
            self.addDir(params)

    def listRadio(self, cItem):
        bu = cItem['bu']
        entries = [
            ('list_media', _('Live'), self.IL + '%s/mediaList/audio/livestreams' % bu),
            ('list_media', _('Most popular'), self.IL + '%s/mediaList/audio/trending?pageSize=40' % bu),
            ('list_radio_channels', _('Channels'), self.IL + '%s/channelList/radio' % bu),
            ('list_az', _('Shows A-Z'), self.IL + '%s/showList/radio/alphabetical?pageSize=100' % bu),
        ]
        for cat, title, url in entries:
            params = dict(cItem)
            params.update({'category': cat, 'title': title, 'url': url, 'radio': True})
            self.addDir(params)

    def listRadioChannels(self, cItem):
        data = self._json(cItem['url'])
        if not data:
            return
        bu = cItem['bu']
        for ch in (data.get('channelList') or []):
            cid = ch.get('id') or ''
            if not cid:
                continue
            params = dict(cItem)
            params.pop('page', None)
            params.update({'category': 'list_media', 'title': self.cleanHtmlStr(ch.get('title') or ''),
                           'icon': self._icon(ch.get('imageUrl')),
                           'url': self.IL + '%s/mediaList/audio/latestByChannel/%s?pageSize=40' % (bu, cid)})
            self.addDir(params)

    def listPodcast(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            return
        for item in re.findall(r'<item>(.*?)</item>', data, re.S):
            enclosure = re.search(r'<enclosure\b[^>]*>', item)
            m = re.search(r'\b(?:url|href)="([^"]+)"', enclosure.group(0)) if enclosure else None
            if not m:
                continue
            url = m.group(1).replace('&amp;', '&')
            title = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', item, re.S)
            dur = re.search(r'<itunes:duration>([^<]+)</itunes:duration>', item)
            pub = re.search(r'<pubDate>([^<]+)</pubDate>', item)
            desc = re.search(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', item, re.S)
            params = stripPagerKeys(dict(cItem), ('base_url',))
            params.update({'good_for_fav': True, 'title': self.cleanHtmlStr(title.group(1)) if title else cItem.get('title', ''),
                           'direct_url': url, 'url': url, 'urn': '',
                           'desc': '[/br]'.join([x for x in (
                               ', '.join([y for y in ((dur.group(1) if dur else ''), (pub.group(1)[:16] if pub else '')) if y]),
                               self.cleanHtmlStr(desc.group(1)) if desc else '') if x])})
            self.addAudio(params)

    def listTopics(self, cItem):
        data = self._json(cItem['url'])
        if not data:
            return
        bu = cItem['bu']
        for t in (data.get('topicList') or []):
            tid = t.get('id') or ''
            if not tid:
                continue
            params = stripPagerKeys(dict(cItem), ('base_url',))
            params.update({'category': 'list_media', 'title': self.cleanHtmlStr(t.get('title') or ''),
                           'icon': self._icon(t.get('imageUrl')), 'desc': self.cleanHtmlStr(t.get('lead') or ''),
                           'url': self.IL + '%s/mediaList/video/latestByTopic/%s?pageSize=40' % (bu, tid)})
            self.addDir(params)

    def listAZ(self, cItem):
        data = self._json(cItem['url'])
        if not data:
            return
        bu = cItem['bu']
        radio = bool(cItem.get('radio'))
        for show in (data.get('showList') or []):
            sid = show.get('id') or ''
            if not sid:
                continue
            desc = []
            if show.get('numberOfEpisodes'):
                desc.append(_('%s episodes') % show['numberOfEpisodes'])
            if show.get('lead') or show.get('description'):
                desc.append(self.cleanHtmlStr(show.get('lead') or show.get('description')))
            params = stripPagerKeys(dict(cItem), ('base_url',))
            params.update({'title': self.cleanHtmlStr(show.get('title') or ''),
                           'icon': self._icon(show.get('imageUrl')), 'desc': '[/br]'.join(desc)})
            if radio:
                feed = show.get('podcastFeedHdUrl') or show.get('podcastFeedSdUrl') or ''
                if not feed:
                    continue
                params.update({'category': 'list_podcast', 'url': feed})
            else:
                params.update({'category': 'list_media', 'url': self.IL + '%s/mediaList/video/latest/byShow/%s?pageSize=40' % (bu, sid)})
            self.addDir(params)
        self._addPaging(cItem, data.get('next') or '')

    def listSearchResult(self, cItem, searchPattern, searchType):
        bu = (searchType or cItem.get('bu') or 'srf').lower()
        q = urllib_quote(searchPattern)
        if not cItem.get('url'):
            data = self._json(self.IL + '%s/searchResultShowList?q=%s' % (bu, q))
            if data:
                for show in (data.get('searchResultShowList') or data.get('showList') or []):
                    sid = show.get('id') or ''
                    if not sid:
                        continue
                    params = dict(cItem)
                    params.update({'category': 'list_media', 'bu': bu, 'title': '[%s] %s' % (_('Show'), self.cleanHtmlStr(show.get('title') or '')),
                                   'icon': self._icon(show.get('imageUrl')), 'desc': self.cleanHtmlStr(show.get('lead') or ''),
                                   'url': self.IL + '%s/mediaList/video/latest/byShow/%s?pageSize=40' % (bu, sid)})
                    self.addDir(params)
            url = self.IL + '%s/searchResultMediaList?q=%s&pageSize=40' % (bu, q)
        else:
            url = cItem['url']  # a pager row
        data = self._json(url)
        if not data:
            return
        for m in (data.get('searchResultMediaList') or data.get('mediaList') or []):
            self._addMedia(dict(cItem, bu=bu), m)
        self._addPaging(dict(cItem, bu=bu), data.get('next') or '', url)

    ###################################################
    def _akamaiToken(self, url):
        try:
            # ACL = first two path segments + /* (matches the proven old-host scheme)
            segs = url.split('://', 1)[-1].split('?', 1)[0].split('/')
            acl = '/%s/%s/*' % (segs[1], segs[2]) if len(segs) > 3 else '/*'
            data = self._json(self.TOKEN_URL + urllib_quote(acl, ''))
            authparams = ((data or {}).get('token') or {}).get('authparams') or ''
            if authparams:
                return url + ('&' if '?' in url else '?') + authparams
        except Exception:
            printExc()
        return url

    def getLinksForVideo(self, cItem):
        printDBG("PlayRTSIW.getLinksForVideo [%s]" % cItem.get('urn', ''))
        if cItem.get('direct_url'):
            return applySidecarToLinks([{'need_resolve': 0, 'name': _('Audio'), 'url': cItem['direct_url']}], buildSidecarFromItem(cItem, IsSidecarEnabled()))
        urn = cItem.get('urn', '')
        if not urn:
            return []
        data = self._json(self.IL + 'mediaComposition/byUrn/%s.json?onlyChapters=true&vector=portalplay' % urn)
        if not data:
            return []
        try:
            chapter = None
            for ch in (data.get('chapterList') or []):
                if ch.get('urn') == data.get('chapterUrn'):
                    chapter = ch
                    break
            if chapter is None and data.get('chapterList'):
                chapter = data['chapterList'][0]
            if not chapter:
                return []
        except Exception:
            printExc()
            return []

        blockReason = str(chapter.get('blockReason') or '')
        synopsis = self.cleanHtmlStr(chapter.get('description') or chapter.get('lead') or '')
        resources = chapter.get('resourceList') or []
        if not resources:
            if blockReason:
                printDBG("PlayRTSIW: blocked [%s]" % blockReason)
                if 'GEOBLOCK' in blockReason.upper():
                    SetIPTVPlayerLastHostError(_('This content is only available in Switzerland.'))
                else:
                    SetIPTVPlayerLastHostError(_('Content not available') + ' [%s]' % blockReason)
            return []

        subTracks = []
        for sub in (chapter.get('subtitleList') or []):
            surl = sub.get('url') or ''
            # the same track also comes as TTML (hbbtv.xml): the player reads VTT/SRT only
            if surl and (sub.get('format') or 'VTT').upper() in ('VTT', 'SRT'):
                subTracks.append({'title': sub.get('locale') or sub.get('language') or '', 'url': surl,
                                  'lang': sub.get('locale') or 'de', 'format': (sub.get('format') or '').lower() or 'vtt'})

        isAudio = ':audio:' in urn
        preferHls = config.plugins.iptvplayer.playrtsiw_hls.value
        live = bool(cItem.get('live'))
        hd, sd = [], []
        for res in resources:
            rurl = res.get('url') or ''
            if not rurl:
                continue
            proto = (res.get('protocol') or '').upper()
            isHls = 'HLS' in proto or '.m3u8' in rurl.lower()
            # for radio keep every protocol (MP3 + HLS); for video honour the config
            if not isAudio:
                if preferHls and not isHls:
                    continue
                if not preferHls and isHls:
                    continue
            if (res.get('tokenType') or 'NONE').upper() == 'AKAMAI':
                rurl = self._akamaiToken(rurl)
            name = ('%s %s' % (proto, res.get('quality') or '')).strip()
            meta = {'iptv_livestream': live}
            if subTracks:
                meta['external_sub_tracks'] = subTracks
            if isHls:
                meta['iptv_proto'] = 'm3u8'
            entry = {'need_resolve': 0, 'name': name, 'url': self.up.decorateUrl(rurl, meta)}
            # radio: plain HTTPS/MP3 first (most reliable), then HLS
            if isAudio and not isHls:
                hd.append(entry)
            elif str(res.get('quality') or '').upper() == 'HD':
                hd.append(entry)
            else:
                sd.append(entry)

        urlTab = hd + sd
        if not urlTab:
            for res in resources:
                if res.get('url'):
                    urlTab.append({'need_resolve': 0, 'name': ('%s %s' % (res.get('protocol') or '', res.get('quality') or '')).strip(),
                                   'url': self.up.decorateUrl(res['url'], {'iptv_livestream': live})})
        if not live:
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))
        return urlTab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('PlayRTSIW.getArticleContent [%s]' % cItem.get('urn', ''))
        text, icon, info = cItem.get('desc', ''), cItem.get('icon', ''), {}
        urn = cItem.get('urn', '')
        chapter, show = {}, {}
        if urn:
            data = self._json(self.IL + 'mediaComposition/byUrn/%s.json?onlyChapters=true&vector=portalplay' % urn) or {}
            show = data.get('show') or {}
            for ch in (data.get('chapterList') or []):
                if ch.get('urn') == urn or not chapter:
                    chapter = ch
            if chapter:
                parts = [self.cleanHtmlStr(chapter.get(k) or '') for k in ('lead', 'description')]
                parts = [x for i, x in enumerate(parts) if x and x not in parts[:i]]
                text = '[/br]'.join(parts) or text
                if len(text) < 20:
                    # live streams and short news clips: the show's text
                    showText = self.cleanHtmlStr(show.get('lead') or show.get('description') or '')
                    text = '[/br]'.join([x for x in (text, showText) if x])
                dur = self._fmtDur(chapter.get('duration'))
                if dur:
                    info['duration'] = dur
                if (chapter.get('date') or '')[:10]:
                    info['broadcast'] = chapter['date'][:10]
                if (chapter.get('validTo') or '')[:10]:
                    info['remaining'] = _('available until %s') % chapter['validTo'][:10]
                channel = (data.get('channel') or {}).get('title') or ''
                if channel:
                    info['station'] = self.cleanHtmlStr(channel)
                if show.get('title'):
                    info['category'] = self.cleanHtmlStr(show['title'])
        meta = {}
        if cItem.get('meta_type') and cItem.get('meta_title'):
            try:
                meta = getMeta(cItem['meta_type'], cItem['meta_title'])
            except Exception:
                printExc()
        # the site's texts first, the service adds ratings, cast, year and the poster
        for key, value in (meta.get('info') or {}).items():
            info.setdefault(key, value)
        text = text or meta.get('plot', '')
        icon = meta.get('poster') or icon
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('PlayRTSIW.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("PlayRTSIW.handleService: name[%s] category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if name is None:
            self.listPortals({'name': 'category'})
        elif category == 'list_portal':
            self.listPortal(self.currItem)
        elif category == 'list_media':
            self._mediaList(self.currItem)
        elif category == 'list_topics':
            self.listTopics(self.currItem)
        elif category == 'list_az':
            self.listAZ(self.currItem)
        elif category == 'list_radio':
            self.listRadio(self.currItem)
        elif category == 'list_radio_channels':
            self.listRadioChannels(self.currItem)
        elif category == 'list_podcast':
            self.listPodcast(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PlayRTSIW(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('srgssr')

    def withArticleContent(self, cItem):
        return cItem.get('type') in ('video', 'audio')

    def getSearchTypes(self):
        return [('SRF', 'srf'), ('RTS', 'rts'), ('RSI', 'rsi'), ('RTR', 'rtr')]
