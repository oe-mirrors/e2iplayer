# -*- coding: utf-8 -*-
# ARD Mediathek
# Rewritten for the api.ardmediathek.de "page-gateway" JSON API
# Last Modified: 28.08.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
import re
if not isPY2():
    from functools import cmp_to_key
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ardmediathek_iconquality = ConfigSelection(default="medium", choices=[("large", _("high")), ("medium", _("medium")), ("small", _("low"))])
config.plugins.iptvplayer.ardmediathek_prefformat = ConfigSelection(default="mp4,m3u8", choices=[("mp4,m3u8", "mp4,m3u8"), ("m3u8,mp4", "m3u8,mp4")])
config.plugins.iptvplayer.ardmediathek_prefquality = ConfigSelection(default="4", choices=[("0", _("low")), ("1", _("medium")), ("2", _("high")), ("3", _("very high")), ("4", _("hd"))])
config.plugins.iptvplayer.ardmediathek_prefmoreimportant = ConfigSelection(default="quality", choices=[("quality", _("quality")), ("format", _("format"))])
config.plugins.iptvplayer.ardmediathek_onelinkmode = ConfigYesNo(default=True)
config.plugins.iptvplayer.ardmediathek_audiotype = ConfigSelection(default="standard", choices=[("standard", _("standard")), ("all", _("all"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Icons quality"), config.plugins.iptvplayer.ardmediathek_iconquality))
    optionList.append(getConfigListEntry(_("Prefered format"), config.plugins.iptvplayer.ardmediathek_prefformat))
    optionList.append(getConfigListEntry(_("Prefered quality"), config.plugins.iptvplayer.ardmediathek_prefquality))
    optionList.append(getConfigListEntry(_("More important"), config.plugins.iptvplayer.ardmediathek_prefmoreimportant))
    optionList.append(getConfigListEntry(_("One link mode"), config.plugins.iptvplayer.ardmediathek_onelinkmode))
    optionList.append(getConfigListEntry(_("Audio track"), config.plugins.iptvplayer.ardmediathek_audiotype))
    return optionList
###################################################


def gettytul():
    return 'ARDmediathek'


class ARDmediathek(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API = 'https://api.ardmediathek.de/page-gateway/'
    CLIENT = 'ard'

    HTTP_HEADER = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        'Accept': 'application/json',
    }

    IMG_WIDTH = {'large': 1280, 'medium': 640, 'small': 320}
    QUALITY_MAP = {'hd': 4, 'veryhigh': 3, 'high': 2, 'med': 1, 'low': 0}

    VIDEO_TYPES = ('EPISODE', 'CLIP', 'EXCLUSIVE', 'MORE', 'PERMANENT_LIVESTREAM', 'LIVESTREAM', 'EVENT_LIVESTREAM')
    FOLDER_TYPES = ('SHOW', 'SERIES', 'SEASON_SERIES', 'COLLECTION', 'GROUPING', 'COMPILATION', 'EDITORIAL_COLLECTION')
    WIDGET_SKIP = ('navigation', 'top_navigation', 'banner', 'notification', 'region_gridlist', 'aeneas', 'grouping_header', 'headline', 'jsonld')

    RUBRIKEN = [
        (_('Films'), 'editorial/filme'),
        (_('Series'), 'editorial/serien'),
        (_('Documentaries'), 'editorial/dokus'),
        (_('Sport'), 'editorial/sport'),
        (_('Culture'), 'editorial/kultur'),
        (_('Knowledge & Nature'), 'editorial/natur'),
        (_('Travel'), 'editorial/reisen'),
        (_('Food'), 'editorial/food'),
        (_('Health'), 'editorial/gesundheit'),
        (_('Children & Family'), 'editorial/kinderfamilie'),
        (_('Show & Comedy'), 'editorial/shows_comedy'),
        (_('News (tagesschau)'), 'editorial/tagesschau'),
        (_('Accessible'), 'editorial/barrierefrei'),
        (_('All categories'), 'compilation/alle-rubriken'),
    ]

    def __init__(self):
        printDBG("ARDmediathek.__init__")
        CBaseHostClass.__init__(self, {'history': 'ARDmediathek', 'cookie': 'ardmediathek.cookie'})
        self.MAIN_URL = 'https://www.ardmediathek.de/'
        self.DEFAULT_ICON_URL = 'https://www.ardmediathek.de/sharing-icon-1280x720.1787634912994.png'

        self.MAIN_CAT_TAB = [
            {'category': 'list_page', 'title': _('Home page'), 'url': self._pageUrl('home')},
            {'category': 'list_az', 'title': _('Program A-Z'), 'url': self._pageUrl('editorial/experiment-a-z')},
            {'category': 'list_rubriken', 'title': _('Categories')},
            {'category': 'list_live', 'title': _('Live')},
            {'category': 'audio_menu', 'title': _('Radio') + ' (ARD Audiothek)'},
        ]
        self.MAIN_CAT_TAB += self.searchItems()

        self.watchedHelper = IPTVWatchedHelper('ardmediathek')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    # nav rows that are not real content containers - keep them out of the folder tree
    # list_widget_inline / list_page(home) carry no own url - dict(cItem) leaves the
    # enclosing page's url on them, which would collide with the page's own key
    WF_SKIP_CATEGORIES = ('list_az', 'list_live', 'list_rubriken', 'list_widget_inline',
                          'audio_menu', 'audio_categories', 'audio_live', 'audio_live_variants',
                          'search', 'search_next_page', 'search_history')

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            itemType = cItem.get('type', '')
            if itemType == 'video':
                url = self.wfNormalizeUrlKey(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if itemType in ('audio', 'more', 'marker'):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('category', '') in self.WF_SKIP_CATEGORIES:
                return ''
            url = self.wfNormalizeUrlKey(cItem.get('url', ''))
            if not url or url.rstrip('/').endswith('/home'):
                return ''
            return 'folder:%s' % url
        except Exception:
            printExc()
        return ''

    ###################################################
    # helpers
    ###################################################
    def _pageUrl(self, path):
        return '%spages/%s/%s?embedded=false' % (self.API, self.CLIENT, path)

    @staticmethod
    def _normHref(href):
        # page/item responses are huge with embedded=true - always request the slim variant
        return (href or '').replace('embedded=true', 'embedded=false')

    @staticmethod
    def _widgetUrl(href):
        # a widget's own endpoint DOES need embedded=true to return its teasers
        href = (href or '').replace('embedded=false', 'embedded=true')
        if 'embedded=' not in href:
            href += ('&' if '?' in href else '?') + 'embedded=true'
        href = re.sub(r'pageSize=\d+', 'pageSize=40', href)
        return href

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

    def _imgUrl(self, images):
        try:
            if not isinstance(images, dict) or not images:
                return ''
            img = images.get('aspect16x9') or images.get('aspect16x7') or images.get('aspect3x4')
            if img is None:
                img = list(images.values())[0]
            src = (img or {}).get('src', '') or ''
            if not src:
                return ''
            width = str(self.IMG_WIDTH.get(config.plugins.iptvplayer.ardmediathek_iconquality.value, 640))
            return src.replace('{width}', width).replace('%7Bwidth%7D', width)
        except Exception:
            printExc()
            return ''

    def _teaserTitle(self, t):
        show = ''
        try:
            show = self.cleanHtmlStr((t.get('show') or {}).get('title', '') or '')
        except Exception:
            show = ''
        title = self.cleanHtmlStr(t.get('mediumTitle') or t.get('shortTitle') or t.get('longTitle') or t.get('title') or '')
        if show and title and show.lower() not in title.lower():
            title = '%s - %s' % (show, title)
        elif not title:
            title = show
        return title

    def _teaserDesc(self, t):
        parts = []
        # full synopsis is only on the item detail page; in list teasers the best
        # we have is the "| ..." tail of the medium/long title
        text = self.cleanHtmlStr(t.get('synopsis') or '')
        if not text:
            lt = self.cleanHtmlStr(t.get('mediumTitle') or t.get('longTitle') or '')
            if '|' in lt:
                text = lt.split('|', 1)[1].strip()
        if text:
            parts.append(text)

        meta = []
        dur = t.get('duration')
        if dur:
            try:
                dur = int(dur)
                h, rem = divmod(dur, 3600)
                m, s = divmod(rem, 60)
                meta.append('%d:%02d:%02d' % (h, m, s) if h else '%d:%02d min' % (m, s))
            except Exception:
                pass
        bcast = t.get('broadcastedOn') or ''
        if isinstance(bcast, str) and len(bcast) >= 10:
            meta.append(bcast[:10])
        avail = t.get('availableTo') or ''
        if isinstance(avail, str) and len(avail) >= 10:
            meta.append(_('available until %s') % avail[:10])
        fsk = t.get('maturityContentRating') or ''
        if fsk:
            meta.append(str(fsk))
        if meta:
            parts.append(' | '.join(meta))
        return '[/br]'.join(parts)

    @staticmethod
    def _href(links, *keys):
        links = links or {}
        for key in keys:
            href = ((links.get(key) or {}).get('href')) or ''
            if href:
                return href
        return ''

    def _teasers(self, widget):
        tab = widget.get('teasers')
        return tab if isinstance(tab, list) else []

    ###################################################
    # teaser -> dir / video
    ###################################################
    def _addTeaser(self, cItem, t):
        try:
            if not isinstance(t, dict):
                return
            href = self._href(t.get('links'), 'target', 'self')
            if not href:
                return
            cat = (t.get('coreAssetType') or t.get('type') or '').upper()
            title = self._teaserTitle(t)
            if not title:
                return
            params = dict(cItem)
            params.pop('page', None)
            params.pop('w_teasers', None)
            params.update({'title': title, 'url': self._normHref(href), 'icon': self._imgUrl(t.get('images')), 'desc': self._teaserDesc(t), 'good_for_fav': True})

            isFolder = cat in self.FOLDER_TYPES or '/grouping/' in href or '/editorial/' in href or '/compilation/' in href
            isVideo = (cat in self.VIDEO_TYPES or '/item/' in href) and not isFolder
            if isVideo:
                if 'LIVESTREAM' in cat:
                    params['live'] = True
                    params['title'] = '[L] ' + title
                else:
                    show = self.cleanHtmlStr((t.get('show') or {}).get('title', '') or '')
                    params['title'] = normalizeMediathekTitle(
                        title, date=t.get('broadcastedOn') or '',
                        sxeHint='%s %s' % (t.get('mediumTitle') or '', t.get('longTitle') or ''),
                        isMovie=(not show) and cat not in ('EPISODE', 'CLIP'))
                self.addVideo(params)
            else:
                params['category'] = 'list_page'
                self.addDir(params)
        except Exception:
            printExc()

    ###################################################
    # page (pages/.../...) -> widgets
    ###################################################
    def listPage(self, cItem):
        printDBG('ARDmediathek.listPage [%s]' % cItem['url'])
        data = self._json(self._normHref(cItem['url']))
        if not data:
            return
        widgets = data.get('widgets')
        if not isinstance(widgets, list):
            widgets = [data]

        contentWidgets = []
        for w in widgets:
            if not isinstance(w, dict):
                continue
            wtype = (w.get('type') or '').lower()
            if wtype in self.WIDGET_SKIP:
                continue
            if w.get('mediaCollection'):
                continue
            selfHref = self._href(w.get('links'), 'self')
            inlineTeasers = self._teasers(w)
            if not selfHref and not inlineTeasers:
                continue
            contentWidgets.append((w, selfHref, inlineTeasers))

        # a single content widget -> flatten it straight away
        if len(contentWidgets) == 1:
            w, selfHref, inlineTeasers = contentWidgets[0]
            if inlineTeasers:
                self._listWidget(cItem, w)
            else:
                self.listWidget(dict(cItem, url=self._widgetUrl(selfHref)))
            return

        for w, selfHref, inlineTeasers in contentWidgets:
            title = self.cleanHtmlStr(w.get('title') or '') or _('Section')
            params = dict(cItem)
            params.pop('page', None)
            params.update({'title': title, 'good_for_fav': False, 'icon': self._imgUrl(inlineTeasers[0].get('images')) if inlineTeasers else ''})
            if inlineTeasers and not selfHref:
                params.update({'category': 'list_widget_inline', 'w_teasers': inlineTeasers})
            else:
                params.update({'category': 'list_widget', 'url': self._widgetUrl(selfHref)})
            self.addDir(params)

    def listWidget(self, cItem):
        printDBG('ARDmediathek.listWidget [%s]' % cItem['url'])
        data = self._json(cItem['url'])
        if not data:
            return
        if isinstance(data.get('widgets'), list) and data['widgets']:
            data = data['widgets'][0]
        self._listWidget(cItem, data)

    def _listWidget(self, cItem, widget):
        for t in self._teasers(widget):
            self._addTeaser(cItem, t)
        try:
            pag = widget.get('pagination') or {}
            pageNo = int(pag.get('pageNumber', 0))
            pageSize = int(pag.get('pageSize', 0))
            total = int(pag.get('totalElements', 0))
            selfHref = self._widgetUrl(self._href(widget.get('links'), 'self'))
            if selfHref and pageSize and total and (pageNo + 1) * pageSize < total:
                if re.search(r'pageNumber=\d+', selfHref):
                    nextHref = re.sub(r'pageNumber=\d+', 'pageNumber=%d' % (pageNo + 1), selfHref)
                else:
                    nextHref = selfHref + ('&' if '?' in selfHref else '?') + 'pageNumber=%d' % (pageNo + 1)
                params = dict(cItem)
                params.update({'category': 'list_widget', 'title': _('Next page'), 'url': nextHref, 'good_for_fav': False})
                self.addDir(params)
        except Exception:
            printExc()

    def listWidgetInline(self, cItem):
        for t in cItem.get('w_teasers', []):
            self._addTeaser(cItem, t)

    ###################################################
    # A-Z
    ###################################################
    def listAZ(self, cItem):
        data = self._json(self._normHref(cItem['url']))
        if not data:
            return
        for w in data.get('widgets', []):
            if not isinstance(w, dict):
                continue
            title = self.cleanHtmlStr(w.get('title') or '')
            selfHref = self._href(w.get('links'), 'self')
            teasers = self._teasers(w)
            if not title or (not selfHref and not teasers):
                continue
            params = dict(cItem)
            params.pop('page', None)
            params.update({'title': title, 'good_for_fav': False, 'icon': ''})
            if teasers and not selfHref:
                params.update({'category': 'list_widget_inline', 'w_teasers': teasers})
            else:
                params.update({'category': 'list_widget', 'url': self._widgetUrl(selfHref)})
            self.addDir(params)

    ###################################################
    # Rubriken
    ###################################################
    def listRubriken(self, cItem):
        for title, path in self.RUBRIKEN:
            params = dict(cItem)
            params.pop('page', None)
            params.update({'category': 'list_page', 'title': title, 'url': self._pageUrl(path), 'good_for_fav': True, 'icon': ''})
            self.addDir(params)

    ###################################################
    # Live
    ###################################################
    def listLive(self, cItem):
        data = self._json(self._pageUrl('home'))
        if not data:
            return
        liveHref = ''
        for w in data.get('widgets', []):
            if not isinstance(w, dict):
                continue
            title = (w.get('title') or '').lower()
            if 'live' in title and (w.get('type') or '') in ('gridlist', 'extended_gridlist', 'compilation'):
                liveHref = self._href(w.get('links'), 'self')
                if 'tv-programme live' in title or 'livestream' in title:
                    break
        if not liveHref:
            return
        wdata = self._json(self._widgetUrl(liveHref))
        if not wdata:
            return
        if isinstance(wdata.get('widgets'), list) and wdata['widgets']:
            wdata = wdata['widgets'][0]
        for t in self._teasers(wdata):
            self._addTeaser(cItem, t)

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ARDmediathek.listSearchResult [%s]" % searchPattern)
        page = cItem.get('page', 0)
        query = cItem.get('query') or urllib_quote_plus(searchPattern)
        url = '%spages/%s/search?searchString=%s&embedded=false&vodPageNumber=%d&showPageNumber=%d' % (self.API, self.CLIENT, query, page, page)
        data = self._json(url)
        if not data:
            return
        if page == 0:
            for t in data.get('showResults') or []:
                self._addTeaser(cItem, t)
        for t in data.get('vodResults') or []:
            self._addTeaser(cItem, t)
        try:
            total = int(data.get('vodTotal', 0))
            pageSize = int(data.get('vodPageSize', 24)) or 24
            if (page + 1) * pageSize < total:
                params = dict(cItem)
                params.update({'title': _('Next page'), 'page': page + 1, 'query': query})
                self.addDir(params)
        except Exception:
            printExc()

    ###################################################
    # stream links
    ###################################################
    def _subtitles(self, embedded):
        subTracks = []
        try:
            for sub in embedded.get('subtitles', []) or []:
                best = ''
                for src in sub.get('sources', []) or []:
                    surl = src.get('url', '') or ''
                    if not surl:
                        continue
                    if 'webvtt' in surl or surl.endswith('.vtt'):
                        best = surl
                        break
                    best = surl
                if best:
                    if best.startswith('//'):
                        best = 'https:' + best
                    subTracks.append({'title': _('German'), 'url': best, 'lang': 'de', 'format': 'vtt' if ('vtt' in best) else 'ttml'})
        except Exception:
            printExc()
        return subTracks

    def getLinksForVideo(self, cItem):
        printDBG("ARDmediathek.getLinksForVideo [%s]" % cItem.get('url', ''))
        if cItem.get('audio_url'):
            return [{'need_resolve': 0, 'name': _('Audio'), 'url': cItem['audio_url']}]
        url = self._normHref(cItem.get('url', ''))
        if '/item/' not in url:
            return []
        data = self._json(url)
        if not data:
            return []

        embedded = None
        synopsis = ''
        live = bool(cItem.get('live'))
        for w in data.get('widgets', []):
            if not isinstance(w, dict):
                continue
            if not synopsis and w.get('synopsis'):
                synopsis = self.cleanHtmlStr(w.get('synopsis'))
            mc = w.get('mediaCollection')
            if not mc:
                continue
            embedded = mc.get('embedded')
            if not embedded and mc.get('href'):
                embedded = self._json(mc['href'])
            if 'live' in (w.get('type') or '').lower():
                live = True
            break
        if not isinstance(embedded, dict):
            return []

        preferedQuality = int(config.plugins.iptvplayer.ardmediathek_prefquality.value)
        preferedFormat = config.plugins.iptvplayer.ardmediathek_prefformat.value
        formatMap = {}
        tmp = preferedFormat.split(',')
        for i in range(len(tmp)):
            formatMap[tmp[i]] = i
        allowAllAudio = config.plugins.iptvplayer.ardmediathek_audiotype.value == 'all'

        subTracks = self._subtitles(embedded)
        tmpUrlTab = []
        try:
            for stream in embedded.get('streams', []) or []:
                for media in stream.get('media', []) or []:
                    murl = media.get('url', '') or ''
                    if not murl:
                        continue
                    audios = media.get('audios', []) or []
                    audioKind = (audios[0].get('kind') if audios else 'standard') or 'standard'
                    if audioKind != 'standard' and not allowAllAudio:
                        continue
                    if murl.startswith('//'):
                        murl = 'https:' + murl
                    mime = (media.get('mimeType') or '').lower()
                    isHls = 'mpegurl' in mime or '.m3u8' in murl.lower()
                    audioSuffix = '' if audioKind == 'standard' else ' [%s]' % audioKind

                    if isHls and live:
                        # hand the master playlist straight to the player for live
                        tmpUrlTab.append({'url': murl, 'quality_name': 'auto' + audioSuffix, 'quality': 10,
                                          'quality_pref': 0, 'format_name': 'm3u8', 'format_pref': formatMap.get('m3u8', 10)})
                    elif isHls:
                        try:
                            hlsList = getDirectM3U8Playlist(strwithmeta(murl, {'iptv_proto': 'm3u8'}), checkExt=False)
                        except Exception:
                            hlsList = []
                        for it in hlsList:
                            res = it.get('with', 0) or 0
                            quality = 'low'
                            if res > 320:
                                quality = 'med'
                            if res > 600:
                                quality = 'high'
                            if res > 800:
                                quality = 'veryhigh'
                            if res > 1200:
                                quality = 'hd'
                            qVal = self.QUALITY_MAP.get(quality, 10)
                            tmpUrlTab.append({'url': it['url'], 'quality_name': '%s %sx%s' % (quality, res, it.get('heigth', 0)) + audioSuffix,
                                              'quality': qVal, 'quality_pref': abs(qVal - preferedQuality),
                                              'format_name': 'm3u8', 'format_pref': formatMap.get('m3u8', 10)})
                        if not hlsList:
                            tmpUrlTab.append({'url': murl, 'quality_name': 'auto' + audioSuffix, 'quality': 10,
                                              'quality_pref': 0, 'format_name': 'm3u8', 'format_pref': formatMap.get('m3u8', 10)})
                    else:
                        label = media.get('forcedLabel') or ''
                        height = 0
                        m = re.search(r'(\d{3,4})\s*[pi]', label)
                        if m:
                            height = int(m.group(1))
                        else:
                            try:
                                height = int(media.get('maxVResolutionPx') or 0)
                            except Exception:
                                height = 0
                        quality = 'low'
                        if height >= 360:
                            quality = 'med'
                        if height >= 540:
                            quality = 'high'
                        if height >= 720:
                            quality = 'veryhigh'
                        if height >= 1080:
                            quality = 'hd'
                        if not label:
                            label = quality
                        qVal = self.QUALITY_MAP.get(quality, 10)
                        tmpUrlTab.append({'url': murl, 'quality_name': str(label) + audioSuffix,
                                          'quality': qVal, 'quality_pref': abs(qVal - preferedQuality),
                                          'format_name': 'mp4', 'format_pref': formatMap.get('mp4', 10)})
        except Exception:
            printExc()

        if not tmpUrlTab:
            return []

        def _cmpLinks(it1, it2):
            moreImportant = config.plugins.iptvplayer.ardmediathek_prefmoreimportant.value
            # lower is better for *_pref, higher is better for raw quality
            if moreImportant == 'quality':
                order = (('quality_pref', 1), ('quality', -1), ('format_pref', 1))
            else:
                order = (('format_pref', 1), ('quality_pref', 1), ('quality', -1))
            for key, direction in order:
                if it1[key] != it2[key]:
                    return -direction if it1[key] < it2[key] else direction
            return 0

        if isPY2():
            tmpUrlTab.sort(_cmpLinks)
        else:
            tmpUrlTab.sort(key=cmp_to_key(_cmpLinks))

        onelinkmode = config.plugins.iptvplayer.ardmediathek_onelinkmode.value
        urlTab = []
        for item in tmpUrlTab:
            if not self.cm.isValidUrl(item['url']):
                continue
            decorateParams = {'iptv_livestream': live}
            if item['format_name'] == 'm3u8':
                decorateParams['iptv_proto'] = 'm3u8'
            if subTracks:
                decorateParams['external_sub_tracks'] = subTracks
            urlTab.append({'need_resolve': 0, 'name': '%s %s' % (item['quality_name'], item['format_name']), 'url': self.up.decorateUrl(item['url'], decorateParams)})
            if onelinkmode:
                break
        if not live:
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))
        return urlTab

    ###################################################
    # article / info window
    ###################################################
    def getArticleContent(self, cItem):
        url = self._normHref(cItem.get('url', ''))
        if '/item/' not in url:
            return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', ''), 'images': [{'title': '', 'url': cItem.get('icon', '')}]}]
        data = self._json(url)
        widget = {}
        for w in ((data or {}).get('widgets') or []):
            if isinstance(w, dict) and (w.get('synopsis') or w.get('mediaCollection')):
                widget = w
                break
        title = self.cleanHtmlStr(widget.get('title') or cItem.get('title', ''))
        text = self.cleanHtmlStr(widget.get('synopsis') or cItem.get('desc', ''))
        otherInfo = {}
        show = (widget.get('show') or {}).get('title') or ''
        if show:
            otherInfo['title'] = self.cleanHtmlStr(show)
        bcast = widget.get('broadcastedOn') or ''
        if isinstance(bcast, str) and len(bcast) >= 10:
            otherInfo['premiere'] = bcast[:10]
        avail = widget.get('availableTo') or ''
        if isinstance(avail, str) and len(avail) >= 10:
            otherInfo['remaining'] = _('available until %s') % avail[:10]
        fsk = widget.get('maturityContentRating') or ''
        if fsk:
            otherInfo['fsk'] = str(fsk)
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': cItem.get('icon', '')}], 'other_info': otherInfo}]

    ###################################################
    # ARD Audiothek (Radio) - separate REST API
    ###################################################
    AUDIO_API = 'https://api.ardaudiothek.de/'
    AUDIO_LIMIT = 40

    def _audioJson(self, path):
        url = path if path.startswith('http') else self.AUDIO_API + path.lstrip('/')
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    def _audioImg(self, node):
        src = ((node or {}).get('image') or {}).get('url') or ''
        if not src:
            return ''
        width = str(self.IMG_WIDTH.get(config.plugins.iptvplayer.ardmediathek_iconquality.value, 640))
        return src.replace('{width}', width).replace('%7Bwidth%7D', width)

    def listAudioMenu(self, cItem):
        for cat, title in (('audio_live', _('Live')), ('audio_categories', _('Categories'))):
            params = dict(cItem)
            params.update({'category': cat, 'title': title})
            self.addDir(params)
        for it in self.searchItems():
            params = dict(cItem)
            params.update(it)
            params['f_audio'] = True
            self.addDir(params)

    def listAudioLive(self, cItem):
        data = self._audioJson('organizations')
        try:
            orgs = data['data']['organizations']['nodes']
        except Exception:
            return
        for org in orgs:
            orgName = self.cleanHtmlStr(org.get('name') or '')
            for ps in ((org.get('publicationServices') or {}).get('nodes') or []):
                items = ((ps.get('liveStreams') or {}).get('items')) or []
                streams = []
                for it in items:
                    st = it.get('stream') or {}
                    surl = st.get('streamUrl') or ''
                    if surl:
                        streams.append((self.cleanHtmlStr(st.get('shortTitle') or st.get('sender') or ps.get('title') or ''), surl))
                if not streams:
                    continue
                psTitle = self.cleanHtmlStr(ps.get('title') or '')
                label = '%s - %s' % (orgName, psTitle) if orgName and orgName not in psTitle else psTitle
                icon = self._audioImg(ps)
                if len(streams) == 1:
                    params = dict(cItem)
                    params.update({'title': label, 'audio_url': streams[0][1], 'live': True, 'icon': icon, 'good_for_fav': True})
                    self.addAudio(params)
                else:
                    params = dict(cItem)
                    params.update({'category': 'audio_live_variants', 'title': label, 'icon': icon,
                                   'a_streams': streams, 'good_for_fav': False})
                    self.addDir(params)

    def listAudioLiveVariants(self, cItem):
        for name, surl in cItem.get('a_streams', []):
            params = dict(cItem)
            params.pop('a_streams', None)
            params.update({'title': name, 'audio_url': surl, 'live': True, 'good_for_fav': True})
            self.addAudio(params)

    def listAudioCategories(self, cItem):
        data = self._audioJson('editorialcategories')
        try:
            nodes = data['data']['editorialCategories']['nodes']
        except Exception:
            return
        for n in nodes:
            if not n.get('id'):
                continue
            params = dict(cItem)
            params.update({'category': 'audio_category', 'title': self.cleanHtmlStr(n.get('title') or ''),
                           'url': 'editorialcategories/%s?limit=%d' % (n['id'], self.AUDIO_LIMIT), 'icon': self._audioImg(n), 'good_for_fav': True})
            self.addDir(params)

    def listAudioCategory(self, cItem):
        data = self._audioJson(cItem['url'])
        try:
            sections = data['data']['editorialCategory']['sections']
        except Exception:
            return
        seen = set()
        for sec in sections:
            for n in (sec.get('nodes') or []):
                pid = n.get('id')
                if not pid or pid in seen or not n.get('title'):
                    continue
                seen.add(pid)
                self._addProgramSet(cItem, n)

    def _addProgramSet(self, cItem, n):
        params = dict(cItem)
        params.pop('page', None)
        desc = self.cleanHtmlStr(n.get('synopsis') or '')
        cnt = n.get('numberOfElements')
        if cnt:
            desc = (_('%s episodes') % cnt) + ('[/br]' + desc if desc else '')
        params.update({'category': 'audio_programset', 'title': self.cleanHtmlStr(n.get('title') or ''),
                       'url': 'programsets/%s?offset=0&limit=%d' % (n['id'], self.AUDIO_LIMIT),
                       'p_offset': 0, 'p_total': int(cnt) if cnt else 0,
                       'icon': self._audioImg(n), 'desc': desc, 'good_for_fav': True})
        self.addDir(params)

    def listAudioProgramSet(self, cItem):
        data = self._audioJson(cItem['url'])
        try:
            ps = data['data']['programSet']
            nodes = ps['items']['nodes']
        except Exception:
            return
        total = cItem.get('p_total') or ps.get('numberOfElements') or 0
        for it in nodes:
            audios = it.get('audios') or []
            aurl = (audios[0].get('url') if audios else '') or ''
            if not aurl:
                continue
            descTab = []
            dur = it.get('duration')
            if dur:
                try:
                    m, s = divmod(int(dur), 60)
                    descTab.append('%d:%02d' % (m, s))
                except Exception:
                    pass
            pub = it.get('publicationStartDateAndTime') or ''
            if isinstance(pub, str) and len(pub) >= 10:
                descTab.append(pub[:10])
            syn = self.cleanHtmlStr(it.get('synopsis') or '')
            params = dict(cItem)
            params.pop('page', None)
            params.pop('p_offset', None)
            params.update({'title': self.cleanHtmlStr(it.get('title') or ''), 'audio_url': aurl,
                           'icon': self._audioImg(it) or cItem.get('icon', ''),
                           'desc': '[/br]'.join([x for x in (', '.join(descTab), syn) if x]), 'good_for_fav': True})
            self.addAudio(params)
        offset = int(cItem.get('p_offset', 0)) + len(nodes)
        if nodes and total and offset < int(total):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'p_offset': offset,
                           'url': re.sub(r'offset=\d+', 'offset=%d' % offset, cItem['url']), 'good_for_fav': False})
            self.addDir(params)

    def listAudioSearch(self, cItem, searchPattern):
        page = cItem.get('page', 0)
        offset = page * self.AUDIO_LIMIT
        url = 'search/programsets?query=%s&offset=%d&limit=%d' % (urllib_quote_plus(searchPattern), offset, self.AUDIO_LIMIT)
        data = self._audioJson(url)
        try:
            ps = data['data']['search']['programSets']
            nodes = ps['nodes']
        except Exception:
            return
        for n in nodes:
            if n.get('id') and n.get('title'):
                self._addProgramSet(cItem, n)
        total = ps.get('numberOfElements') or 0
        if nodes and total and offset + len(nodes) < int(total):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    ###################################################
    # dispatcher
    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ARDmediathek.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("ARDmediathek.handleService: name[%s], category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_page':
            self.listPage(self.currItem)
        elif category == 'list_widget':
            self.listWidget(self.currItem)
        elif category == 'list_widget_inline':
            self.listWidgetInline(self.currItem)
        elif category == 'list_az':
            self.listAZ(self.currItem)
        elif category == 'list_rubriken':
            self.listRubriken(self.currItem)
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'audio_menu':
            self.listAudioMenu(self.currItem)
        elif category == 'audio_categories':
            self.listAudioCategories(self.currItem)
        elif category == 'audio_live':
            self.listAudioLive(self.currItem)
        elif category == 'audio_live_variants':
            self.listAudioLiveVariants(self.currItem)
        elif category == 'audio_category':
            self.listAudioCategory(self.currItem)
        elif category == 'audio_programset':
            self.listAudioProgramSet(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            if self.currItem.get('f_audio'):
                self.listAudioSearch(cItem, searchPattern)
            else:
                self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            baseItem = {'name': 'history', 'category': 'search'}
            if self.currItem.get('f_audio'):
                baseItem['f_audio'] = True
            self.listsHistory(baseItem, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ARDmediathek(), True)
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('ardmediathek')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
