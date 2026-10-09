# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 09.08.2025 - Lululla - fix for increase getThumbnailUrl2 - sport page show poster - events theatre added
# 08.10.2026 - catalogue from the current raiplay.it JSON (menu, pages, genres A-Z, programmes,
# seasons/sets with local paging), search (programmes + videos), live TV from dirette.json and
# radio from raiplaysound, replay from the JSON TV guide, TG1/TG2/TG3/TGR as programmes, Rai Sport
# archive (offset paging, videos only); INFO from the programme/video data (moviemeta for films),
# "Show - SxxExx" / "Title (Year)" / "(YYYY-MM-DD)" names, watched flag programme -> season ->
# episode, own url per video, subtitles, a message for geo-blocked and DRM videos, default user agent.
# 09.10.2026 - radio stations as audio rows (the player treated them as videos), INFO on them
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
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import re
import datetime
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://raiplay.it/'


# "... - Puntata del 31/05/2026", "Tg1 ore 20:00 del 07/10/2026", "TGR Lazio del 07/10/2026 ore 19:30"
DATE_RE = re.compile(r'\s*(?:-\s*)?(?:(?:puntata|edizione)\s+)?(?:del\s+)?\b(\d{1,2})/(\d{1,2})/(\d{4})\b', re.I)


class Raiplay(GenericFolderWatchedScraperMixin, CBaseHostClass):

    MAIN_URL = 'https://www.raiplay.it/'
    HOME_URL = MAIN_URL + 'index.json'
    MENU_URL = MAIN_URL + 'menu.json'
    CHANNELS_URL = MAIN_URL + 'dirette.json'
    EPG_URL = MAIN_URL + 'palinsesto/app/%s/%s.json'
    SEARCH_URL = MAIN_URL + 'atomatic/raiplay-search-service/api/v1/msearch'
    # template ids of the raiplay.it search web component (rai-search.js)
    SEARCH_TEMPLATE_IN = '6470a982e4e0301afe1f81f1'
    SEARCH_TEMPLATE_OUT = '6516ac5d40da6c377b151642'
    RADIO_MAIN_URL = 'https://www.raiplaysound.it'
    CHANNELS_RADIO_URL = RADIO_MAIN_URL + '/dirette.json'

    RAISPORT_DOMAIN = "RaiNews|Category-6dd7493b-f116-45de-af11-7d28a3f33dd2"
    RAISPORT_CATEGORIES_URL = "https://www.rainews.it/category/6dd7493b-f116-45de-af11-7d28a3f33dd2.json"
    RAISPORT_SEARCH_URL = "https://www.rainews.it/atomatic/news-search-service/api/v3/search"

    TGR_REGIONS = [('Abruzzo', 'abruzzo'), ('Basilicata', 'basilicata'), ('Calabria', 'calabria'), ('Campania', 'campania'),
                   ('Emilia Romagna', 'emiliaromagna'), ('Friuli Venezia Giulia', 'friuliveneziagiulia'), ('Lazio', 'lazio'),
                   ('Liguria', 'liguria'), ('Lombardia', 'lombardia'), ('Marche', 'marche'), ('Molise', 'molise'),
                   ('Piemonte', 'piemonte'), ('Puglia', 'puglia'), ('Sardegna', 'sardegna'), ('Sicilia', 'sicilia'),
                   ('Toscana', 'toscana'), ('Trentino Alto Adige - Bolzano', 'trentinoaltoadigebolzano'),
                   ('Trentino Alto Adige - Trento', 'trentinoaltoadigetrento'), ('Umbria', 'umbria'),
                   ("Valle d'Aosta", 'valledaosta'), ('Veneto', 'veneto')]

    # blocks of a page that carry a list of contents (hero / sidekick / marketing / recommendation
    # blocks are teasers of rows listed elsewhere or need a login)
    LIST_BLOCKS = ('RaiPlay Slider Block', 'RaiPlay Slider Chart Block', 'RaiPlay Slider Video Block', 'RaiPlay Slider Generi Block')
    PROGRAM_TYPES = ('RaiPlay Programma Item', 'RaiPlay Programma Stagione Item')
    PAGE_TYPES = ('RaiPlay Raccolta Item', 'RaiPlay Genere Item', 'RaiPlay Tipologia Item')
    WF_FOLDER_CATEGORIES = ('rp_page', 'rp_block', 'rp_letter', 'rp_program', 'rp_set')

    PAGE_SIZE = 50
    SEARCH_PAGE_SIZE = 50
    SPORT_PAGE_SIZE = 50
    INFO_TWINS = {'directors': 'director', 'cast': 'actors', 'genres': 'genre'}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'raiplay', 'cookie': 'raiplay.it.cookie'})
        self.DEFAULT_ICON_URL = "https://img.tuttoandroid.net/wp-content/uploads/2019/10/Raiplay-logo.jpg"
        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'application/json, text/plain, */*'}
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.RaiSportKeys = []
        self.watchedHelper = IPTVWatchedHelper('raiplay')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            if cItem.get('type') == 'video':
                url = self.wfNormalizeUrlKey(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if cItem.get('search_item') or cItem.get('category', '') not in self.WF_FOLDER_CATEGORIES:
                return ''
            url = self.wfNormalizeUrlKey(cItem.get('url', ''))
            if not url:
                return ''
            sub = cItem.get('block_id') or cItem.get('letter') or ''
            return 'folder:%s#%s' % (url, sub) if sub else 'folder:%s' % url
        except Exception:
            printExc()
        return ''

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        params = dict(self.defaultParams)
        if addParams:
            params.update(addParams)
        return self.cm.getPage(url, params, post_data)

    def _json(self, url, post=None, header=None):
        params = {}
        if header:
            params['header'] = header
        if post is not None:
            params['raw_post_data'] = True
        sts, data = self.getPage(url, params, post)
        if not sts or not data:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    def _clean(self, value):
        if value is None or isinstance(value, (dict, list, bool)):
            return ''
        if isinstance(value, (int, float)):
            value = str(value)
        return self.cleanHtmlStr(value)

    @staticmethod
    def _num(value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    def _full(self, path, base=''):
        path = str(path or '').strip().replace(' ', '%20')
        if not path:
            return ''
        if '://' in path:
            return path
        if path.startswith('//'):
            return 'https:' + path
        if path.startswith('/raiplay/'):
            path = path[len('/raiplay'):]
        return (base or self.MAIN_URL.rstrip('/')) + ('' if path.startswith('/') else '/') + path

    def _imgUrl(self, path, size='400x-', base=''):
        # raiplay.it scales its jpg covers on the fly (resizegd) - the originals are up to 1 MB
        path = str(path or '').strip().replace('[RESOLUTION]', size).replace(' ', '%20')
        if not path or '[an error occurred' in path:
            return ''
        if '://' in path:
            return path
        if not path.startswith('/'):
            path = '/' + path
        if not base and size and re.search(r'\.jpe?g$', path, re.I):
            return '%sresizegd/%s%s' % (self.MAIN_URL, size, path)
        return (base or self.MAIN_URL.rstrip('/')) + path

    def _img(self, item, size='400x-', keys=('landscape', 'landscape43', 'portrait', 'portrait43', 'square', 'portrait_logo')):
        images = item.get('images')
        if isinstance(images, dict):
            for key in keys:
                if images.get(key):
                    return self._imgUrl(images[key], size)
        for key in ('image', 'immagine', 'transparent_icon', 'transparent-icon'):
            if item.get(key):
                return self._imgUrl(item[key], size)
        return ''

    @staticmethod
    def _isoDate(value):
        # "18-09-2020" / "06/10/2026" / "2026-10-07T11:45:00+0000" -> "YYYY-MM-DD"
        value = str(value or '').strip()
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', value)
        if m:
            return m.group(0)
        m = re.match(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', value)
        if m:
            return '%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1)))
        return ''

    def _mediaTitle(self, name, show='', epTitle='', season='', episode='', date='', year='', isFilm=False):
        # "Show - SxxExx - Episode" for numbered episodes, "Title (Year)" for films, "Title (YYYY-MM-DD)"
        # for dated rows - only with media naming normalisation on, the site's label otherwise
        if not IsMediaNamingNormalized():
            return name
        season, episode = self._num(season), self._num(episode)
        # programmes number their "seasons" by year (2026) or as "2024/25": those get the date instead
        if season and episode and season < 1900 and show:
            title = '%s - S%02dE%02d' % (show, season, episode)
            if epTitle and epTitle.lower() != show.lower():
                title += ' - ' + epTitle
            return title
        if isFilm:
            return normalizeMediathekTitle(name, year=year, isMovie=True)
        m = DATE_RE.search(name)
        if m:
            # "TGR Lazio del 07/10/2026 ore 19:30" -> "TGR Lazio ore 19:30 (2026-10-07)"
            base = re.sub(r'\s{2,}', ' ', '%s %s' % (name[:m.start()], name[m.end():])).strip(' -') or name
            return normalizeMediathekTitle(base, date='%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1))))
        if date:
            return normalizeMediathekTitle(name, date=date)
        return name

    @staticmethod
    def _letterKey(key):
        return (not key[:1].isalpha(), key)

    ###################################################
    # main menu
    ###################################################
    def listMainMenu(self, cItem):
        tab = [{'category': 'live_tv', 'title': _('Live channels')},
               {'category': 'live_radio', 'title': _('Radio stations')},
               {'category': 'replay', 'title': _('Replay')},
               {'category': 'rp_page', 'title': _('Home page'), 'url': self.HOME_URL},
               {'category': 'catalogue', 'title': _('Categories')},
               {'category': 'tg', 'title': _('News')},
               {'category': 'raisport_main', 'title': _('Sport')}] + self.searchItems()
        for item in tab:
            item.setdefault('icon', self.DEFAULT_ICON_URL)
        self.listsTab(tab, cItem)

    ###################################################
    # live
    ###################################################
    def _channels(self):
        return [ch for ch in (self._json(self.CHANNELS_URL).get('contents') or []) if isinstance(ch, dict) and ch.get('channel')]

    def listLiveTvChannels(self, cItem):
        printDBG("Raiplay.listLiveTvChannels")
        for ch in self._channels():
            relinker = (ch.get('video') or {}).get('content_url') or ''
            if not relinker:
                continue
            self.addVideo({'name': 'category', 'category': 'rp_live', 'title': self._clean(ch['channel']), 'url': relinker, 'live': True,
                           'icon': self._img(ch, keys=()), 'desc': self._clean(ch.get('description')), 'good_for_fav': True})

    def listLiveRadioChannels(self, cItem):
        printDBG("Raiplay.listLiveRadioChannels")
        for st in (self._json(self.CHANNELS_RADIO_URL).get('contents') or []):
            if not isinstance(st, dict):
                continue
            audio = st.get('audio') or {}
            url = audio.get('url') or ''
            title = self._clean(st.get('title') or audio.get('title'))
            if not url or not title:
                continue
            icon = self._imgUrl(st.get('image') or audio.get('poster') or (st.get('channel') or {}).get('logo'), '', self.RADIO_MAIN_URL)
            # an audio row: the player treats it as radio (audio screensaver, no picture expected)
            self.addAudio({'name': 'category', 'category': 'rp_live', 'title': title, 'url': url, 'live': True, 'radio': True,
                           'icon': icon, 'desc': '%s: %s' % (_('Live radio'), title), 'good_for_fav': True})

    ###################################################
    # replay (TV guide)
    ###################################################
    def listReplayDate(self, cItem):
        today = datetime.date.today()
        for n in range(8):
            day = today - datetime.timedelta(days=n)
            self.addDir({'name': 'category', 'category': 'replay_date', 'title': day.strftime('%Y-%m-%d'),
                         'epg_date': day.strftime('%d-%m-%Y'), 'icon': self.DEFAULT_ICON_URL})

    def listReplayChannels(self, cItem):
        for ch in self._channels():
            chId = ch.get('absolute_path') or ''
            if not chId:
                continue
            self.addDir({'name': 'category', 'category': 'replay_channel', 'title': self._clean(ch['channel']), 'channel_id': chId,
                         'epg_date': cItem.get('epg_date', ''), 'icon': self._img(ch, keys=())})

    def listEPG(self, cItem):
        epgDate = cItem.get('epg_date', '')
        data = self._json(self.EPG_URL % (cItem.get('channel_id', ''), epgDate))
        isoDate = self._isoDate(epgDate)
        seen = set()
        for ev in (data.get('events') or []):
            if not isinstance(ev, dict) or not ev.get('has_video') or not ev.get('path_id'):
                continue
            name = self._clean(ev.get('name'))
            # a programme split by the news (UnoMattina 1st/2nd part) points to the same video twice
            if not name or ev['path_id'] in seen:
                continue
            seen.add(ev['path_id'])
            hour = self._clean(ev.get('hour'))
            label = '%s %s' % (hour, name) if hour else name
            if IsMediaNamingNormalized():
                # a repeat carries its first air date in the name - the guide's day is the one that counts here
                label = re.sub(r'\s{2,}', ' ', DATE_RE.sub(' ', label)).strip(' -') or label
            descTab = [x for x in (self._clean(ev.get('duration_in_minutes')), self._clean(ev.get('description'))) if x]
            self.addVideo({'name': 'category', 'category': 'rp_video', 'url': self._full(ev['path_id']),
                           'title': self._mediaTitle(label, date=isoDate), 'icon': self._imgUrl(ev.get('image')),
                           'desc': '[/br]'.join(descTab), 'good_for_fav': True})

    ###################################################
    # catalogue / pages
    ###################################################
    def listCatalogue(self, cItem):
        data = self._json(self.MENU_URL)
        for menu in (data.get('menu') or []):
            if not isinstance(menu, dict) or menu.get('menu_type') != 'Catalogo':
                continue
            for el in (menu.get('elements') or []):
                path = (el or {}).get('path_id') or ''
                title = self._clean((el or {}).get('name'))
                if path and title:
                    self.addDir({'name': 'category', 'category': 'rp_page', 'title': title, 'url': self._full(path),
                                 'icon': self._imgUrl(el.get('image_background')) or self.DEFAULT_ICON_URL, 'good_for_fav': True})

    def listTg(self, cItem):
        for title, slug in (('Tg1', 'tg1'), ('Tg2', 'tg2'), ('Tg3', 'tg3')):
            self.addDir({'name': 'category', 'category': 'rp_program', 'title': title,
                         'url': self._full('/programmi/%s.json' % slug), 'icon': self.DEFAULT_ICON_URL, 'good_for_fav': True})
        self.addDir({'name': 'category', 'category': 'tgr', 'title': 'TGR', 'icon': self.DEFAULT_ICON_URL})

    def listTgr(self, cItem):
        for title, slug in self.TGR_REGIONS:
            self.addDir({'name': 'category', 'category': 'rp_program', 'title': 'TGR - %s' % title,
                         'url': self._full('/programmi/tgr-%s.json' % slug), 'icon': self.DEFAULT_ICON_URL, 'good_for_fav': True})

    def _blockItems(self, block):
        return [it for it in (block.get('contents') or []) if isinstance(it, dict) and self._itemKind(it)]

    def listPage(self, cItem):
        printDBG("Raiplay.listPage [%s]" % cItem.get('url', ''))
        data = self._json(cItem.get('url', ''))
        if not data:
            return
        contents = data.get('contents')
        if isinstance(contents, dict):
            self._listLetters(cItem, contents)
            return
        if not contents and data.get('blocks'):
            self.listProgram(cItem, data)
            return
        blocks = [b for b in (contents or []) if isinstance(b, dict) and b.get('type') in self.LIST_BLOCKS and self._blockItems(b)]
        if len(blocks) == 1:
            self._addItemsPaged(cItem, self._blockItems(blocks[0]))
            return
        # the genres (= the whole catalogue of the page, A-Z) first, then the editorial rows
        for b in blocks:
            if b.get('type') == 'RaiPlay Slider Generi Block':
                for it in self._blockItems(b):
                    self._addContentItem(cItem, it)
        for b in blocks:
            if b.get('type') == 'RaiPlay Slider Generi Block':
                continue
            items = self._blockItems(b)
            title = self._clean(b.get('name') or (b.get('header') or {}).get('label'))
            if not title or not b.get('id'):
                continue
            self.addDir({'name': 'category', 'category': 'rp_block', 'title': title, 'url': cItem['url'], 'block_id': b['id'],
                         'icon': self._img(items[0]) if items else '', 'desc': '%d %s' % (len(items), _('Videos') if b.get('type') == 'RaiPlay Slider Video Block' else _('Programmes')),
                         'good_for_fav': True})

    def listBlock(self, cItem):
        data = self._json(cItem.get('url', ''))
        for b in (data.get('contents') or []):
            if isinstance(b, dict) and b.get('id') == cItem.get('block_id'):
                self._addItemsPaged(cItem, self._blockItems(b))
                break

    def _listLetters(self, cItem, contents):
        letters = sorted([k for k, v in contents.items() if isinstance(v, list) and v], key=self._letterKey)
        total = sum(len(contents[k]) for k in letters)
        if total <= 2 * self.PAGE_SIZE:
            for k in letters:
                for it in contents[k]:
                    if isinstance(it, dict) and self._itemKind(it):
                        self._addContentItem(cItem, it)
            return
        for k in letters:
            self.addDir({'name': 'category', 'category': 'rp_letter', 'title': '%s (%d)' % (k, len(contents[k])), 'url': cItem['url'],
                         'letter': k, 'icon': cItem.get('icon', ''), 'good_for_fav': True})

    def listLetter(self, cItem):
        contents = self._json(cItem.get('url', '')).get('contents')
        if isinstance(contents, dict):
            items = [it for it in (contents.get(cItem.get('letter', '')) or []) if isinstance(it, dict) and self._itemKind(it)]
            self._addItemsPaged(cItem, items)

    def _addItemsPaged(self, cItem, items):
        page = max(1, self._num(cItem.get('page', 1)) or 1)
        lastPage = (len(items) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        for it in items[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]:
            self._addContentItem(cItem, it)
        if lastPage > 1:
            # the whole list comes in one answer: the page lives in cItem['page'], the url stays ("Jump" template)
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get('url', '').replace('{', '%7B').replace('}', '%7D'))

    def _itemKind(self, it):
        itemType = it.get('type') or ''
        path = it.get('path_id') or ''
        if not path or not (it.get('name') or it.get('title') or it.get('titolo')):
            return ''
        path = re.sub(r'^https?://[^/]+', '', path)
        if itemType == 'RaiPlay Video Item' or path.startswith('/video/'):
            return 'video'
        if itemType in self.PAGE_TYPES or re.match(r'/(?:collezioni|genere|tipologia)/', path):
            return 'page'
        if itemType in self.PROGRAM_TYPES or path.startswith('/programmi/'):
            return 'program'
        return ''

    def _addContentItem(self, cItem, it):
        try:
            kind = self._itemKind(it)
            if kind == 'video':
                self._addVideoItem(cItem, it)
                return
            if not kind:
                return
            title = self._clean(it.get('name') or it.get('title') or it.get('titolo'))
            descTab = []
            year = self._clean(it.get('year'))
            if year:
                descTab.append(year)
            for key in ('vanity', 'description', 'sommario'):
                if it.get(key):
                    descTab.append(self._clean(it[key]))
                    break
            self.addDir({'name': 'category', 'category': 'rp_program' if kind == 'program' else 'rp_page', 'title': title,
                         'url': self._full(it['path_id']), 'icon': self._img(it), 'desc': '[/br]'.join(descTab), 'good_for_fav': True})
        except Exception:
            printExc()

    def _addVideoItem(self, cItem, it):
        name = self._clean(it.get('name') or it.get('title') or it.get('titolo'))
        show = self._clean(it.get('program_name') or it.get('programma') or cItem.get('prog_name'))
        epTitle = self._clean(it.get('episode_title') or it.get('toptitle') or it.get('titolo'))
        season = it.get('season') or it.get('stagione') or ''
        episode = it.get('episode') or it.get('episodio') or ''
        # the full film of a film programme (not its trailer / extras)
        isFilm = bool(cItem.get('prog_film')) and (it.get('forma') or '') == 'Integrale' and not self._num(episode)
        if it.get('titolo') and show and not (self._num(season) and self._num(episode)):
            # "Ulisse - La Sicilia di Montalbano" + "La Sicilia di Montalbano": the show alone, no doubled name
            if name.lower() in show.lower():
                name = show
            elif show.lower() not in name.lower():
                name = '%s - %s' % (show, name)
        title = self._mediaTitle(name, show, epTitle, season, episode, year=cItem.get('prog_year', ''), isFilm=isFilm)
        descTab = []
        duration = self._clean(it.get('duration_in_minutes') or it.get('duration') or it.get('durata'))
        if duration:
            descTab.append('%s: %s' % (_('Duration'), duration))
        if it.get('subtitle'):
            descTab.append(self._clean(it['subtitle']))
        for key in ('description', 'vanity', 'sommario'):
            if it.get(key):
                descTab.append(self._clean(it[key]))
                break
        self.addVideo({'name': 'category', 'category': 'rp_video', 'title': title, 'url': self._full(it['path_id']),
                       'icon': self._img(it), 'desc': '[/br]'.join(descTab), 'good_for_fav': True})

    ###################################################
    # programme -> sets (seasons) -> videos
    ###################################################
    def listProgram(self, cItem, data=None):
        printDBG("Raiplay.listProgram [%s]" % cItem.get('url', ''))
        if data is None:
            data = self._json(cItem.get('url', ''))
        if not data:
            return
        prog = data.get('program_info') or {}
        ctx = {'prog_name': self._clean(prog.get('name') or data.get('name')), 'prog_year': self._clean(prog.get('year'))[:4],
               'prog_film': (prog.get('typology') or '') == 'Film'}
        icon = self._img(prog) or cItem.get('icon', '')
        sets = []
        for block in (data.get('blocks') or []):
            for st in ((block or {}).get('sets') or []):
                if isinstance(st, dict) and st.get('path_id'):
                    sets.append((self._clean(block.get('name')), st))
        if len(sets) == 1:
            listItem = dict(cItem, category='rp_set', url=self._full(sets[0][1]['path_id']), **ctx)
            listItem.pop('page', None)
            self.listSet(listItem)
            return
        if not sets and data.get('first_item_path'):
            self._addVideoItem(dict(cItem, **ctx), {'name': ctx['prog_name'] or cItem.get('title', ''), 'path_id': data['first_item_path'],
                                                    'forma': 'Integrale', 'images': prog.get('images') or {},
                                                    'duration': data.get('first_item_duration') or '', 'description': prog.get('description') or ''})
            return
        multiBlock = len({b for b, _st in sets}) > 1
        for blockName, st in sets:
            setName = self._clean(st.get('name'))
            title = setName or blockName
            if multiBlock and blockName and setName and blockName.lower() != setName.lower() and blockName.lower() not in setName.lower():
                title = '%s - %s' % (blockName, setName)
            params = {'name': 'category', 'category': 'rp_set', 'title': title, 'url': self._full(st['path_id']), 'icon': icon,
                      'desc': self._clean((st.get('episode_size') or {}).get('label')), 'good_for_fav': True}
            params.update(ctx)
            self.addDir(params)

    def listSet(self, cItem):
        printDBG("Raiplay.listSet [%s]" % cItem.get('url', ''))
        data = self._json(cItem.get('url', ''))
        items = [it for it in (data.get('items') or []) if isinstance(it, dict) and it.get('path_id')]
        self._addItemsPaged(cItem, items)

    ###################################################
    # search
    ###################################################
    def _search(self, pattern, start, size, videos):
        params = {'param': pattern.strip(), 'from': start, 'sort': 'relevance', 'size': size if videos else 1,
                  'additionalSize': size, 'onlyVideoQuery': bool(videos), 'onlyProgramsQuery': not videos}
        body = json_dumps({'templateIn': self.SEARCH_TEMPLATE_IN, 'templateOut': self.SEARCH_TEMPLATE_OUT, 'params': params})
        header = dict(self.HTTP_HEADER, **{'Content-Type': 'application/json', 'Origin': self.MAIN_URL.rstrip('/'), 'Referer': self.MAIN_URL + 'ricerca.html'})
        return self._json(self.SEARCH_URL, body, header).get('agg') or {}

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Raiplay.listSearchResult [%s]" % searchPattern)
        if not (searchPattern or '').strip():
            return
        cItem = dict(cItem, search_pattern=searchPattern)
        page = max(1,self._num(cItem.get('page', 1)) or 1)
        agg = self._search(searchPattern, (page - 1) * self.SEARCH_PAGE_SIZE, self.SEARCH_PAGE_SIZE, False)
        if page == 1:
            videoTotal = self._num((self._search(searchPattern, 0, 1, True).get('video') or {}).get('totale'))
            if videoTotal:
                self.addDir({'name': 'category', 'category': 'search_videos', 'title': '%s (%d)' % (_('Videos'), videoTotal),
                             'search_pattern': searchPattern, 'icon': self.DEFAULT_ICON_URL})
        titles = agg.get('titoli') or {}
        for card in (titles.get('cards') or []):
            if isinstance(card, dict) and card.get('path_id'):
                self._addContentItem(cItem, dict(card, name=card.get('titolo') or ''))
        total = self._num(titles.get('totale'))
        lastPage = (total + self.SEARCH_PAGE_SIZE - 1) // self.SEARCH_PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage)

    def listSearchVideos(self, cItem):
        pattern = cItem.get('search_pattern', '')
        page = max(1, self._num(cItem.get('page', 1)) or 1)
        video = self._search(pattern, (page - 1) * self.SEARCH_PAGE_SIZE, self.SEARCH_PAGE_SIZE, True).get('video') or {}
        for card in (video.get('cards') or []):
            if isinstance(card, dict) and card.get('path_id'):
                self._addVideoItem(cItem, card)
        total = self._num(video.get('totale'))
        lastPage = (total + self.SEARCH_PAGE_SIZE - 1) // self.SEARCH_PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage)

    ###################################################
    # Rai Sport archive (rainews.it)
    ###################################################
    def fillRaiSportKeys(self):
        self.RaiSportKeys = []
        data = self._json(self.RAISPORT_CATEGORIES_URL)
        for c in (data.get('children') or []):
            name = self._clean((c or {}).get('name'))
            code = (c or {}).get('uniqueName') or ''
            if not name or not code:
                continue
            subKeys = []
            for c2 in (c.get('children') or []):
                subName = self._clean((c2 or {}).get('name'))
                subCode = (c2 or {}).get('uniqueName') or ''
                if subName and subCode:
                    subKeys.append({'title': subName, 'key': '%s|%s' % (subName, subCode)})
            self.RaiSportKeys.append({'title': name, 'key': '%s|%s' % (name, code), 'sub_keys': subKeys})

    def listRaiSportMain(self, cItem):
        if not self.RaiSportKeys:
            self.fillRaiSportKeys()
        for k in self.RaiSportKeys:
            self.addDir({'name': 'category', 'category': 'raisport_item', 'title': k['title'], 'key': k['key'],
                         'sub_keys': k['sub_keys'], 'icon': self.DEFAULT_ICON_URL})

    def listRaiSportItems(self, cItem):
        tab = [{'title': _('All videos'), 'key': cItem.get('key', '')}] + list(cItem.get('sub_keys') or [])
        for k in tab:
            # the url only names the list (favourite identity / "Jump" template), the videos come from a POST
            self.addDir({'name': 'category', 'category': 'raisport_subitem', 'title': k['title'], 'key': k['key'],
                         'url': 'https://www.rainews.it/sport#%s' % k['key'].split('|')[-1], 'icon': self.DEFAULT_ICON_URL,
                         'good_for_fav': True})

    def listRaiSportVideos(self, cItem):
        printDBG("Raiplay.listRaiSportVideos %s" % cItem.get('title', ''))
        page = max(1, self._num(cItem.get('page', 1)) or 1)
        header = dict(self.HTTP_HEADER, **{'Content-Type': 'application/json; charset=UTF-8', 'Origin': 'https://www.rainews.it',
                                           'Referer': 'https://www.rainews.it/sport', 'X-Requested-With': 'XMLHttpRequest'})
        # "page" is the offset of the first hit (rainews-archive.js), post_filters keeps only the videos
        payload = {'page': (page - 1) * self.SPORT_PAGE_SIZE, 'pageSize': self.SPORT_PAGE_SIZE, 'mode': 'archive', 'param': None,
                   'filters': {'tematica': [cItem.get('key', '')], 'dominio': self.RAISPORT_DOMAIN}, 'post_filters': {'tipo': 'video'}}
        data = self._json(self.RAISPORT_SEARCH_URL, json_dumps(payload), header)
        for video in (data.get('hits') or []):
            if not isinstance(video, dict) or video.get('data_type') != 'video':
                continue
            media = video.get('media') or {}
            relinker = media.get('mediapolis') or ''
            title = self._clean(video.get('title'))
            if not relinker or not title:
                continue
            date = self._isoDate(video.get('publication_date') or video.get('create_date'))
            duration = self._clean(media.get('durata'))
            descTab = [x for x in (date, duration, self._clean(video.get('summary'))) if x]
            # the relinker url has no page of its own to read the INFO from: date / duration go with the row
            self.addVideo({'name': 'category', 'category': 'rp_video', 'title': self._mediaTitle(title, date=date), 'url': relinker,
                           'icon': self._img(video), 'desc': '[/br]'.join(descTab), 'air_date': date, 'duration': duration,
                           'good_for_fav': True})
        total = self._num(data.get('total'))
        lastPage = (total + self.SPORT_PAGE_SIZE - 1) // self.SPORT_PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get('url', ''))

    ###################################################
    # links
    ###################################################
    def _relinker(self, url):
        # output=56: the stream as XML (url, type, DRM licence); outside Italy a geo-protected
        # stream answers with ".../video_no_available.mp4"
        url = re.sub(r'^http://(mediapolis)', r'https://\1', url.strip())
        base = re.sub(r'([?&])output=[^&]*&?', r'\1', url).rstrip('?&')
        if '?' not in base and '&' in base:
            base = base.replace('&', '?', 1)
        sts, data = self.getPage(base + ('&' if '?' in base else '?') + 'output=56')
        if not sts or not data or '<Mediapolis' not in data:
            return {}
        streamUrl = re.search(r'<url type="content">\s*(?:<!\[CDATA\[)?\s*([^\]<\s]*)', data)
        ct = re.search(r'<ct>([^<]*)</ct>', data)
        drm = False
        lic = re.search(r'<license_url>\s*<!\[CDATA\[(.*?)\]\]>', data, re.S)
        if lic and lic.group(1).strip() not in ('', '{}'):
            try:
                drm = bool((json_loads(lic.group(1)) or {}).get('drmLicenseUrlValues'))
            except Exception:
                drm = True
        return {'url': streamUrl.group(1) if streamUrl else '', 'ct': (ct.group(1) if ct else '').strip().lower(), 'drm': drm}

    def getLinksForVideo(self, cItem):
        printDBG("Raiplay.getLinksForVideo [%s]" % cItem.get('url', ''))
        url = cItem.get('url', '')
        live = bool(cItem.get('live'))
        relinker, synopsis, subTracks = '', '', []
        if '/relinker/' in url:
            relinker = url
        elif url.endswith('.json'):
            data = self._json(url)
            video = data.get('video') or {}
            relinker = video.get('content_url') or ''
            synopsis = self._clean(data.get('description'))
            for sub in (video.get('subtitlesArray') or video.get('subtitleList') or []):
                subUrl = (sub or {}).get('url') or ''
                if subUrl:
                    lang = (sub.get('language') or 'it').lower()
                    subTracks.append({'title': self._clean(sub.get('label')) or lang, 'url': self._full(subUrl), 'lang': lang,
                                      'format': 'vtt' if subUrl.lower().endswith('.vtt') else 'srt'})
        if not relinker:
            return []
        res = self._relinker(relinker)
        streamUrl = res.get('url', '')
        if not streamUrl:
            return []
        if 'video_no_available' in streamUrl:
            if live:
                SetIPTVPlayerLastHostError(_('This channel is not available in your country (geo-blocking).'))
            else:
                SetIPTVPlayerLastHostError(_('Not available in your country (geo-blocking).'))
            return []
        if res.get('drm'):
            SetIPTVPlayerLastHostError(_('Video with DRM protection.'))
            return []

        meta = {'User-Agent': self.USER_AGENT, 'iptv_livestream': live}
        if subTracks:
            meta['external_sub_tracks'] = subTracks
        ct = res.get('ct', '')
        urlTab = []
        if 'm3u8' in ct or 'hls' in ct or '.m3u8' in streamUrl:
            meta['iptv_proto'] = 'm3u8'
            master = strwithmeta(streamUrl, meta)
            if live:
                urlTab.append({'name': 'auto', 'url': master, 'need_resolve': 0})
            for item in getDirectM3U8Playlist(master, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999):
                # audio-only variants have no resolution: " 320k"
                item['name'] = str(item.get('name', '')).strip() or 'hls'
                item['need_resolve'] = 0
                urlTab.append(item)
            if not urlTab:
                urlTab.append({'name': 'hls', 'url': master, 'need_resolve': 0})
        else:
            name = 'mpd' if ('mpd' in ct or '.mpd' in streamUrl) else (ct or 'mp4')
            urlTab.append({'name': name, 'url': strwithmeta(streamUrl, meta), 'need_resolve': 0})
        if not live:
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))
        return urlTab

    ###################################################
    # INFO
    ###################################################
    def _programInfo(self, prog, info):
        year = self._clean(prog.get('year'))[:4]
        if year.isdigit():
            info['year'] = year
        for src, dst in (('direction', 'director'), ('actors', 'actors'), ('country', 'country'), ('channel', 'station')):
            value = self._clean(prog.get(src))
            if value:
                info.setdefault(dst, value)
        genres = [self._clean((g or {}).get('name')) for g in (prog.get('genres') or []) if isinstance(g, dict)]
        genres = [g for g in genres if g]
        if genres:
            info['genre'] = ', '.join(genres)
        if self._num(prog.get('seasons_number')):
            info['seasons'] = str(self._num(prog['seasons_number']))
        return year

    def getArticleContent(self, cItem):
        printDBG("Raiplay.getArticleContent [%s]" % cItem.get('url', ''))
        text, icon, info = cItem.get('desc', ''), cItem.get('icon', ''), {}
        url = cItem.get('url', '')
        isVideo = cItem.get('type') == 'video'
        meta = {}
        if cItem.get('air_date'):
            info['broadcast'] = cItem['air_date']
        if cItem.get('duration'):
            info['duration'] = cItem['duration']
        if url.endswith('.json') and (isVideo or cItem.get('category') == 'rp_program'):
            data = self._json(url)
            prog = data.get('program_info') or {}
            if isVideo and data:
                text = self._clean(data.get('description')) or self._clean(prog.get('description') or prog.get('vanity')) or text
                video = data.get('video') or {}
                if video.get('duration'):
                    info['duration'] = self._clean(video['duration'])
                # the air date is in the name ("... - Puntata del 04/10/2026"), date_published is when it went online
                m = DATE_RE.search(self._clean(data.get('name')))
                bcast = '%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1))) if m else self._isoDate(data.get('date_published'))
                if bcast:
                    info['broadcast'] = bcast
                avail = data.get('availabilities') or {}
                end = self._isoDate(avail.get('expiration_date_iso') or avail.get('expiration_date')) if isinstance(avail, dict) else ''
                if end:
                    info['remaining'] = _('available until %s') % end
                if data.get('channel'):
                    info['station'] = self._clean(data['channel'])
                if video.get('subtitlesArray') or video.get('subtitleList'):
                    info['subtitles'] = ', '.join([self._clean((s or {}).get('label')) for s in (video.get('subtitlesArray') or video.get('subtitleList')) if (s or {}).get('label')])
                icon = self._img(data, '600x-') or icon
            elif prog:
                text = self._clean(prog.get('description') or prog.get('vanity')) or text
                icon = self._img(prog, '600x-', ('portrait43', 'portrait', 'landscape', 'landscape43')) or icon
            year = self._programInfo(prog, info) if prog else ''
            # moviemeta only for real films: the full film (not an episode, clip or trailer) of a "Film" programme
            isFilm = (prog.get('typology') or '') == 'Film' and (not isVideo or (data.get('form') or '') == 'Integrale')
            if isFilm and prog.get('name'):
                try:
                    meta = getMeta('movie', self._clean(prog['name']), year, maxYearDiff=1)
                except Exception:
                    printExc()
        # the site's Italian texts first, the service adds ratings, poster and missing fields
        for key, value in (meta.get('info') or {}).items():
            if key not in info and self.INFO_TWINS.get(key, '') not in info:
                info[key] = value
        text = text or meta.get('plot', '')
        icon = meta.get('poster') or icon
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Raiplay.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        self.informAboutGeoBlockingIfNeeded('IT')

        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        printDBG("Raiplay.handleService: name[%s] category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'live_tv':
            self.listLiveTvChannels(self.currItem)
        elif category == 'live_radio':
            self.listLiveRadioChannels(self.currItem)
        elif category == 'replay':
            self.listReplayDate(self.currItem)
        elif category == 'replay_date':
            self.listReplayChannels(self.currItem)
        elif category == 'replay_channel':
            self.listEPG(self.currItem)
        elif category == 'catalogue':
            self.listCatalogue(self.currItem)
        elif category == 'rp_page':
            self.listPage(self.currItem)
        elif category == 'rp_block':
            self.listBlock(self.currItem)
        elif category == 'rp_letter':
            self.listLetter(self.currItem)
        elif category == 'rp_program':
            self.listProgram(self.currItem)
        elif category == 'rp_set':
            self.listSet(self.currItem)
        elif category == 'tg':
            self.listTg(self.currItem)
        elif category == 'tgr':
            self.listTgr(self.currItem)
        elif category == 'raisport_main':
            self.listRaiSportMain(self.currItem)
        elif category == 'raisport_item':
            self.listRaiSportItems(self.currItem)
        elif category == 'raisport_subitem':
            self.listRaiSportVideos(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_videos':
            self.listSearchVideos(self.currItem)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Raiplay(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('raiplay')

    def withArticleContent(self, cItem):
        return cItem.get('type') in ('video', 'audio') or cItem.get('category') == 'rp_program'
