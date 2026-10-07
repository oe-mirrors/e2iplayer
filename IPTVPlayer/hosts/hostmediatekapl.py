# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# mediateka.pl - audio portal of the ZPR Media group (Radio ESKA, ESKA2, ESKA Rock, VOX, vibe fm, Radio Super Express)
# Radio: the brands of https://mediateka.pl/radio/ ("?stream_uid=ra-..."); front-api.grupazprmedia.pl
#   /radios/v1/radio_station_details/<uid>/ -> site_uid, /radios/v1/radio_stations/<site_uid>/ -> all streams of the
#   brand (regional + theme stations) with stream_ic (Icecast AAC) and stream_url (HLS).
# Podcasts: the podcast cards of /podcasty/; a podcast page carries its latest episodes as JSON
#   (<script id="ao-..." type="application/json">) with HLS audio (cache.stream.smcdn.pl).
# 03.10.2026 - new host: radio stations, podcasts, watched flag (podcast episodes), sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://mediateka.pl/'


class MediatekaPL(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API = 'https://front-api.grupazprmedia.pl'
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'desc', 'live', 'station_uid', 'stream_ic', 'stream_hls',
                  'podcast_url', 'ep_uid', 'site_uid')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'mediatekapl', 'cookie': 'mediatekapl.cookie'})
        self.MAIN_URL = 'https://mediateka.pl/'
        self.DEFAULT_ICON_URL = 'https://mediateka.pl/web-app-manifest-512x512.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True}
        self.watchedHelper = IPTVWatchedHelper('mediatekapl')
        self.wfInitFolderCache()

    ###################################################
    # watched flag (podcast episodes only, radio stations are live)
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            if cItem.get('type') == 'audio' and cItem.get('ep_uid'):
                return 'audio:%s' % cItem['ep_uid']
            if cItem.get('category') == 'list_episodes':
                uid = self.cm.ph.getSearchGroups(cItem.get('url', ''), r'-(ps-[\w-]+)\.html')[0]
                return 'folder:%s' % uid if uid else ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'audio' or cItem.get('category') in ('list_episodes', 'list_stations'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        for item in [{'category': 'list_brands', 'title': _('Radio stations')},
                     {'category': 'list_podcasts', 'title': _('Podcasts'), 'url': self.getFullUrl('/podcasty/')}]:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listBrands(self, cItem):
        sts, data = self.getPage(self.getFullUrl('/radio/'))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mediateka__dedicated_streams-streams'), ('<!--', '-->'), False)[1] or data
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, '<a href="?stream_uid=', '</a>'):
            uid = self.cm.ph.getSearchGroups(item, r'stream_uid=(ra-[\w-]+)')[0]
            if not uid or uid in seen:
                continue
            seen.add(uid)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'mediateka__stream-title'), ('</div', '>'), False)[1])
            icon = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src="([^"]+)"''')[0]
            params = dict(cItem)
            params.update({'category': 'list_stations', 'title': title or uid, 'station_uid': uid, 'icon': icon,
                           'url': self.getFullUrl('/radio/?stream_uid=%s' % uid), 'good_for_fav': True})
            self.addDir(params)

    def listStations(self, cItem):
        siteUid = cItem.get('site_uid', '')
        if not siteUid:
            details = self._json('%s/radios/v1/radio_station_details/%s/' % (self.API, cItem.get('station_uid', '')))
            siteUid = details.get('site_uid', '') if isinstance(details, dict) else ''
        if not siteUid:
            return
        data = self._json('%s/radios/v1/radio_stations/%s/' % (self.API, siteUid))
        brand = self.cleanHtmlStr(cItem.get('title', ''))
        stations = []
        byUrl = {}
        for st in data if isinstance(data, list) else []:
            try:
                if not isinstance(st, dict) or st.get('on_player') is False:
                    continue
                ic = st.get('stream_ic') or ''
                hls = st.get('stream_url') or ''
                if not ic and not hls:
                    continue
                name = self.cleanHtmlStr(st.get('name') or '')
                url = ic or hls
                if url in byUrl:
                    # some regional stations share one stream (e.g. Ostrow / Kalisz) - one row named after both
                    byUrl[url]['names'].append(name)
                    continue
                params = {'name': 'category', 'type': 'audio', 'live': True, 'good_for_fav': True, 'names': [name],
                          'url': url, 'stream_ic': ic, 'stream_hls': hls, 'station_uid': st.get('uid', ''),
                          'icon': st.get('cover') or cItem.get('icon', ''), 'desc': _('Radio station - live stream')}
                byUrl[url] = params
                stations.append(params)
            except Exception:
                printExc()
        for params in stations:
            names = params.pop('names')
            if len(names) > 3:
                # one stream for dozens of regions (Radio VOX) - short title, the full list in the description
                name = ' / '.join(names[:3]) + ' (+%d)' % (len(names) - 3)
                params['desc'] = params['desc'] + '[/br]' + ', '.join(names)
            else:
                name = ' / '.join(names)
            low = name.lower()
            params['title'] = name if (not brand or brand.lower() in low or low in brand.lower()) else '%s - %s' % (brand, name)
            self.addAudio(params)

    def listPodcasts(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        items = []
        seen = set()
        for card in data.split('podcast-card')[1:]:
            url = self.cm.ph.getSearchGroups(card, r'''href="((?:https://mediateka\.pl)?/podcast/[^"]+\.html)"''')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            if url in seen:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(card, ('<div', '>', 'podcast-title'), ('</div', '>'), False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'''alt="([^"]+)"''')[0])
            if not title:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(card, r'''<img[^>]+src="([^"]+)"''')[0]
            items.append((title, url, icon))
        items.sort(key=lambda x: x[0].lower())
        for title, url, icon in items:
            params = dict(cItem)
            params.update({'category': 'list_episodes', 'title': title, 'url': url, 'icon': icon, 'good_for_fav': True})
            self.addDir(params)

    def _episodes(self, data):
        for raw in re.findall(r'<script id="ao-[\w-]+" type="application/json">(.*?)</script>', data, re.S):
            try:
                eps = json_loads(raw)
                if isinstance(eps, list) and eps:
                    return eps
            except Exception:
                printExc()
        return []

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        eps = self._episodes(data)
        if not eps:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        podcast = self.cleanHtmlStr(cItem.get('title', ''))
        for ep in eps:
            if not isinstance(ep, dict) or not ep.get('uid'):
                continue
            title = self.cleanHtmlStr(ep.get('title') or ep.get('name') or '')
            if not title:
                continue
            raw = title
            # "TITLE | PODCAST NAME" -> "Podcast - TITLE" when the names are normalised
            if IsMediaNamingNormalized() and podcast:
                parts = [p.strip() for p in title.split('|')]
                if len(parts) > 1 and parts[-1].lower() == podcast.lower():
                    title = ' | '.join(parts[:-1])
                if podcast.lower() not in title.lower():
                    title = '%s - %s' % (podcast, title)
            dur = ''
            try:
                secs = int(ep.get('duration') or ep.get('length') or 0)
                if secs:
                    dur = '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)
            except Exception:
                pass
            desc = self.cleanHtmlStr(ep.get('description') or '')
            params = {'name': 'category', 'type': 'audio', 'title': title, 'raw_title': raw, 'ep_uid': ep['uid'],
                      'url': '%s#%s' % (cItem['url'], ep['uid']), 'podcast_url': cItem['url'],
                      'icon': ep.get('cover_url') or cItem.get('icon', ''),
                      'desc': ((_('Duration: %s') % dur) + '[/br]' if dur else '') + desc, 'good_for_fav': True}
            self.addAudio(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MediatekaPL.getLinksForVideo [%s]" % cItem.get('url', ''))
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.getMainUrl()}
        if cItem.get('live'):
            urlTab = []
            ic = cItem.get('stream_ic') or ''
            hls = cItem.get('stream_hls') or ''
            if not ic and not hls and cItem.get('station_uid'):
                st = self._json('%s/radios/v1/radio_station_details/%s/' % (self.API, cItem['station_uid']))
                if isinstance(st, dict):
                    ic = st.get('stream_ic') or ''
                    hls = st.get('stream_url') or ''
            if ic:
                urlTab.append({'name': 'AAC (Icecast)', 'url': strwithmeta(ic, dict(meta, iptv_livestream=True)), 'need_resolve': 0})
            if hls:
                urlTab.append({'name': 'HLS', 'url': strwithmeta(hls, dict(meta, iptv_livestream=True, iptv_proto='m3u8')), 'need_resolve': 0})
            if not urlTab:
                SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))
            return urlTab

        podcastUrl = cItem.get('podcast_url') or cItem.get('url', '').split('#')[0]
        epUid = cItem.get('ep_uid') or cItem.get('url', '').split('#')[-1]
        sts, data = self.getPage(podcastUrl)
        if not sts:
            return []
        episode = None
        for ep in self._episodes(data):
            if isinstance(ep, dict) and ep.get('uid') == epUid:
                episode = ep
                break
        if episode is None:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        urlTab = []
        seen = set()
        for src in (episode.get('sources') or []) + [{'src': episode.get('url') or '', 'type': ''}]:
            url = ensure_str(src.get('src') or '')
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            if 'mpegurl' in (src.get('type') or '').lower() or '.m3u8' in url:
                urlTab.append({'name': 'HLS', 'url': strwithmeta(url, dict(meta, iptv_proto='m3u8')), 'need_resolve': 0})
            else:
                urlTab.append({'name': 'MP4', 'url': strwithmeta(url, meta), 'need_resolve': 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        synopsis = self.cleanHtmlStr(episode.get('description') or '')
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        title = self.cleanHtmlStr(cItem.get('raw_title') or cItem.get('title', ''))
        icon = cItem.get('icon', '')
        desc = cItem.get('desc', '')
        text = desc.split('[/br]', 1)[1] if '[/br]' in desc else desc
        other = {}
        if cItem.get('category') == 'list_episodes':
            sts, data = self.getPage(cItem['url'])
            if sts:
                eps = self._episodes(data)
                if eps:
                    other['episodes'] = str(len(eps))
                    authors = self.cleanHtmlStr(eps[0].get('archiver_authors') or '')
                    if authors:
                        other['actors'] = authors
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+name="description"[^>]+content="([^"]*)"''')[0]) or text
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("MediatekaPL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_brands':
            self.listBrands(self.currItem)
        elif category == 'list_stations':
            self.listStations(self.currItem)
        elif category == 'list_podcasts':
            self.listPodcasts(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MediatekaPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('mediatekapl')

    def withArticleContent(self, cItem):
        return (cItem.get('type') == 'audio' and not cItem.get('live')) or cItem.get('category') == 'list_episodes'
