# -*- coding: utf-8 -*-
# SRG SSR (SRF / RTS / RSI / RTR)
# Rewritten for the il.srgssr.ch integrationlayer 2.0 JSON API
# Last Modified: 28.08.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
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


class PlayRTSIW(CBaseHostClass):

    IL = 'https://il.srgssr.ch/integrationlayer/2.0/'
    TOKEN_URL = 'https://tp.srgssr.ch/akahd/token?acl='

    BU = [
        ('srf', 'SRF', 'https://www.srf.ch/play/static/img/srg/srf/playsrf_logo.png'),
        ('rts', 'RTS', 'https://www.rts.ch/play/static/img/srg/rts/playrts_logo.png'),
        ('rsi', 'RSI', 'https://www.rsi.ch/play/static/img/srg/rsi/playrsi_logo.png'),
        ('rtr', 'RTR', 'https://www.rtr.ch/play/static/img/srg/rtr/playrtr_logo.png'),
    ]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'PlayRTSIW', 'cookie': 'srgssr.cookie'})
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/SRG_SSR_2011_logo.svg/1200px-SRG_SSR_2011_logo.svg.png'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36', 'Accept': 'application/json'}

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
            if show and show.lower() not in title.lower():
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
            params = dict(cItem)
            params.pop('page', None)
            params.update({'good_for_fav': True, 'title': title or urn, 'urn': urn,
                           'icon': self._icon(media.get('imageUrl')), 'desc': '[/br]'.join(descTab)})
            if str(media.get('type') or '').upper() in ('LIVESTREAM', 'SCHEDULED_LIVESTREAM'):
                params['live'] = True
            if str(media.get('mediaType') or '').upper() == 'AUDIO':
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
        nextUrl = data.get('next') or ''
        if nextUrl:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextUrl, 'good_for_fav': False})
            self.addDir(params)

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
            params = dict(cItem)
            params.pop('page', None)
            params.update({'good_for_fav': True, 'title': self.cleanHtmlStr(title.group(1)) if title else cItem.get('title', ''),
                           'direct_url': url, 'urn': '',
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
            params = dict(cItem)
            params.pop('page', None)
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
            params = dict(cItem)
            params.pop('page', None)
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
        nextUrl = data.get('next') or ''
        if nextUrl:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextUrl, 'good_for_fav': False})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        bu = (searchType or 'srf').lower()
        q = urllib_quote(searchPattern)
        page = cItem.get('page', 0)
        if page == 0:
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
            url = cItem['url']
        data = self._json(url)
        if not data:
            return
        for m in (data.get('searchResultMediaList') or data.get('mediaList') or []):
            self._addMedia(dict(cItem, bu=bu), m)
        nextUrl = data.get('next') or ''
        if nextUrl:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextUrl, 'page': page + 1})
            self.addDir(params)

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
            return [{'need_resolve': 0, 'name': _('Audio'), 'url': cItem['direct_url']}]
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
            if surl:
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
        return urlTab

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


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PlayRTSIW(), True, [])

    def getSearchTypes(self):
        return [('SRF', 'srf'), ('RTS', 'rts'), ('RSI', 'rsi'), ('RTR', 'rtr')]
