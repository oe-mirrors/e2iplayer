# -*- coding: utf-8 -*-
# MP3Quran.net - Quran recitations, radios, videos, tafsir and tadabor.
# Everything comes from the public mp3quran.net API v3 (21 languages); the
# "Atheer radio" categories come from its api_2 endpoint (Arabic only).
# Surah audio is <moshaf server><NNN>.mp3 (redirects to cdn.mp3quran.net).
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Components.config import config, ConfigSelection, getConfigListEntry

# API locales (api/v3/languages); "auto" follows the Enigma2 language
LANGUAGES = [('auto', _('Auto')), ('ar', 'العربية'), ('eng', 'English'), ('fr', 'Français'), ('ru', 'Русский'),
             ('de', 'Deutsch'), ('es', 'Español'), ('tr', 'Türkçe'), ('cn', '中文'), ('th', 'ไทย'), ('ur', 'اردو'),
             ('bn', 'বাংলা'), ('bs', 'Bosanski'), ('ug', 'ئۇيغۇرچە'), ('fa', 'فارسی'), ('tg', 'Тоҷикӣ'), ('ml', 'മലയാളം'),
             ('tl', 'Tagalog'), ('id', 'Indonesia'), ('pt', 'Português'), ('ha', 'Hausa'), ('sw', 'Kiswahili')]
config.plugins.iptvplayer.mp3quran_lang = ConfigSelection(default='auto', choices=LANGUAGES)


def GetConfigList():
    return [getConfigListEntry(_('Language:'), config.plugins.iptvplayer.mp3quran_lang)]


def gettytul():
    return 'https://www.mp3quran.net/'


class MP3Quran(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API = 'https://www.mp3quran.net/api/v3/'
    ATHEER_API = 'https://api.mp3quran.net/api_2/atheer/'
    LIVE_RADIO = 'http://live.mp3quran.net:8006/;'  # NOSONAR - Shoutcast stream, no https on this port
    PAGE_SIZE = 100
    # folder category -> item key holding its stable id (watched flag)
    FOLDER_KEYS = {'list_moshaf': 'reciter_id', 'list_surahs': 'moshaf_id', 'list_videos': 'video_reciter',
                   'list_tafsir': 'sura_id', 'list_tadabor': 'sura_key'}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'MP3Quran', 'cookie': 'MP3Quran.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = 'https://www.mp3quran.net/img/logo2.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json', 'Referer': self.MAIN_URL})
        self.defaultParams = {'header': self.HEADER}
        self._cache = {}
        self.watchedHelper = IPTVWatchedHelper('mp3quran')
        self.wfInitFolderCache()

    def _getWatchedKeyForItem(self, cItem):
        # files by their url (stable across languages), folders by their API id;
        # live radios and the navigation folders have no key
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                url = cItem.get('url', '')
                return 'video:%s' % url if url else ''
            category = cItem.get('category', '')
            idKey = self.FOLDER_KEYS.get(category)
            if idKey and cItem.get(idKey) not in (None, ''):
                if category == 'list_tafsir':
                    return 'folder:%s:%s:%s' % (category, cItem.get('tafsir_id'), cItem.get(idKey))
                if category == 'list_surahs':
                    return 'folder:%s:%s:%s' % (category, cItem.get('reciter_id'), cItem.get(idKey))
                return 'folder:%s:%s' % (category, cItem.get(idKey))
        except Exception:
            printExc()
        return ''

    def getLang(self):
        lang = config.plugins.iptvplayer.mp3quran_lang.value
        if lang == 'auto':
            lang = {'en': 'eng', 'zh': 'cn'}.get(GetDefaultLang(), GetDefaultLang())
            if lang not in [k for k, _v in LANGUAGES]:
                lang = 'eng'
        return lang

    def getJson(self, url, params=None):
        if url in self._cache:
            return self._cache[url]
        sts, data = self.cm.getPage(url, params or self.defaultParams)
        if not sts:
            return {}
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return {}
        self._cache[url] = data
        return data

    def api(self, endpoint, **args):
        args.setdefault('language', self.getLang())
        query = '&'.join('%s=%s' % (k, v) for k, v in sorted(args.items()))
        return self.getJson('%s%s?%s' % (self.API, endpoint, query))

    def getSurahNames(self):
        return dict((s.get('id'), (s.get('name') or '').strip()) for s in self.api('suwar').get('suwar', []))

    def getReciters(self, lang=None):
        reciters = self.api('reciters', language=lang or self.getLang()).get('reciters', [])
        return sorted(reciters, key=lambda r: (r.get('name') or '').strip().lower())

    def addReciter(self, cItem, reciter):
        moshafs = reciter.get('moshaf') or []
        if not moshafs:
            return
        params = stripPagerKeys(dict(cItem), ('url',))
        params.update({'good_for_fav': True, 'category': 'list_moshaf', 'title': (reciter.get('name') or '').strip(),
                       'reciter_id': reciter.get('id'), 'desc': self.moshafDesc(moshafs[0]) if len(moshafs) == 1 else
                       _('%d recitations') % len(moshafs)})
        self.addDir(params)

    def moshafDesc(self, moshaf):
        total = moshaf.get('surah_total') or 0
        desc = moshaf.get('name', '')
        if total == 114:
            return '%s\n%s' % (desc, _('Complete Quran'))
        return '%s\n%s: %s' % (desc, _('Surahs'), total)

    def _pageSlice(self, cItem, rows):
        # (page, last page, rows of the page) - the long API lists are shown PAGE_SIZE rows at a time
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = max(1, (len(rows) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        page = min(page, lastPage)
        return page, lastPage, rows[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]

    def _addLocalPaging(self, cItem, page, lastPage):
        if lastPage > 1:
            # the url template only serves "Jump" - the list is cut by cItem['page']
            addPagingItems(self, cItem, page, page < lastPage, lastPage, '%s#%s-{page}' % (self.MAIN_URL, cItem.get('category', '')))

    def listReciters(self, cItem):
        page, lastPage, reciters = self._pageSlice(cItem, self.getReciters())
        for reciter in reciters:
            self.addReciter(cItem, reciter)
        self._addLocalPaging(cItem, page, lastPage)

    def findReciter(self, reciterId):
        for reciter in self.getReciters():
            if reciter.get('id') == reciterId:
                return reciter
        return {}

    def listMoshaf(self, cItem):
        moshafs = self.findReciter(cItem.get('reciter_id')).get('moshaf') or []
        if len(moshafs) == 1:
            return self.listSurahs(dict(cItem, moshaf_id=moshafs[0].get('id')))
        for moshaf in sorted(moshafs, key=lambda m: m.get('name', '')):
            params = dict(cItem)
            params.update({'category': 'list_surahs', 'title': moshaf.get('name', ''), 'moshaf_id': moshaf.get('id'),
                           'desc': self.moshafDesc(moshaf)})
            self.addDir(params)

    def listSurahs(self, cItem):
        reciter = self.findReciter(cItem.get('reciter_id'))
        moshaf = next((m for m in reciter.get('moshaf') or [] if m.get('id') == cItem.get('moshaf_id')), None)
        if not moshaf:
            return
        server = moshaf.get('server', '')
        names = self.getSurahNames()
        reciterName = (reciter.get('name') or '').strip()
        # with name normalisation on the reciter leads the title, so the
        # downloaded files of different reciters do not share one name
        withReciter = IsMediaNamingNormalized() and reciterName
        for num in (moshaf.get('surah_list') or '').split(','):
            if not num.strip().isdigit():
                continue
            num = int(num)
            title = ('%03d. %s' % (num, names.get(num, ''))).strip()
            if withReciter:
                title = '%s - %s' % (reciterName, title)
            self.addAudio({'good_for_fav': True, 'title': title, 'url': '%s%03d.mp3' % (server, num),
                           'desc': '%s\n%s' % (reciterName, moshaf.get('name', ''))})

    def listRadios(self, cItem):
        radios = [r for r in self.api('radios').get('radios', []) if r.get('url')]
        page, lastPage, radios = self._pageSlice(cItem, sorted(radios, key=lambda r: (r.get('name') or '').strip().lower()))
        for radio in radios:
            self.addAudio({'good_for_fav': True, 'title': (radio.get('name') or '').strip(), 'url': radio['url'],
                           'desc': _('Live radio'), 'live': True})
        self._addLocalPaging(cItem, page, lastPage)

    def atheer(self, url):
        params = {'header': dict(self.HEADER, Origin='https://www.atheer-radio.com', Referer='https://www.atheer-radio.com/')}
        return self.getJson(url, params).get('reads', [])

    def listAtheerCats(self, cItem):
        for cat in self.atheer(self.ATHEER_API + 'radios_cats?language=ar'):
            params = dict(cItem)
            params.update({'category': 'list_atheer', 'title': cat.get('name', ''), 'url': cat.get('link') or
                           '%sradios?radio_cat=%s' % (self.ATHEER_API, cat.get('id'))})
            self.addDir(params)

    def listAtheer(self, cItem):
        seen = set()
        for radio in self.atheer(cItem['url']):
            # the API lists some stations twice under different names
            if radio.get('URL'):
                if radio['URL'] in seen:
                    continue
                seen.add(radio['URL'])
            if radio.get('list'):
                params = dict(cItem)
                params.update({'category': 'list_atheer_sub', 'title': radio.get('name', ''), 'radio_id': radio.get('id')})
                self.addDir(params)
            elif radio.get('URL'):
                self.addAudio({'good_for_fav': True, 'title': radio.get('name', ''), 'url': radio['URL'], 'desc': _('Live radio'), 'live': True})

    def listAtheerSub(self, cItem):
        for radio in self.atheer(cItem['url']):
            if radio.get('id') == cItem.get('radio_id'):
                for item in radio.get('list') or []:
                    if item.get('url'):
                        self.addAudio({'good_for_fav': True, 'title': item.get('name', ''), 'url': item['url']})

    def listVideoReciters(self, cItem):
        for entry in sorted(self.api('videos').get('videos', []), key=lambda v: (v.get('reciter_name') or '').lower()):
            params = dict(cItem)
            params.update({'category': 'list_videos', 'title': (entry.get('reciter_name') or '').strip(), 'video_reciter': entry.get('id'),
                           'desc': _('%d videos') % len(entry.get('videos') or [])})
            self.addDir(params)

    def listVideos(self, cItem):
        for entry in self.api('videos').get('videos', []):
            if entry.get('id') != cItem.get('video_reciter'):
                continue
            for idx, video in enumerate(entry.get('videos') or []):
                if video.get('video_url'):
                    self.addVideo({'good_for_fav': True, 'title': '%s %d' % ((entry.get('reciter_name') or '').strip(), idx + 1),
                                   'url': video['video_url'], 'icon': video.get('video_thumb_url', '')})

    def listTafasir(self, cItem):
        tafasir = self.api('tafasir', language='ar').get('tafasir', [])
        if isinstance(tafasir, dict):
            tafasir = [tafasir]
        for tafsir in tafasir:
            params = dict(cItem)
            params.update({'category': 'list_tafsir_surahs', 'title': tafsir.get('name', ''), 'tafsir_id': tafsir.get('id')})
            self.addDir(params)

    def tafsirItems(self, tafsirId):
        return self.api('tafsir', tafsir=tafsirId, language='ar').get('tafasir', {}).get('soar', [])

    def listTafsirSurahs(self, cItem):
        names = self.getSurahNames()
        seen = []
        for item in self.tafsirItems(cItem.get('tafsir_id')):
            sid = item.get('sura_id')
            if sid not in seen:
                seen.append(sid)
        for sid in sorted(seen):
            params = dict(cItem)
            params.update({'category': 'list_tafsir', 'title': '%03d. %s' % (sid, names.get(sid, '')), 'sura_id': sid})
            self.addDir(params)

    def listTafsir(self, cItem):
        for item in self.tafsirItems(cItem.get('tafsir_id')):
            if item.get('sura_id') == cItem.get('sura_id') and item.get('url'):
                self.addAudio({'good_for_fav': True, 'title': item.get('name', ''), 'url': item['url']})

    def listTadaborSurahs(self, cItem):
        tadabor = self.api('tadabor').get('tadabor', {})
        names = self.getSurahNames()
        for sid in sorted(tadabor, key=lambda k: int(k) if str(k).isdigit() else 0):
            items = tadabor.get(sid) or []
            if not items:
                continue
            num = int(sid) if str(sid).isdigit() else 0
            params = dict(cItem)
            params.update({'category': 'list_tadabor', 'title': '%03d. %s' % (num, names.get(num, items[0].get('sora_name', ''))),
                           'sura_key': sid, 'icon': items[0].get('image_url', ''), 'desc': _('%d videos') % len(items)})
            self.addDir(params)

    def listTadabor(self, cItem):
        for item in self.api('tadabor').get('tadabor', {}).get(cItem.get('sura_key'), []) or []:
            url = item.get('video_url') or item.get('audio_url')
            if not url:
                continue
            title = item.get('title', '')
            if item.get('reciter_name'):
                title = '%s | %s' % (title, item['reciter_name'])
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': item.get('image_url', ''),
                      'desc': self.cleanHtmlStr(item.get('text', ''))}
            if item.get('video_url'):
                self.addVideo(params)
            else:
                self.addAudio(params)

    def listSearch(self, cItem, searchPattern, searchType):
        pattern = searchPattern.strip().lower()
        if not pattern:
            return
        # match the name in the chosen language, English and Arabic, so Latin
        # and Arabic input both work whatever the language setting is
        matched = set()
        for lang in (self.getLang(), 'eng', 'ar'):
            for reciter in self.getReciters(lang):
                if pattern in (reciter.get('name') or '').lower():
                    matched.add(reciter.get('id'))
        for reciter in self.getReciters():
            if reciter.get('id') in matched:
                self.addReciter(dict(cItem, name='category'), reciter)
        for radio in self.api('radios').get('radios', []):
            if pattern in (radio.get('name') or '').lower() and radio.get('url'):
                self.addAudio({'good_for_fav': True, 'title': (radio.get('name') or '').strip(), 'url': radio['url'],
                               'desc': _('Live radio'), 'live': True})

    def getLinksForVideo(self, cItem):
        printDBG('MP3Quran.getLinksForVideo [%s]' % cItem['url'])
        url = cItem['url']
        if not re.match(r'https?://', url):
            return []
        # tadabor files have Arabic file names
        # the radio servers (qurango.net) refuse non-browser User-Agents
        url = strwithmeta(self.cm.iriToUri(url), {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL})
        urlTab = [{'name': 'MP3Quran', 'url': url, 'need_resolve': 0}]
        if not cItem.get('live'):
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        return urlTab

    def getArticleContent(self, cItem):
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', ''),
                 'images': [{'title': '', 'url': cItem.get('icon') or self.DEFAULT_ICON_URL}], 'other_info': {}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('MP3Quran.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        self.currList = []

        if name is None:
            tab = [{'category': 'list_reciters', 'title': _('Reciters')},
                   {'category': 'list_radios', 'title': _('Radio')},
                   {'category': 'list_atheer_cats', 'title': _('Atheer radio (Arabic)')},
                   {'category': 'list_video_reciters', 'title': _('Video recitations')},
                   {'category': 'list_tadabor_surahs', 'title': _('Tadabor')},
                   {'category': 'list_tafasir', 'title': _('Tafsir (Arabic)')}]
            self.listsTab(tab, {'name': 'category'})
            self.addAudio({'good_for_fav': True, 'title': _('MP3Quran live radio'), 'url': self.LIVE_RADIO, 'desc': _('Live radio'), 'live': True})
            self.listsTab(self.searchItems(), {'name': 'category'})
        elif category == 'list_reciters':
            self.listReciters(self.currItem)
        elif category == 'list_moshaf':
            self.listMoshaf(self.currItem)
        elif category == 'list_surahs':
            self.listSurahs(self.currItem)
        elif category == 'list_radios':
            self.listRadios(self.currItem)
        elif category == 'list_atheer_cats':
            self.listAtheerCats(self.currItem)
        elif category == 'list_atheer':
            self.listAtheer(self.currItem)
        elif category == 'list_atheer_sub':
            self.listAtheerSub(self.currItem)
        elif category == 'list_video_reciters':
            self.listVideoReciters(self.currItem)
        elif category == 'list_videos':
            self.listVideos(self.currItem)
        elif category == 'list_tafasir':
            self.listTafasir(self.currItem)
        elif category == 'list_tafsir_surahs':
            self.listTafsirSurahs(self.currItem)
        elif category == 'list_tafsir':
            self.listTafsir(self.currItem)
        elif category == 'list_tadabor_surahs':
            self.listTadaborSurahs(self.currItem)
        elif category == 'list_tadabor':
            self.listTadabor(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearch(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MP3Quran(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('mp3quran')

    def withArticleContent(self, cItem):
        return cItem.get('type', '') in ('audio', 'video') and len(cItem.get('desc', '')) > 20
