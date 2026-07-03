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
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.nuteczki_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.nuteczki_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.nuteczki_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.nuteczki_password))
    return optionList
###################################################


def gettytul():
    return 'https://nuteczki.eu/'


class NuteczkiEU(CBaseHostClass):

    # Stałe dla znaczników HTML - zmniejszają złożoność i eliminują duplikację
    HTML_DIV_END = '</div'
    HTML_SELECT = '<select'
    HTML_SELECT_END = '</select>'
    HTML_OPTION = '<option'
    HTML_OPTION_END = '</option>'
    HTML_IFRAME = '<iframe'
    HTML_IFRAME_END = '</iframe>'
    HTML_SCRIPT = '<script'
    HTML_SCRIPT_END = '</script>'

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'nuteczki.eu', 'cookie': 'nuteczki.eu.cookie'})

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://nuteczki.eu/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/736x/2d/07/83/2d0783d156a48860691667dadd8de458--note-music-music-wallpaper.jpg'

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _extract_select_options(self, select_html):
        """
        Wyodrębnia opcje z pojedynczego selecta.
        """
        key = self.cm.ph.getSearchGroups(select_html, '''name="([^"]+?)"''')[0]
        if key == '':
            return None, []

        options = self.cm.ph.getAllItemsBeetwenMarkers(select_html, self.HTML_OPTION, self.HTML_OPTION_END)
        options_list = []
        for option in options:
            value = self.cm.ph.getSearchGroups(option, '''value="([^"]+?)"''')[0]
            if value == '':
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
                self.cacheFilters[key] = options
                self.cacheFiltersKeys.append(key)

    def _process_form_filters(self, form_data):
        """
        Przetwarza filtry z formularza.
        """
        filters_data = self.cm.ph.getAllItemsBeetwenNodes(
            form_data, ('<div', '>', 'form-group'), (self.HTML_DIV_END, '>')
        )

        if not filters_data:
            # Próbujemy znaleźć selecty bezpośrednio w formularzu
            self._process_selects_from_data(
                form_data,
                lambda d: self.cm.ph.getAllItemsBeetwenMarkers(d, self.HTML_SELECT, self.HTML_SELECT_END)
            )
            return

        for tmp in filters_data:
            key, options = self._extract_select_options(tmp)
            if key and options:
                self.cacheFilters[key] = options
                self.cacheFiltersKeys.append(key)

    def listMainMenu(self, cItem):
        printDBG("NuteczkiEU.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'drop-cat'), ('</span', '>'), False)[1]
        tmp = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(tmp)
        if len(data) > 1:
            try:
                cTree = self.listToDir(tmp[1:-1], 0)[0]
                tmpList = []
                for item in cTree['list']:
                    tmpList.extend(item['list'])
                cTree = {'data': '', 'list': tmpList}

                params = dict(cItem)
                params.update({'category': 'categories', 'title': _('Main menu'), 'c_tree': cTree})
                self.addDir(params)
            except Exception:
                printExc()

        MAIN_CAT_TAB = [
            {'category': 'list_items', 'title': _('Najnowsze'), 'url': self.getFullUrl('/muzyka/')}
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("NuteczkiEU.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat'])
                url = self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '#':
                    url = ''
                else:
                    url = self.getFullUrl(url)
                if 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    obj = item['list'][0]
                    if url != '' and 'list' in obj:
                        obj['list'].insert(0, {'dat': '<a href="%s">%s</a>' % (url, _('--All--'))})
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': obj, 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def fillCacheFilters(self, cItem):
        """
        Wypełnia cache filtrów dla strony.
        """
        printDBG("NuteczkiEU.fillCacheFilters")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        self.setMainUrl(self.cm.meta['url'])

        # Szukamy formularza filtrowania - nowa struktura
        form_data = self.cm.ph.getDataBeetwenNodes(
            data, ('<form', '>', 'filter'), ('</form', '>'), False
        )[1]

        if not form_data:
            # Próbujemy znaleźć selecty z klasą lub id
            self._process_selects_from_data(
                data,
                lambda d: self.cm.ph.getAllItemsBeetwenNodes(d, (self.HTML_SELECT, '>'), (self.HTML_SELECT_END, '>'), False)
            )
        else:
            # Stara metoda - dla formularza
            self._process_form_filters(form_data)

        printDBG("cacheFilters: %s" % self.cacheFilters)
        printDBG("cacheFiltersKeys: %s" % self.cacheFiltersKeys)

    def listFilters(self, cItem, nextCategory):
        printDBG("NuteczkiEU.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter_key = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory

        for item in self.cacheFilters.get(filter_key, []):
            params = dict(cItem)
            params['post_data'] = dict(params.get('post_data', {}))
            params['post_data'].update(item['post_data'])
            # Dodajemy domyślne parametry jeśli istnieją
            if 'do=search' in cItem.get('url', ''):
                params['post_data']['do'] = 'search'
                params['post_data']['subaction'] = 'search'
            params['title'] = item['title']
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("NuteczkiEU.listItems")
        page = cItem.get('page', 1)

        postData = cItem.get('post_data')
        sts, data = self.getPage(cItem['url'], post_data=postData)
        if not sts:
            return

        nextPage = ''
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'pagination'), (self.HTML_DIV_END, '>'), False)
        for item in tmp:
            nextPage = self.cm.ph.getSearchGroups(item, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
            if nextPage != '':
                break

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'dle-content'), ('<div', '>', 'clearfix'), False)[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, (self.HTML_DIV_END, '>'), ('<div', '>', 'row'), False)
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])

            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>', 'news-title'), ('</h2>', '>'))[1]
            if tmp == '':
                tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short-result'), (self.HTML_DIV_END, '>'))[1]
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, '''alt="([^"]+?)"''')[0])
            else:
                title = self.cleanHtmlStr(tmp)

            url = self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^"]+?)['"]''')[0]
            if url == '#':
                url = self.cm.ph.getSearchGroups(item, '''(<div[^>]+?getPlayer[^>]+?>)''')[0]
                url = self.cm.ph.getSearchGroups(url, r'''\sid=['"]([^'^"]+?)['"]''')[0]
                if url != '':
                    url = '/getPlayer.php?id=' + url
            url = self.getFullUrl(url)

            desc = []
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'news-meta'), (self.HTML_DIV_END, '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
            for t in tmp:
                label = self.cm.ph.getSearchGroups(t, r'''fa\-([a-zA-Z]+?)\s''')[0]
                t = self.cleanHtmlStr(t)
                if t != '':
                    try:
                        desc.append('%s: %s' % (label.title(), int(t)))
                    except Exception:
                        desc.append(t.replace(' , ', ', '))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': '[/br]'.join(desc), 'icon': icon})
            if url != '':
                self.addAudio(params)
            elif 'playerMask' in item:
                params['title'] = _('[Logged-in-only] ') + params['title']
                self.addArticle(params)

        if nextPage != '':
            params = dict(cItem)
            params.pop('desc', None)

            if 'post_data' in params and 'do=search' in cItem['url']:
                nextPage = cItem['url']
                params['post_data'] = dict(params['post_data'])
                params['post_data'].update({'search_start': page + 1, 'full_search': '0', 'result_from': params['post_data'].get('result_from', 1) + len(self.currList)})

            params.update({'title': _("Next page"), 'url': self.getFullUrl(nextPage), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("NuteczkiEU.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/index.php?do=search')
        cItem['post_data'] = {'do': 'search', 'subaction': 'search', 'story': searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def _extract_player_urls(self, data, base_url):
        """
        Wyodrębnia wszystkie URL-e odtwarzaczy ze strony.
        """
        urls = []

        # Szukamy iframe
        iframes = self.cm.ph.getAllItemsBeetwenMarkers(data, self.HTML_IFRAME, self.HTML_IFRAME_END, caseSensitive=False)
        for iframe in iframes:
            url = self.cm.ph.getSearchGroups(iframe, r'''\ssrc=['"]([^"^"]+?)['"]''', 1, True)[0]
            if url and 'facebook' not in url.lower() and 'radioftb' not in url.lower():
                urls.append(self.getFullUrl(url, base_url))

        # Szukamy div z data-url (krakenfiles)
        divs = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'frame-fixer'), (self.HTML_DIV_END, '>'), caseSensitive=False)
        for div in divs:
            url = self.cm.ph.getSearchGroups(div, r'''\sdata\-url=['"]([^"^"]+?)['"]''', 1, True)[0]
            if url and 'radioftb' not in url.lower():
                urls.append(self.getFullUrl(url, base_url))

        # Szukamy bezpośrednich linków do odtwarzaczy (tylko krakenfiles)
        player_links = re.findall(r'''<a[^>]+?href=['"]([^'"]*krakenfiles[^'"]*?)['"]''', data, re.I)
        for url in player_links:
            if url.startswith('/'):
                url = self.getFullUrl(url, base_url)
            if url and 'facebook' not in url.lower() and 'radioftb' not in url.lower():
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
        match = re.search(r'''https?://[^'"]+\.(?:m4a|mp3)''', data, re.I)
        if match:
            return match.group(0)

        # Szukamy w JSON
        try:
            json_match = re.search(r'''\{[^}]*"(?:m4a|mp3|file)"[^}]*\}''', data, re.I)
            if json_match:
                json_data = json.loads(json_match.group(0))
                for key in ['m4a', 'mp3', 'file']:
                    if key in json_data:
                        return json_data[key]
        except Exception:
            pass

        return None

    def getLinksForVideo(self, cItem):
        printDBG("NuteczkiEU.getLinksForVideo [%s]" % cItem)
        self.tryTologin()

        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        self.setMainUrl(self.cm.meta['url'])

        # Wyodrębnij wszystkie URL-e odtwarzaczy (tylko krakenfiles)
        player_urls = self._extract_player_urls(data, self.cm.meta['url'])

        for idx, url in enumerate(player_urls):
            # Sprawdź czy to znany host
            if 1 == self.up.checkHostSupport(url):
                name = _('Player %s: %s') % (idx + 1, self.up.getHostName(url))
                urlTab.append({'url': url, 'name': name, 'need_resolve': 1})
            else:
                # Dla nieznanych hostów próbujemy pobrać bezpośredni link
                name = _('Player %s') % (idx + 1)
                urlTab.append({'url': url, 'name': name, 'need_resolve': 1})

        # Jeśli nie znaleziono żadnych odtwarzaczy, spróbuj znaleźć bezpośredni link audio
        if not urlTab:
            # Szukaj bezpośredniego linku do pliku audio
            audio_urls = re.findall(r'''https?://[^'"]+\.(?:mp3|m4a|ogg|wav)''', data, re.I)
            for url in audio_urls:
                if url not in [item['url'] for item in urlTab]:
                    urlTab.append({'url': url, 'name': 'Direct', 'need_resolve': 0})

        return urlTab

    def _extract_audio_urls_from_data(self, data):
        """
        Wyodrębnia URL-e audio z danych.
        """
        urls = []
        audio_patterns = [
            r'''https?://[^'"]+\.mp3(?:\?[^'"]*)?''',
            r'''https?://[^'"]+\.m4a(?:\?[^'"]*)?''',
            r'''https?://[^'"]+\.ogg(?:\?[^'"]*)?''',
            r'''https?://[^'"]+\.wav(?:\?[^'"]*)?''',
        ]

        for pattern in audio_patterns:
            matches = re.findall(pattern, data, re.I)
            for url in matches:
                if url and url not in urls:
                    urls.append(url)

        return urls

    def getVideoLinks(self, videoUrl):
        printDBG("NuteczkiEU.getVideoLinks [%s]" % videoUrl)

        # Jeśli to znany host, użyj jego resolwera
        if 1 == self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        urlTab = []

        # Pobierz stronę
        sts, data = self.getPage(videoUrl)
        if not sts:
            return []

        # Obsługa krakenfiles.com
        if 'krakenfiles.com' in videoUrl.lower():
            audio_url = self._extract_kraken_audio_url(data)
            if audio_url:
                # Sprawdź czy to już jest pełny URL
                if not audio_url.startswith('http'):
                    audio_url = 'https:' + audio_url if audio_url.startswith('//') else 'https://' + audio_url
                urlTab.append({'name': 'Audio', 'url': audio_url})

        # Ogólne wyszukiwanie linków audio
        if not urlTab:
            audio_urls = self._extract_audio_urls_from_data(data)
            for url in audio_urls:
                if url not in [item['url'] for item in urlTab]:
                    urlTab.append({'name': 'Direct', 'url': url})

        # Próbuj wyciągnąć z JavaScript (dla krakenfiles)
        if not urlTab:
            # Szukaj w kodzie JavaScript
            js_blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, self.HTML_SCRIPT, self.HTML_SCRIPT_END)
            for js in js_blocks:
                # Szukaj URL-i w stringach
                urls = re.findall(r'''['"](https?://[^'"]+\.(?:mp3|m4a|ogg|wav)[^'"]*)['"]''', js, re.I)
                for url in urls:
                    if url not in [item['url'] for item in urlTab]:
                        urlTab.append({'name': 'JS', 'url': url})

        printDBG("NuteczkiEU.getVideoLinks result: %s" % urlTab)
        return urlTab

    def tryTologin(self):
        printDBG('tryTologin start')

        if None is self.loggedIn or self.login != config.plugins.iptvplayer.nuteczki_login.value or\
            self.password != config.plugins.iptvplayer.nuteczki_password.value:

            self.login = config.plugins.iptvplayer.nuteczki_login.value
            self.password = config.plugins.iptvplayer.nuteczki_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                return False

            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return False
            self.setMainUrl(self.cm.meta['url'])

            actionUrl = self.cm.meta['url']
            post_data = {'login_name': self.login, 'login_password': self.password, 'login': 'submit'}

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(self.AJAX_HEADER)
            httpParams['header']['Referer'] = self.cm.meta['url']
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and 'action=logout' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                if sts:
                    msgTab.append(self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'alert'), (self.HTML_DIV_END, '>'), False)[1]))
                self.sessionEx.open(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

        # MAIN MENU
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
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, NuteczkiEU(), True, favouriteTypes=[])
