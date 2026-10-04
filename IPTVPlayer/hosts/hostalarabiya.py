# -*- coding: utf-8 -*-
# Al Arabiya (alarabiya.net) - the live channels (Al Arabiya, Al Hadath, Al Arabiya English, Business,
#   Programmes, FM), the programme archive and the video sections of the site, plus the video search.
# The site sits behind Cloudflare that only lets Chrome's TLS fingerprint through (and challenges every
#   url with a query string, so its "?pageNo=N" pager can not be used): pages and the site's search API
#   (openapi.alarabiya.net, which also lists a programme or a section page by page) via curl-impersonate.
#   The live HLS (live.alarabiya.net) and the VOD files (vid.alarabiya.net, MP4 + HLS) are open to every
#   client that sends a User-Agent.
# Last Modified: 03.10.2026 - new host: live, programmes, video sections, search + history, watched flag,
#   downloaded marker, name normalisation "Programme - Title (YYYY-MM-DD)", sidecar, INFO, favourites
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://www.alarabiya.net/'


class AlArabiya(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API_URL = 'https://openapi.alarabiya.net/v1/search/ar/%d/%d/%s?sortColumn=creationDate&contentTypes=video'
    PER_PAGE = 20
    API_MAX = 10000  # the API caps totalNoOfItems
    # data-channel of the live page -> name
    LIVE_NAMES = {'video-live': 'العربية', 'video-live-alhadath': 'الحدث', 'video-live-en': 'Al Arabiya English',
                  'video-live-aswaq': 'العربية Business', 'video-live-programs': 'العربية برامج', 'video-live-fm': 'العربية FM'}
    LIVE_FALLBACK = [('video-live', 'https://live.alarabiya.net/alarabiapublish/alarabiya.smil/playlist.m3u8'),
                     ('video-live-alhadath', 'https://live.alarabiya.net/alarabiapublish/alhadath.smil/playlist.m3u8'),
                     ('video-live-en', 'https://live.alarabiya.net/alarabiapublish/english/playlist_dvr.m3u8'),
                     ('video-live-aswaq', 'https://live.alarabiya.net/alarabiapublish/aswaaq.smil/playlist.m3u8'),
                     ('video-live-programs', 'https://live.alarabiya.net/alarabiapublish/aaprograms.smil/playlist.m3u8'),
                     ('video-live-fm', 'https://fm.alarabiya.net/fm/myStream/playlist.m3u8')]
    # stable identity of a row
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'program_title', 'icon', 'date', 'duration', 'height',
                  'mp4', 'hls', 'live', 'section', 'page')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'alarabiya', 'cookie': 'alarabiya.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = 'https://www.alarabiya.net/.resources/aa-fe-templating/webresources/dist/assets/gfx/logo/logo@3x.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        # Cloudflare blocks every non-Chrome TLS fingerprint: curl-impersonate, no cookie needed
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True,
                              'cookiefile': self.COOKIE_FILE, 'impersonate': True}
        self.cachePrograms = None
        self.watchedHelper = IPTVWatchedHelper('alarabiya')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            if cItem.get('type', '') == 'video':
                url = self._pathOf(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if cItem.get('category', '') == 'list_items' and cItem.get('program_title') and cItem.get('section'):
                # "Next page" rows carry the same section, so page 2+ keys like page 1
                return 'program:%s' % cItem['section']
        except Exception:
            printExc()
        return ''

    @staticmethod
    def _pathOf(url):
        return re.sub(r'^https?://[^/]+', '', str(url or '').strip())

    ###################################################
    # http
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        sts, data = self.cm.getPageCFProtection(url, addParams, post_data)
        if not sts:
            meta = getattr(data, 'meta', None) or {}
            if meta.get('status_code') in (403, 503):
                SetIPTVPlayerLastHostError(_('%s refused the request (Cloudflare check, HTTP %s). This host needs curl-impersonate on the receiver.') % ('Al Arabiya', meta.get('status_code')))
        return sts, data

    def fullUrl(self, path):
        # the site's paths carry raw Arabic words
        path = ensure_str(path or '').strip()
        if not path:
            return ''
        if path.startswith('//'):
            path = 'https:' + path
        if not path.startswith('http'):
            path = self.MAIN_URL + path.lstrip('/')
        return urllib_quote(path, safe=":/?=&%#-_.~+,;*")

    def apiList(self, query, page, section=''):
        url = self.API_URL % (page, self.PER_PAGE, urllib_quote(ensure_str(query), safe='*'))
        if section:
            url += '&sections=' + urllib_quote(section, safe='/')
        header = dict(self.HEADER)
        header.update({'Accept': 'application/json', 'Referer': self.MAIN_URL, 'Origin': self.MAIN_URL.rstrip('/')})
        params = dict(self.defaultParams)
        params['header'] = header
        sts, data = self.getPage(url, params)
        if not sts:
            return -1, []
        try:
            data = json_loads(data)
            return min(int(data.get('totalNoOfItems') or 0), self.API_MAX), data.get('items') or []
        except Exception:
            printExc()
        return -1, []

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        self.addDir({'name': 'category', 'category': 'list_live', 'title': _('Live')})
        self.addDir({'name': 'category', 'category': 'list_program_groups', 'title': _('Programmes'), 'url': self.MAIN_URL + 'programs'})
        self.addDir({'name': 'category', 'category': 'list_video_sections', 'title': _('Videos'), 'url': self.MAIN_URL + 'alarabiya-videos'})
        self.listsTab(self.searchItems(), {'name': 'category'})

    def listLive(self, cItem):
        channels = []
        sts, data = self.getPage(self.MAIN_URL + 'live-stream')
        if sts:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'class="select-channel"', '</div>', False)[1]
            for span in re.findall(r'<span\s[^>]*data-src-url="[^"]+"[^>]*>', tmp):
                url = self.cm.ph.getSearchGroups(span, r'data-src-url="([^"]+)"')[0]
                channel = self.cm.ph.getSearchGroups(span, r'data-channel="([^"]+)"')[0]
                icon = self.cm.ph.getSearchGroups(span, r'data-poster="([^"]+)"')[0]
                channels.append((channel, url, icon))
        if not channels:
            channels = [(channel, url, '') for channel, url in self.LIVE_FALLBACK]
        for channel, url, icon in channels:
            title = self.LIVE_NAMES.get(channel) or channel.replace('video-live-', '').replace('-', ' ').title()
            desc = _('Radio') if channel.endswith('-fm') else _('Live')
            self.addVideo({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'live': True, 'desc': desc})

    def _sectionLabel(self, html):
        return self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(html, '>', '</div>', False)[1])

    def _fillPrograms(self, url):
        if self.cachePrograms:
            return self.cachePrograms
        groups = []
        sts, data = self.getPage(url)
        if not sts:
            return groups
        tabLabels = dict(re.findall(r'id="tab-panel-(\d+)"[^>]*>\s*<span class="tabs-tab__content">\s*<span class="tabs-tab__text-label">([^<]+)<', data))
        for m in re.finditer(r'<ul class="video-list[^"]*">(.*?)</ul>', data, re.S):
            pre = data[:m.start()]
            si = pre.rfind('data-aa-component="sectionLabel"')
            label = self._sectionLabel(pre[si:]) if si > -1 else ''
            pi = pre.rfind('aria-labelledby="tab-panel-')
            if pi > si:
                tab = self.cleanHtmlStr(tabLabels.get(self.cm.ph.getSearchGroups(pre[pi:], r'tab-panel-(\d+)')[0], ''))
                label = '%s - %s' % (label, tab) if label and tab else (tab or label)
            programs = []
            seen = set()
            for item in re.findall(r'<a class="list-item-link"(.*?)</a>', m.group(1), re.S):
                href = self.cm.ph.getSearchGroups(item, r'href="(/programs/[^"/?#]+)"')[0]
                if not href or href in seen:
                    continue
                seen.add(href)
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="program-title">(.*?)</span>', ignoreCase=True)[0]) or \
                    self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
                icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
                if title:
                    programs.append({'title': title, 'url': self.fullUrl(href), 'section': '/ar' + href, 'icon': icon})
            if programs:
                groups.append({'title': label or _('Programmes'), 'programs': programs})
        self.cachePrograms = groups
        return groups

    def listProgramGroups(self, cItem):
        for idx, group in enumerate(self._fillPrograms(cItem['url'])):
            self.addDir({'name': 'category', 'category': 'list_programs', 'title': group['title'], 'url': cItem['url'], 'group_idx': idx,
                         'desc': _('%d programmes') % len(group['programs'])})

    def listPrograms(self, cItem):
        groups = self._fillPrograms(cItem['url'])
        idx = cItem.get('group_idx', -1)
        if idx < 0 or idx >= len(groups):
            return
        for program in groups[idx]['programs']:
            self.addDir({'name': 'category', 'category': 'list_items', 'good_for_fav': True, 'title': program['title'], 'program_title': program['title'],
                         'url': program['url'], 'section': program['section'], 'icon': program['icon'], 'page': 1})

    def listVideoSections(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        seen = set()
        for m in re.finditer(r'data-aa-component="sectionLabel"[^>]*>(.*?)</div>', data, re.S):
            href = self.cm.ph.getSearchGroups(m.group(1), r'href="(/[^"?#]+)"')[0].rstrip('/')
            title = self.cleanHtmlStr(m.group(1))
            if not href or not title or href in seen:
                continue
            seen.add(href)
            self.addDir({'name': 'category', 'category': 'list_items', 'good_for_fav': True, 'title': title, 'url': self.fullUrl(href),
                         'section': '/ar' + href, 'page': 1})

    @staticmethod
    def _stripProgram(title, program):
        # episode titles often repeat the programme name ("سؤال مباشر: ...")
        if program and title.startswith(program):
            rest = re.sub(r'^\s*[-|:–—]+\s*', '', title[len(program):]).strip()
            if rest:
                return rest
        return title

    def _videoTitle(self, title, program, date):
        if IsMediaNamingNormalized() and program:
            # some episode titles start with a separator themselves ("- ...") -> no "Show - - Title"
            rest = re.sub(r'^\s*[-|:–—]+\s*', '', self._stripProgram(title, program)).strip() or title
            title = '%s - %s' % (program, rest)
        return normalizeMediathekTitle(re.sub(r'\s+-\s+(?:-\s+)+', ' - ', title), date=date)

    @staticmethod
    def _fmtDuration(seconds):
        try:
            seconds = int(seconds)
        except Exception:
            return ''
        if seconds <= 0:
            return ''
        if seconds >= 3600:
            return '%d:%02d:%02d' % (seconds // 3600, (seconds // 60) % 60, seconds % 60)
        return '%d:%02d' % (seconds // 60, seconds % 60)

    def _addApiItem(self, cItem, item):
        video = item.get('video') or {}
        mp4 = ensure_str(video.get('url') or '')
        hls = ensure_str(video.get('urlHls') or '')
        path = item.get('canonicalPath') or ''
        if not (mp4 or hls) or not path:
            return False
        title = self.cleanHtmlStr(ensure_str(item.get('title') or ''))
        if not title:
            return False
        date = ensure_str(item.get('publishedDate') or '')[:10]
        duration = self._fmtDuration(video.get('duration'))
        icon = ''
        for img in (video.get('image') or {}).get('imageUrls') or []:
            if img.get('ratio') == '16x9':
                icon = ensure_str(img.get('url') or '')
        if not icon:
            images = item.get('images') or []
            icon = ensure_str((images[0] if images else {}).get('url') or (video.get('image') or {}).get('url') or '')
        text = ensure_str(item.get('subtitle') or '')
        if not text:
            text = ' '.join(ensure_str(b.get('text') or '') for b in (item.get('body') or []) if b.get('type') == 'text')
        text = self.cleanHtmlStr(text)
        if len(text) > 600:
            text = text[:600].rsplit(' ', 1)[0] + '...'
        program = cItem.get('program_title', '')
        params = {'good_for_fav': True, 'title': self._videoTitle(title, program, date), 'raw_title': title, 'program_title': program,
                  'url': self.fullUrl(path), 'icon': icon, 'date': date, 'duration': duration, 'mp4': mp4, 'hls': hls,
                  'height': min(video.get('width') or 0, video.get('height') or 0) or video.get('height') or 0,  # 1080x1920 (portrait) = 1080p
                  'desc': '%s[/br]%s' % (' | '.join([x for x in (date, duration) if x]), text) if text else ' | '.join([x for x in (date, duration) if x])}
        subs = []
        for sub in video.get('subtitles') or []:
            if isinstance(sub, dict) and sub.get('url'):
                surl = ensure_str(sub['url'])
                lang = ensure_str(sub.get('language') or sub.get('lang') or sub.get('srclang') or '')[:2]
                subs.append({'title': ensure_str(sub.get('label') or sub.get('title') or lang or 'Sub'), 'url': surl, 'lang': lang,
                             'format': 'srt' if surl.lower().endswith('.srt') else 'vtt'})
        if subs:
            params['subs'] = subs
        self.addVideo(params)
        return True

    def _addHtmlItems(self, cItem, data):
        # the first page of a section straight from the site (a few sections are not in the search index)
        cnt = 0
        seen = set()
        program = cItem.get('program_title', '')
        for m in re.finditer(r'<ul class="video-list[^"]*">(.*?)</ul>', data, re.S):
            for item in re.findall(r'<a class="list-item-link"(.*?)</a>', m.group(1), re.S):
                href = self.cm.ph.getSearchGroups(item, r'href="(/[^"]+/\d{4}/\d{2}/\d{2}/[^"]+)"')[0]
                if not href or href in seen:
                    continue
                seen.add(href)
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
                if not title:
                    continue
                date = '-'.join(self.cm.ph.getSearchGroups(href, r'/(\d{4})/(\d{2})/(\d{2})/', 3))
                icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
                self.addVideo({'good_for_fav': True, 'title': self._videoTitle(title, program, date), 'raw_title': title, 'program_title': program,
                               'url': self.fullUrl(href), 'icon': icon, 'date': date, 'desc': date})
                cnt += 1
        return cnt

    def listItems(self, cItem):
        page = max(1, int(cItem.get('page', 1) or 1))
        printDBG('AlArabiya.listItems |%s| page %s' % (cItem.get('section', ''), page))
        total, items = self.apiList('*', page - 1, cItem.get('section', ''))
        cnt = 0
        for item in items:
            if self._addApiItem(cItem, item):
                cnt += 1
        if page == 1 and total < self.PER_PAGE:
            # not (fully) in the search index: the site's own first page lists more
            sts, data = self.getPage(cItem['url'])
            if sts:
                tmp = list(self.currList)
                self.currList = []
                if self._addHtmlItems(cItem, data) > cnt:
                    return
                self.currList = tmp
        # API paging (the site's own "?pageNo=N" urls are Cloudflare-challenged): the folder url stays
        # the same for every page, so it serves as the (constant) page template for "Jump"
        lastPage = (total + self.PER_PAGE - 1) // self.PER_PAGE
        addPagingItems(self, dict(cItem, desc=''), page, bool(items) and page < lastPage, lastPage, cItem.get('url', '').replace('{', '').replace('}', ''))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('AlArabiya.listSearchResult [%s]' % searchPattern)
        page = max(1, int(cItem.get('page', 1) or 1))
        pattern = ensure_str(searchPattern).strip()
        if not pattern:
            return
        total, items = self.apiList(pattern, page - 1)
        if total == 0 and page == 1:
            # the index is Arabic: a Latin word mostly finds nothing - say so instead of an empty list
            SetIPTVPlayerLastHostError(_('No results found for: %s') % pattern)
        for item in items:
            self._addApiItem({}, item)
        lastPage = (total + self.PER_PAGE - 1) // self.PER_PAGE
        addPagingItems(self, dict(cItem, category='search_next_page', search_pattern=pattern, desc=''), page, bool(items) and page < lastPage, lastPage)

    ###################################################
    # video page
    ###################################################
    def _parseVideoPage(self, data):
        info = {'mp4': '', 'hls': '', 'desc': '', 'icon': '', 'date': '', 'duration': '', 'title': '', 'program': ''}
        player = self.cm.ph.getDataBeetwenMarkers(data, '<video-js', '</video-js>', False)[1]
        for src, typ in re.findall(r'<source\s+src="([^"]+)"\s+type="([^"]+)"', player):
            if 'mpegurl' in typ.lower() and not info['hls']:
                info['hls'] = src
            elif 'mp4' in typ.lower() and not info['mp4']:
                info['mp4'] = src
        for ld in re.findall(r'<script type="application/ld\+json">(.*?)</script>', data, re.S):
            if '"VideoObject"' not in ld:
                continue
            info['mp4'] = info['mp4'] or self.cm.ph.getSearchGroups(ld, r'"contentUrl"\s*:\s*"([^"]+)"')[0]
            info['date'] = self.cm.ph.getSearchGroups(ld, r'"uploadDate"\s*:\s*"(\d{4}-\d{2}-\d{2})')[0]
            info['duration'] = self._fmtDuration(self.cm.ph.getSearchGroups(ld, r'"duration"\s*:\s*"PT(\d+)S"')[0])
            info['icon'] = self.cm.ph.getSearchGroups(ld, r'"thumbnailUrl"\s*:\s*"([^"]+)"')[0]
            info['title'] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(ld, r'"name"\s*:\s*"([^"]+)"')[0])
            break
        info['desc'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="program-description">', '</div>', False)[1]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        info['title'] = info['title'] or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
        info['icon'] = info['icon'] or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return info

    def getLinksForVideo(self, cItem):
        printDBG('AlArabiya.getLinksForVideo [%s]' % cItem.get('url', ''))
        meta = {'User-Agent': self.HEADER['User-Agent']}
        if cItem.get('live'):
            return [{'name': cItem.get('title', 'Live'), 'url': strwithmeta(cItem['url'], dict(meta, iptv_proto='m3u8')), 'need_resolve': 0}]
        url = cItem.get('url', '')
        mp4, hls = cItem.get('mp4', ''), cItem.get('hls', '')
        desc = cItem.get('desc', '')
        desc = desc.split('[/br]', 1)[1] if '[/br]' in desc else ''
        if not (mp4 or hls) and self.cm.isValidUrl(url):
            # rows from the site's HTML (not the API) carry no stream address: read it from the page
            sts, data = self.getPage(url)
            if sts:
                info = self._parseVideoPage(data)
                mp4, hls, desc = info['mp4'] or mp4, info['hls'] or hls, info['desc']
        if not mp4 and not hls:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        if cItem.get('subs'):
            meta['external_sub_tracks'] = cItem['subs']
        urlTab = []
        if mp4:
            height = cItem.get('height') or 0
            urlTab.append({'name': 'MP4 %sp' % height if height else 'MP4', 'url': strwithmeta(mp4, meta), 'need_resolve': 0})
        if hls:
            urlTab.append({'name': 'HLS', 'url': strwithmeta(hls, dict(meta, iptv_proto='m3u8')), 'need_resolve': 0})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), desc))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('AlArabiya.getArticleContent [%s]' % cItem.get('url', ''))
        title = cItem.get('raw_title') or cItem.get('title', '')
        text = cItem.get('desc', '')
        text = re.sub(r'^.*?\[/br\]', '', text) if '[/br]' in text else text
        icon = cItem.get('icon', '')
        otherInfo = {}
        sts, data = self.getPage(cItem.get('url', ''))
        if cItem.get('type') == 'video':
            if cItem.get('program_title'):
                otherInfo['station'] = cItem['program_title']
            if sts:
                info = self._parseVideoPage(data)
                title = info['title'] or title
                text = info['desc'] or text
                icon = info['icon'] or icon
                cItem = dict(cItem, date=info['date'] or cItem.get('date', ''), duration=info['duration'] or cItem.get('duration', ''))
            if cItem.get('date'):
                otherInfo['released'] = cItem['date']
            if cItem.get('duration'):
                otherInfo['duration'] = cItem['duration']
        elif sts:
            # a programme: its description and header picture
            text = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="desc', '</p>', False)[1].split('>', 1)[-1]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0]) or text
            header = self.cm.ph.getDataBeetwenMarkers(data, 'class="tv-program-header', '</picture>', False)[1]
            icon = self.cm.ph.getSearchGroups(header, r'srcset="([^"\s]+)')[0] or icon
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon or self.DEFAULT_ICON_URL}], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS + ('subs',) if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('AlArabiya.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        printDBG('AlArabiya.handleService: name[%s], category[%s]' % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu(self.currItem)
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'list_program_groups':
            self.listProgramGroups(self.currItem)
        elif category == 'list_programs':
            self.listPrograms(self.currItem)
        elif category == 'list_video_sections':
            self.listVideoSections(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, AlArabiya(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('alarabiya')

    def withArticleContent(self, cItem):
        if cItem.get('live'):
            return False
        return cItem.get('type', '') == 'video' or (cItem.get('category') == 'list_items' and bool(cItem.get('program_title')))
