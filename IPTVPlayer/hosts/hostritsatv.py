# -*- coding: utf-8 -*-
# RitsaTV (ritsatv.ru) - genre-organized live TV channel directory (CinemaPress-based).
# Playback: the real player is the <iframe id="cinemapress-cdn"> (the page also
# has EPG / chat / social iframes). Its ?file= is one of ~6 recurring shapes:
#   - a direct stream (.m3u8/.mpd), possibly "[720p]url,..." or "url or url"
#   - a "https://cors-proxy/https://real..." wrapped stream
#   - /youtube/X.txt  -> JSON [{title,file}] list
#   - /youtube/X.html -> Playerjs page: document.write(unescape()) blob and/or
#     file:"..." / streams=[...] / a nested ?file= wrapper
#   - a VK / OK.ru / Dailymotion / RuTube embed -> handed to urlparser
#   - a youtube.com/embed live id
#   - another /youtube/Y.html wrapper (followed, up to 3 hops)
# A few channels build the player purely in obfuscated JS or a ${token}
# template (no static stream) and can't be resolved without a JS engine.
import json
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://ritsatv.ru/'


class RitsaTv(CBaseHostClass):

    # /genre-<CODE> pages, in the order the site's own player category menu
    # shows them (its categoryList JS array; RADIO/RELAX are extra genre pages
    # not in that array). English labels; the live code list is refreshed from
    # the site at runtime so new categories show up on their own.
    GENRE_LABELS = {
        'TV': 'Information', 'MUSIC': 'Music TV Channels', 'KINO': 'Film Channels',
        'SPORT': 'Sports', 'ABKHAZIA': 'Abkhazia TV', 'COGNITIVE': 'Cognitive',
        'REGIONS': 'Regional', 'ASIATV': 'Central Asia CIS', 'KIDSTV': "Children's",
        'WORLDTV': 'World TV Channels', 'POLSKATV': 'Polska Telewizja',
        'RADIO': 'Radio Stations', 'RELAX': 'Relax Music',
        'TURKEYTV': 'Türk TV Kanallari', 'CLIPS': 'Music Clips',
    }
    GENRE_ORDER = ('TV', 'MUSIC', 'KINO', 'SPORT', 'ABKHAZIA', 'COGNITIVE', 'REGIONS',
                   'ASIATV', 'KIDSTV', 'WORLDTV', 'POLSKATV', 'RADIO', 'RELAX',
                   'TURKEYTV', 'CLIPS')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'RitsaTv', 'cookie': 'RitsaTv.cookie'})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._genresCache = None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _getGenres(self):
        # the full category list only lives in the per-channel player JS
        # (categoryList = [{label, value:'genre-XXX'}]); the homepage nav only
        # links 8 of them. Scrape a channel page for the codes, union with the
        # known set (so we never show fewer), keep our English labels.
        if self._genresCache is not None:
            return self._genresCache
        codes = []
        try:
            sts, data = self.getPage(self.MAIN_URL)
            m = re.search(r'/movie-id\d+[a-z0-9\-]*', data) if sts else None
            if m:
                sts, page = self.getPage(self.MAIN_URL.rstrip('/') + m.group(0))
                if sts:
                    codes = re.findall(r"""value:\s*['"]genre-([A-Za-z0-9_-]+)['"]""", page)
        except Exception:
            printExc()
        allCodes = set(codes) | set(self.GENRE_LABELS)
        ordered = [c for c in self.GENRE_ORDER if c in allCodes]
        ordered += sorted(c for c in allCodes if c not in self.GENRE_ORDER)
        self._genresCache = [(c, self.GENRE_LABELS.get(c, c.replace('_', ' ').title())) for c in ordered]
        return self._genresCache

    def listMainMenu(self):
        menu = [{'name': 'category', 'category': 'list_channels', 'title': _(label), 'genre': code}
                for code, label in self._getGenres()]
        self.listsTab(menu, {'name': 'category'})

    def listChannels(self, cItem):
        printDBG("RitsaTv.listChannels [%s]" % cItem.get('genre', ''))
        sts, data = self.getPage(self.MAIN_URL + 'genre-' + cItem['genre'])
        if not sts:
            return
        # the genre page carries a schema.org JSON-LD block (a list of objects,
        # one of them an ItemList<Movie>) with a clean {name, image,
        # alternativeHeadline, sameAs} entry per channel - far more reliable
        # than scraping the Tailwind/owl-carousel card markup
        isRadio = cItem.get('genre', '') == 'RADIO'
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', data, re.DOTALL):
            try:
                parsed = json.loads(block)
            except Exception:
                continue
            candidates = parsed if isinstance(parsed, list) else [parsed]
            itemList = next((c for c in candidates if isinstance(c, dict) and c.get('@type') == 'ItemList'), None)
            if not itemList:
                continue
            for entry in itemList.get('itemListElement', []):
                item = entry.get('item', {}) if isinstance(entry, dict) else {}
                url = item.get('sameAs') or item.get('url', '')
                title = self.cleanHtmlStr(item.get('name', ''))
                if not url or not title:
                    continue
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'video', 'title': title,
                               'url': url, 'icon': item.get('image', ''),
                               'desc': self.cleanHtmlStr(item.get('alternativeHeadline', '') or item.get('description', ''))})
                if isRadio:
                    self.addAudio(params)
                else:
                    self.addVideo(params)
            return  # only one ItemList block per page

    @staticmethod
    def _urlUnquote(value):
        try:
            from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote
            return urllib_unquote(value)
        except Exception:
            return value

    @staticmethod
    def _unwrapProxy(url):
        # some channels wrap the real URL in a CORS proxy - "https://proxy-host/https://real..."
        m = re.search(r'^https?://[^/]+/(https?://.+)$', url.strip())
        return m.group(1) if m else url.strip()

    @staticmethod
    def _splitStreamString(raw):
        # a stream string is one plain URL, several "[720p]url" mirrors joined
        # by commas, and/or several fallback mirrors joined by " or " - flatten
        # it into a list of (label, url)
        out = []
        for part in re.split(r'\s+or\s+', raw):
            for chunk in part.split(','):
                chunk = chunk.strip()
                if not chunk:
                    continue
                m = re.match(r'^\[([^\]]{1,10})\]\s*(https?://\S+)$', chunk)
                if m:
                    label = m.group(1)
                    if label.rstrip('p').isdigit():
                        label = label.rstrip('p') + 'p'
                    out.append((label, m.group(2)))
                elif chunk.startswith('http'):
                    out.append(('', chunk))
        return out

    @staticmethod
    def _isDirectStream(ref):
        low = ref.lower()
        if re.search(r'\s+or\s+', ref) or re.search(r'\]\s*https?:', ref):
            return True
        if '.m3u8' in low or '.mpd' in low or '/proxy.php' in low:
            return True
        path = low.split('?', 1)[0]
        return path.endswith(('.mp4', '.ts'))

    # embed hosts urlparser can resolve (VK / OK.ru / Dailymotion / RuTube),
    # used by ritsatv for some channels instead of a direct stream
    EMBED_RE = re.compile(
        r'''(https?://(?:[a-z0-9-]+\.)*'''
        r'''(?:vk(?:video)?\.ru|vk\.com|ok\.ru|odnoklassniki\.ru|dailymotion\.com|rutube\.ru)'''
        r'''/[^\s"'<>]+)''', re.I)

    def _pickPlayerFrame(self, data):
        # the channel page has several <iframe>s (EPG, chat, social, ...);
        # the real player is the one with id="cinemapress-cdn". Fall back to
        # heuristics only if that id is absent.
        tags = re.findall(r'<iframe\b[^>]*>', data, re.I)
        cand = []
        for t in tags:
            src = self.cm.ph.getSearchGroups(t, r'''src=["']([^"']+)["']''')[0].replace('&amp;', '&').strip()
            if not src or src.endswith('/404.html'):
                continue
            if 'cinemapress-cdn' in t.lower():
                return src
            low = src.lower()
            if any(s in low for s in ('chatbro', '/chat', 'disqus', '/widget', 'livecomment',
                                      '/files/chat', '/social/', 'epg', 'program', 'tvguide')):
                continue
            cand.append(src)
        for f in cand:
            if re.search(r'[?&]file=|/player|/youtube/|\.m3u8|\.mpd|youtube\.com|youtu\.be', f, re.I):
                return f
        return cand[0] if cand else ''

    def _extractStreamStrings(self, payload):
        out = []
        # (1) plain [{"title": "...", "file": "..."}] JSON list
        try:
            parsed = json.loads(payload.strip())
            if isinstance(parsed, list):
                for entry in parsed:
                    if isinstance(entry, dict) and entry.get('file'):
                        out.append((entry.get('title', ''), entry['file']))
        except Exception:
            pass
        if out:
            return out
        # merge the raw page with any document.write(unescape('...')) payload
        text = payload
        esc = self.cm.ph.getSearchGroups(payload, r'''unescape\(\s*['"]([^'"]+)['"]''')[0]
        if esc:
            text = self._urlUnquote(esc) + '\n' + payload
        # (2) a Playerjs / "var vs = ({... file:"..." })" file: property -
        #     one URL, or a "[720p]url,..." / "url or url" mirror string
        for mm in re.finditer(r'''["']?file["']?\s*:\s*["']([^"']+)["']''', text, re.I):
            v = mm.group(1).strip()
            if v.startswith('http') or v.startswith('['):
                out.append(('', v))
        # (3) Playerjs streams=[...] string array (JSON, or scrape quoted URLs
        #     if it isn't clean JSON)
        for arr in re.findall(r'streams\s*=\s*(\[.*?\])\s*;', text, re.DOTALL):
            try:
                items = [s for s in json.loads(arr) if isinstance(s, str)]
            except Exception:
                items = re.findall(r'''["']([^"']+)["']''', arr)
            out.extend(('', s) for s in items if s.strip() and ('http' in s or s.startswith('[')))
        # (4) nested "...playerT.html?file=<stream>&poster=..." wrappers
        for mm in re.finditer(r'''[?&]file=([^&"'\s<>]+)''', text, re.I):
            v = self._unwrapProxy(self._urlUnquote(mm.group(1)).rstrip('?&'))
            if re.search(r'\.(?:m3u8|mpd|mp4|ts)(?:$|[?&])', v, re.I) or re.search(r'\s+or\s+', v):
                out.append(('', v))
        if out:
            return out
        # (5) last resort: any bare .m3u8 / .mpd URL on the page
        for mm in re.finditer(r'''(https?://[^\s"'<>\\]+?\.(?:m3u8|mpd)(?:\?[^\s"'<>\\]*)?)''', text, re.I):
            out.append(('', mm.group(1)))
        return out

    def _resolveEmbed(self, text):
        # VK / OK.ru / Dailymotion / RuTube embeds inside the wrapper page
        for embed in dict.fromkeys(self.EMBED_RE.findall(text)):
            try:
                if self.up.checkHostSupport(embed):
                    links = self.up.getVideoLinkExt(embed)
                    if links:
                        return links
            except Exception:
                printExc()
        return []

    @staticmethod
    def _nestedWrappers(text):
        # some /youtube/X.html pages are just a chooser that loads another
        # /youtube/Y.html (or a /PLAYER/*.html) - collect those to follow
        out = []
        for mm in re.finditer(
                r'''["'((]((?:https?://ritsatv\.ru)?/(?:youtube|PLAYER)/[^"'\s)]+?\.(?:html|txt)(?:\?[^"'\s)]*)?)["')]''',
                text, re.I):
            u = mm.group(1)
            u = ('https://ritsatv.ru' + u) if u.startswith('/') else u
            low = u.lower()
            if u in out or low.endswith('/404.html') or re.search(r'(epg|prog|tvguide)\.html', low):
                continue
            out.append(u)
        return out

    def _resolvePlayer(self, ref, seen, depth=3):
        ref = self._unwrapProxy((ref or '').strip())
        if not ref or depth <= 0 or ref in seen:
            return []
        seen.add(ref)
        if self._isDirectStream(ref):
            return self._buildLinks([('', ref)])
        sts, payload = self.getPage(ref, {'header': dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        links = self._buildLinks(self._extractStreamStrings(payload)) or self._resolveEmbed(payload)
        if links:
            return links
        for nxt in self._nestedWrappers(payload):
            links = self._resolvePlayer(nxt, seen, depth - 1)
            if links:
                return links
        return []

    def _buildLinks(self, rawStrings):
        urlTab = []
        seen = set()
        for label, raw in rawStrings:
            for quality, url in self._splitStreamString(raw):
                url = self._unwrapProxy(url)
                if url in seen or '${' in url or '%(' in url:
                    continue
                seen.add(url)
                name = ' '.join(x for x in (label, quality) if x) or 'RitsaTV'
                low = url.lower()
                meta = {'Referer': self.MAIN_URL, 'User-Agent': self.HEADER.get('User-Agent', '')}
                if '.mpd' in low:
                    meta['iptv_proto'] = 'mpd'
                elif '.m3u8' in low:
                    meta['iptv_proto'] = 'm3u8'
                urlTab.append({'name': name, 'url': strwithmeta(url, meta)})
        return urlTab

    def getLinksForVideo(self, cItem):
        printDBG("RitsaTv.getLinksForVideo [%s]" % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        frame = self._pickPlayerFrame(data)

        # a bare YouTube embed - hand the video id to the generic resolver
        ytId = self.cm.ph.getSearchGroups(
            frame or data,
            r'youtu(?:\.be/|be\.com/(?:embed/|watch\?v=|live/|v/))([A-Za-z0-9_-]{6,})')[0]
        if ytId:
            ytUrl = 'https://www.youtube.com/watch?v=' + ytId
            try:
                links = self.up.getVideoLinkExt(ytUrl)
            except Exception:
                links = []
            return links or [{'name': 'YouTube', 'url': ytUrl, 'need_resolve': 1}]

        seen = set()
        urlTab = []
        if frame:
            fileMatch = re.search(r'[?&]file=([^&"\']+)', frame)
            urlTab = self._resolvePlayer(self._urlUnquote(fileMatch.group(1) if fileMatch else frame), seen)

        # fallbacks: a stream / embed / nested wrapper on the channel page itself
        # (player injected by JS with no usable iframe, wrapper gave nothing, ...)
        if not urlTab:
            urlTab = self._buildLinks(self._extractStreamStrings(data)) or self._resolveEmbed(data)
        if not urlTab:
            for nxt in self._nestedWrappers(data):
                urlTab = self._resolvePlayer(nxt, seen)
                if urlTab:
                    break
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("RitsaTv.getVideoLinks [%s]" % videoUrl)
        try:
            if self.up.checkHostSupport(videoUrl):
                return self.up.getVideoLinkExt(videoUrl)
        except Exception:
            printExc()
        return []

    def getArticleContent(self, cItem):
        printDBG("RitsaTv.getArticleContent [%s]" % cItem.get('url', ''))
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', ''),
                 'images': [{'title': '', 'url': cItem.get('icon', '')}] if cItem.get('icon') else [],
                 'other_info': {}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('RitsaTv.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        self.currList = []

        if name is None:
            self.listMainMenu()
        elif category == 'list_channels':
            self.listChannels(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RitsaTv(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
