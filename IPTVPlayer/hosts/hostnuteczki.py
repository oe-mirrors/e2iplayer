# -*- coding: utf-8 -*-
# Last Modified: 02.07.2026 damagic
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import json
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# E2 GUI COMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.nuteczki_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.nuteczki_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    """Zwraca listę opcji konfiguracyjnych dla hosta."""
    option_list = []
    option_list.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.nuteczki_login))
    option_list.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.nuteczki_password))
    return option_list


def gettytul():
    """Zwraca tytuł hosta."""
    return 'https://nuteczki.eu/'


class NuteczkiEU(CBaseHostClass):
    """
    Klasa obsługująca host nuteczki.eu.
    """

    # Stałe dla znaczników HTML
    HTML_DIV_END = '</div'
    HTML_SELECT = '<select'
    HTML_SELECT_END = '</select>'
    HTML_OPTION = '<option'
    HTML_OPTION_END = '</option>'
    HTML_IFRAME = '<iframe'
    HTML_IFRAME_END = '</iframe>'
    HTML_SCRIPT = '<script'
    HTML_SCRIPT_END = '</script>'
    HTML_SPAN_END = '</span'
    HTML_FORM_END = '</form>'

    # Stałe dla wzorców URL - bezpieczne, bez backtrackingu
    PATTERN_AUDIO_EXT = r'https?://[^"\']+\.(?:mp3|m4a|ogg|wav)'
    PATTERN_JSON_KEY = r'"(?:m4a|mp3|file)"\s*:\s*"([^"]+)"'
    # Bezpieczny wzorzec dla krakenfiles - używa [^"]* zamiast .*?
    PATTERN_KRAKENFILES = r'<a[^>]*href="([^"]*krakenfiles[^"]*)"'

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'nuteczki.eu', 'cookie': 'nuteczki.eu.cookie'})

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.HEADER = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })

        self.MAIN_URL = 'https://nuteczki.eu/'
        self.DEFAULT_ICON_URL = (
            'https://i.pinimg.com/736x/2d/07/83/'
            '2d0783d156a48860691667dadd8de458--note-music-music-wallpaper.jpg'
        )

        self.default_params = {
            'header': self.HEADER,
            'use_cookie': True,
            'load_cookie': True,
            'save_cookie': True,
            'cookiefile': self.COOKIE_FILE
        }
        self.cache_filters = {}
        self.cache_filters_keys = []

        self.logged_in = None
        self.login = ''
        self.password = ''

    def getPage(self, base_url, add_params=None, post_data=None):
        """Pobiera stronę z opcjonalnymi parametrami."""
        if add_params is None:
            add_params = dict(self.default_params)
        return self.cm.getPage(base_url, add_params, post_data)

    def _extract_select_options(self, select_html):
        """
        Wyodrębnia opcje z pojedynczego selecta.
        """
        key = self.cm.ph.getSearchGroups(select_html, r'''name="([^"]+?)"''')[0]
        if not key:
            return None, []

        options = self.cm.ph.getAllItemsBeetwenMarkers(
            select_html, self.HTML_OPTION, self.HTML_OPTION_END
        )
        options_list = []
        for option in options:
            value = self.cm.ph.getSearchGroups(option, r'''value="([^"]+?)"''')[0]
            if not value:
                continue
            title = self.cleanHtmlStr(option)
            options_list.append({'title': title, 'post_data': {key: value}})

        return key, options_list

    def _process_selects_from_data(self, data, select_extractor):
        """
        Przetwarza wszystkie selecty znalezione w danych.
        """
        selects = select_extractor(data)
        for select in selects:
            key, options = self._extract_select_options(select)
            if key and options:
                self.cache_filters[key] = options
                self.cache_filters_keys.append(key)

    def _process_form_filters(self, form_data):
        """
        Przetwarza filtry z formularza.
        """
        filters_data = self.cm.ph.getAllItemsBeetwenNodes(
            form_data, ('<div', '>', 'form-group'), (self.HTML_DIV_END, '>')
        )

        if not filters_data:
            self._process_selects_from_data(
                form_data,
                lambda d: self.cm.ph.getAllItemsBeetwenMarkers(
                    d, self.HTML_SELECT, self.HTML_SELECT_END
                )
            )
            return

        for tmp in filters_data:
            key, options = self._extract_select_options(tmp)
            if key and options:
                self.cache_filters[key] = options
                self.cache_filters_keys.append(key)

    def listMainMenu(self, c_item):
        """Wyświetla główne menu."""
        printDBG("NuteczkiEU.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(
            data, ('<div', '>', 'drop-cat'), (self.HTML_SPAN_END, '>'), False
        )[1]
        tmp = re.compile(r'(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(tmp)

        if len(data) > 1:
            try:
                c_tree = self.listToDir(tmp[1:-1], 0)[0]
                tmp_list = []
                for item in c_tree['list']:
                    tmp_list.extend(item['list'])
                c_tree = {'data': '', 'list': tmp_list}

                params = dict(c_item)
                params.update({
                    'category': 'categories',
                    'title': _('Main menu'),
                    'c_tree': c_tree
                })
                self.addDir(params)
            except Exception:
                printExc()

        main_cat_tab = [
            {
                'category': 'list_items',
                'title': 'Najnowsze',
                'url': self.getFullUrl('/muzyka/')
            }
        ] + self.searchItems()
        self.listsTab(main_cat_tab, c_item)

    def _process_category_item(self, c_item, item, next_category):
        """
        Przetwarza pojedynczy element kategorii.
        """
        title = self.cleanHtmlStr(item['dat'])
        url = self.cm.ph.getSearchGroups(
            item['dat'], r'''href=['"]([^'^"]+?)['"]'''
        )[0]
        if url == '#':
            url = ''
        else:
            url = self.getFullUrl(url)

        if 'list' not in item:
            if self.cm.isValidUrl(url) and title:
                params = dict(c_item)
                params.update({
                    'good_for_fav': False,
                    'category': next_category,
                    'title': title,
                    'url': url
                })
                self.addDir(params)
            return

        if len(item['list']) == 1 and title:
            obj = item['list'][0]
            if url and 'list' in obj:
                obj['list'].insert(0, {
                    'dat': '<a href="%s">%s</a>' % (url, _('--All--'))
                })
            params = dict(c_item)
            params.update({
                'good_for_fav': False,
                'c_tree': obj,
                'title': title,
                'url': url
            })
            self.addDir(params)

    def listCategories(self, c_item, next_category):
        """Wyświetla kategorie."""
        printDBG("NuteczkiEU.listCategories")
        try:
            c_tree = c_item['c_tree']
            for item in c_tree['list']:
                self._process_category_item(c_item, item, next_category)
        except Exception:
            printExc()

    def fillCacheFilters(self, c_item):
        """
        Wypełnia cache filtrów dla strony.
        """
        printDBG("NuteczkiEU.fillCacheFilters")
        self.cache_filters = {}
        self.cache_filters_keys = []

        sts, data = self.getPage(c_item['url'])
        if not sts:
            return

        self.setMainUrl(self.cm.meta['url'])

        form_data = self.cm.ph.getDataBeetwenNodes(
            data, ('<form', '>', 'filter'), (self.HTML_FORM_END, '>'), False
        )[1]

        if not form_data:
            self._process_selects_from_data(
                data,
                lambda d: self.cm.ph.getAllItemsBeetwenNodes(
                    d, (self.HTML_SELECT, '>'), (self.HTML_SELECT_END, '>'), False
                )
            )
        else:
            self._process_form_filters(form_data)

        printDBG("cacheFilters: %s" % self.cache_filters)
        printDBG("cacheFiltersKeys: %s" % self.cache_filters_keys)

    def listFilters(self, c_item, next_category):
        """Wyświetla filtry."""
        printDBG("NuteczkiEU.listFilters")
        c_item = dict(c_item)

        f_idx = c_item.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(c_item)

        if f_idx >= len(self.cache_filters_keys):
            return

        filter_key = self.cache_filters_keys[f_idx]
        f_idx += 1
        c_item['f_idx'] = f_idx
        if f_idx == len(self.cache_filters_keys):
            c_item['category'] = next_category

        for item in self.cache_filters.get(filter_key, []):
            params = dict(c_item)
            params['post_data'] = dict(params.get('post_data', {}))
            params['post_data'].update(item['post_data'])
            if 'do=search' in c_item.get('url', ''):
                params['post_data']['do'] = 'search'
                params['post_data']['subaction'] = 'search'
            params['title'] = item['title']
            self.addDir(params)

    def _extract_item_icon(self, item_html):
        """Wyodrębnia ikonę z elementu."""
        return self.getFullIconUrl(
            self.cm.ph.getSearchGroups(
                item_html, r'''<img[^>]+?src=['"]([^"^']+?)['"]'''
            )[0]
        )

    def _extract_item_title(self, item_html):
        """Wyodrębnia tytuł z elementu."""
        tmp = self.cm.ph.getDataBeetwenNodes(
            item_html, ('<h2', '>', 'news-title'), ('</h2>', '>')
        )[1]
        if not tmp:
            tmp = self.cm.ph.getDataBeetwenNodes(
                item_html, ('<div', '>', 'short-result'), (self.HTML_DIV_END, '>')
            )[1]
            return self.cleanHtmlStr(
                self.cm.ph.getSearchGroups(tmp, r'''alt="([^"]+?)"''')[0]
            )
        return self.cleanHtmlStr(tmp)

    def _extract_item_url(self, item_html, tmp_html):
        """Wyodrębnia URL z elementu."""
        url = self.cm.ph.getSearchGroups(
            tmp_html, r'''href=['"]([^"^"]+?)['"]'''
        )[0]
        if url == '#':
            url = self.cm.ph.getSearchGroups(
                item_html, r'''(<div[^>]+?getPlayer[^>]+?>)'''
            )[0]
            url = self.cm.ph.getSearchGroups(
                url, r'''\sid=['"]([^'^"]+?)['"]'''
            )[0]
            if url:
                url = '/getPlayer.php?id=' + url
        return self.getFullUrl(url)

    def _extract_item_description(self, item_html):
        """Wyodrębnia opis z elementu."""
        desc = []
        tmp = self.cm.ph.getDataBeetwenNodes(
            item_html, ('<div', '>', 'news-meta'), (self.HTML_DIV_END, '>')
        )[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
        for t in tmp:
            label = self.cm.ph.getSearchGroups(t, r'''fa\-([a-zA-Z]+?)\s''')[0]
            t = self.cleanHtmlStr(t)
            if t:
                try:
                    desc.append('%s: %s' % (label.title(), int(t)))
                except Exception:
                    desc.append(t.replace(' , ', ', '))
        return '[/br]'.join(desc)

    def _extract_next_page(self, data, current_page):
        """Wyodrębnia URL następnej strony."""
        next_page = ''
        tmp = self.cm.ph.getAllItemsBeetwenNodes(
            data, ('<div', '>', 'pagination'), (self.HTML_DIV_END, '>'), False
        )
        for item in tmp:
            next_page = self.cm.ph.getSearchGroups(
                item,
                r'''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (current_page + 1)
            )[0]
            if next_page:
                break
        return next_page

    def _add_next_page(self, c_item, next_page, current_page):
        """Dodaje następną stronę do listy."""
        params = dict(c_item)
        params.pop('desc', None)

        if 'post_data' in params and 'do=search' in c_item['url']:
            next_page = c_item['url']
            params['post_data'] = dict(params['post_data'])
            params['post_data'].update({
                'search_start': current_page + 1,
                'full_search': '0',
                'result_from': params['post_data'].get('result_from', 1) + len(self.currList)
            })

        params.update({
            'title': _("Next page"),
            'url': self.getFullUrl(next_page),
            'page': current_page + 1
        })
        self.addDir(params)

    def listItems(self, c_item):
        """Wyświetla listę elementów."""
        printDBG("NuteczkiEU.listItems")
        page = c_item.get('page', 1)

        post_data = c_item.get('post_data')
        sts, data = self.getPage(c_item['url'], post_data=post_data)
        if not sts:
            return

        next_page = self._extract_next_page(data, page)

        content_data = self.cm.ph.getDataBeetwenNodes(
            data, ('<div', '>', 'dle-content'), ('<div', '>', 'clearfix'), False
        )[1]
        content_data = self.cm.ph.rgetAllItemsBeetwenNodes(
            content_data, (self.HTML_DIV_END, '>'), ('<div', '>', 'row'), False
        )

        for item in content_data:
            icon = self._extract_item_icon(item)
            title = self._extract_item_title(item)
            url = self._extract_item_url(item, item)
            desc = self._extract_item_description(item)

            params = dict(c_item)
            params.update({
                'good_for_fav': True,
                'title': title,
                'url': url,
                'desc': desc,
                'icon': icon
            })

            if url:
                self.addAudio(params)
            elif 'playerMask' in item:
                params['title'] = _('[Logged-in-only]') + " " + params['title']
                self.addArticle(params)

        if next_page:
            self._add_next_page(c_item, next_page, page)

    def listSearchResult(self, c_item, search_pattern, search_type):
        """Wyświetla wyniki wyszukiwania."""
        printDBG(
            "NuteczkiEU.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]"
            % (c_item, search_pattern, search_type)
        )
        c_item = dict(c_item)
        c_item['url'] = self.getFullUrl('/index.php?do=search')
        c_item['post_data'] = {
            'do': 'search',
            'subaction': 'search',
            'story': search_pattern
        }
        c_item['category'] = 'list_items'
        self.listItems(c_item)

    def _is_valid_player_url(self, url):
        """
        Sprawdza czy URL jest poprawnym URL-em odtwarzacza.
        Pomija facebook i radioftb.
        """
        if not url:
            return False
        url_lower = url.lower()
        return 'facebook' not in url_lower and 'radioftb' not in url_lower

    def _extract_player_urls(self, data, base_url):
        """
        Wyodrębnia wszystkie URL-e odtwarzaczy ze strony.
        """
        urls = []

        # Szukamy iframe
        iframes = self.cm.ph.getAllItemsBeetwenMarkers(
            data, self.HTML_IFRAME, self.HTML_IFRAME_END, caseSensitive=False
        )
        for iframe in iframes:
            url = self.cm.ph.getSearchGroups(
                iframe, r'''\ssrc=['"]([^"^"]+?)['"]''', 1, True
            )[0]
            if self._is_valid_player_url(url):
                urls.append(self.getFullUrl(url, base_url))

        # Szukamy div z data-url (krakenfiles)
        divs = self.cm.ph.getAllItemsBeetwenNodes(
            data, ('<div', '>', 'frame-fixer'), (self.HTML_DIV_END, '>'), caseSensitive=False
        )
        for div in divs:
            url = self.cm.ph.getSearchGroups(
                div, r'''\sdata\-url=['"]([^"^"]+?)['"]''', 1, True
            )[0]
            if self._is_valid_player_url(url):
                urls.append(self.getFullUrl(url, base_url))

        # Szukamy bezpośrednich linków do odtwarzaczy (tylko krakenfiles)
        # Używamy wzorca z PATTERN_KRAKENFILES - bezpieczny, bez backtrackingu
        player_links = re.findall(self.PATTERN_KRAKENFILES, data, re.I)
        for url in player_links:
            if url.startswith('/'):
                url = self.getFullUrl(url, base_url)
            if self._is_valid_player_url(url):
                urls.append(url)

        # Usuwamy duplikaty zachowując kolejność
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _extract_kraken_audio_url(self, data):
        """
        Wyodrębnia bezpośredni URL do pliku audio z krakenfiles.com.
        """
        # Szukamy w JavaScript - format m4a
        match = re.search(r'''m4a:\s*['"]([^'"]+\.m4a)['"]''', data, re.I)
        if match:
            return match.group(1)

        # Szukamy w JavaScript - format mp3
        match = re.search(r'''mp3:\s*['"]([^'"]+\.mp3)['"]''', data, re.I)
        if match:
            return match.group(1)

        # Szukamy bezpośredniego linku do pliku
        match = re.search(self.PATTERN_AUDIO_EXT, data, re.I)
        if match:
            return match.group(0)

        # Szukamy w JSON - prostszy wzorzec
        try:
            json_match = re.search(self.PATTERN_JSON_KEY, data, re.I)
            if json_match:
                return json_match.group(1)
        except Exception:
            pass

        return None

    def _extract_audio_urls_from_data(self, data):
        """
        Wyodrębnia URL-e audio z danych.
        """
        urls = []
        audio_patterns = [
            r'https?://[^"\']+\.mp3(?:\?[^"\']*)?',
            r'https?://[^"\']+\.m4a(?:\?[^"\']*)?',
            r'https?://[^"\']+\.ogg(?:\?[^"\']*)?',
            r'https?://[^"\']+\.wav(?:\?[^"\']*)?',
        ]

        for pattern in audio_patterns:
            matches = re.findall(pattern, data, re.I)
            for url in matches:
                if url and url not in urls:
                    urls.append(url)

        return urls

    def _extract_js_audio_urls(self, data):
        """
        Wyodrębnia URL-e audio z kodu JavaScript.
        """
        urls = []
        js_blocks = self.cm.ph.getAllItemsBeetwenMarkers(
            data, self.HTML_SCRIPT, self.HTML_SCRIPT_END
        )
        for js in js_blocks:
            found_urls = re.findall(self.PATTERN_AUDIO_EXT, js, re.I)
            for url in found_urls:
                if url and url not in urls:
                    urls.append(url)
        return urls

    def getLinksForVideo(self, c_item):
        """Pobiera linki dla wideo."""
        printDBG("NuteczkiEU.getLinksForVideo [%s]" % c_item)
        self.tryTologin()

        url_tab = []

        sts, data = self.getPage(c_item['url'])
        if not sts:
            return []
        self.setMainUrl(self.cm.meta['url'])

        player_urls = self._extract_player_urls(data, self.cm.meta['url'])

        for idx, url in enumerate(player_urls):
            if self.up.checkHostSupport(url) == 1:
                name = _('Player %s: %s') % (idx + 1, self.up.getHostName(url))
                url_tab.append({'url': url, 'name': name, 'need_resolve': 1})
            else:
                name = _('Player %s') % (idx + 1)
                url_tab.append({'url': url, 'name': name, 'need_resolve': 1})

        if not url_tab:
            audio_urls = re.findall(self.PATTERN_AUDIO_EXT, data, re.I)
            for url in audio_urls:
                if url not in [item['url'] for item in url_tab]:
                    url_tab.append({'url': url, 'name': 'Direct', 'need_resolve': 0})

        return url_tab

    def _process_kraken_audio(self, data, video_url, url_tab):
        """
        Przetwarza audio z krakenfiles.com.
        """
        if 'krakenfiles.com' in video_url.lower():
            audio_url = self._extract_kraken_audio_url(data)
            if audio_url:
                if not audio_url.startswith('http'):
                    audio_url = (
                        'https:' + audio_url
                        if audio_url.startswith('//')
                        else 'https://' + audio_url
                    )
                url_tab.append({'name': 'Audio', 'url': audio_url})
                return True
        return False

    def getVideoLinks(self, video_url):
        """Pobiera linki dla wideo."""
        printDBG("NuteczkiEU.getVideoLinks [%s]" % video_url)

        # Jeśli to znany host, użyj jego resolwera
        if self.up.checkHostSupport(video_url) == 1:
            return self.up.getVideoLinkExt(video_url)

        url_tab = []

        # Pobierz stronę
        sts, data = self.getPage(video_url)
        if not sts:
            return []

        # Obsługa krakenfiles.com
        if self._process_kraken_audio(data, video_url, url_tab):
            printDBG("NuteczkiEU.getVideoLinks result: %s" % url_tab)
            return url_tab

        # Ogólne wyszukiwanie linków audio
        audio_urls = self._extract_audio_urls_from_data(data)
        for url in audio_urls:
            if url not in [item['url'] for item in url_tab]:
                url_tab.append({'name': 'Direct', 'url': url})

        # Próbuj wyciągnąć z JavaScript
        if not url_tab:
            js_urls = self._extract_js_audio_urls(data)
            for url in js_urls:
                if url not in [item['url'] for item in url_tab]:
                    url_tab.append({'name': 'JS', 'url': url})

        printDBG("NuteczkiEU.getVideoLinks result: %s" % url_tab)
        return url_tab

    def tryTologin(self):
        """Próbuje zalogować użytkownika."""
        printDBG('tryTologin start')

        if (self.logged_in is None or
            self.login != config.plugins.iptvplayer.nuteczki_login.value or
            self.password != config.plugins.iptvplayer.nuteczki_password.value):

            self.login = config.plugins.iptvplayer.nuteczki_login.value
            self.password = config.plugins.iptvplayer.nuteczki_password.value

            rm(self.COOKIE_FILE)

            self.logged_in = False

            if not self.login.strip() or not self.password.strip():
                return False

            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return False
            self.setMainUrl(self.cm.meta['url'])

            action_url = self.cm.meta['url']
            post_data = {
                'login_name': self.login,
                'login_password': self.password,
                'login': 'submit'
            }

            http_params = dict(self.default_params)
            http_params['header'] = dict(self.AJAX_HEADER)
            http_params['header']['Referer'] = self.cm.meta['url']
            sts, data = self.cm.getPage(action_url, http_params, post_data)

            if sts and 'action=logout' in data:
                printDBG('tryTologin OK')
                self.logged_in = True
            else:
                msg_tab = [_('Login failed.')]
                if sts:
                    msg_tab.append(
                        self.cleanHtmlStr(
                            self.cm.ph.getAllItemsBeetwenNodes(
                                data,
                                ('<div', '>', 'alert'),
                                (self.HTML_DIV_END, '>'),
                                False
                            )[1]
                        )
                    )
                self.sessionEx.open(
                    MessageBox,
                    '\n'.join(msg_tab),
                    type=MessageBox.TYPE_ERROR,
                    timeout=10
                )
                printDBG('tryTologin failed')

        return self.logged_in

    def handleService(self, index, refresh=0, search_pattern='', search_type=''):
        """Główna metoda obsługi usługi."""
        printDBG('handleService start')

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, search_pattern, search_type)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

        if name is None:
            self.listMainMenu({'name': 'category'})

        elif category == 'categories':
            self.listCategories(self.currItem, 'list_items')

        elif category == 'list_items':
            self.listItems(self.currItem)

        elif category == 'filters':
            self.listFilters(self.currItem, 'list_items')

        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])

        elif category in ["search", "search_next_page"]:
            c_item = dict(self.currItem)
            c_item.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(c_item, search_pattern, search_type)

        elif category == "search_history":
            self.listsHistory(
                {'name': 'history', 'category': 'search'},
                'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    """Klasa hosta dla IPTV."""

    def __init__(self):
        CHostBase.__init__(self, NuteczkiEU(), True, favouriteTypes=[])
