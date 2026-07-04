# -*- coding: utf-8 -*-
# Last Modified: 04.07.2026 - damagic
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import base64
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText
###################################################


def GetConfigList():
    """Zwraca listę opcji konfiguracyjnych."""
    option_list = []
    return option_list


def gettytul():
    """Zwraca tytuł hosta."""
    return 'https://premiumsmart.eu/'


class Premiumsmarteu(CBaseHostClass):
    """
    Klasa obsługująca host premiumsmart.eu.
    """

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'premiumsmart.eu', 'cookie': 'premiumsmart.eu.cookie'})

        config.plugins.iptvplayer.cloudflare_user = ConfigText(
            default='Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0',
            fixed_size=False
        )
        self.USER_AGENT = config.plugins.iptvplayer.cloudflare_user.value
        self.MAIN_URL = 'https://premiumsmart.eu/'
        self.API_URL = self.getFullUrl('api/v1/')
        self.DEFAULT_ICON_URL = (
            'https://premiumsmart.eu/storage/branding_media/'
            '9a5b1890-53ce-4052-9a83-862d97a6b285.png'
        )
        self.HTTP_HEADER = {
            'User-Agent': self.USER_AGENT,
            'DNT': '1',
            'Accept': 'text/html',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': self.getMainUrl(),
            'Origin': self.getMainUrl(),
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive'
        }
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        })

        self.itemsPerPage = 50
        self.cache_movie_filters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cache_links = {}
        self.default_params = {
            'header': self.HTTP_HEADER,
            'with_metadata': True,
            'use_cookie': True,
            'load_cookie': True,
            'save_cookie': True,
            'cookiefile': self.COOKIE_FILE
        }

        self.menu = [
            {
                'category': 'list_sort',
                'title': _('Filmy'),
                'url': self.API_URL + 'channel/filmy?perPage=%d' % self.itemsPerPage
            },
            {
                'category': 'list_sort',
                'title': _('Seriale'),
                'url': self.API_URL + 'channel/seriale?perPage=%d' % self.itemsPerPage
            },
            {
                'category': 'search',
                'title': _('Search'),
                'search_item': True
            },
            {
                'category': 'search_history',
                'title': _('Search history')
            },
        ]

    def getPage(self, base_url, add_params=None, post_data=None):
        """Pobiera stronę z ochroną CloudFlare."""
        if add_params is None:
            add_params = dict(self.default_params)

        base_url = self.cm.iriToUri(base_url)
        sts, data = self.cm.getPageCFProtection(base_url, add_params, post_data)

        if data.meta.get('cf_user', self.USER_AGENT) != self.USER_AGENT:
            self.__init__()
        return sts, data

    def setMainUrl(self, url):
        """Ustawia główny URL."""
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, c_item):
        """Wyświetla główne menu."""
        printDBG("Premiumsmarteu.listMainMenu")
        self.listsTab(self.menu, c_item)

    def listSort(self, c_item):
        """Wyświetla opcje sortowania."""
        printDBG("Premiumsmarteu.listSort")
        sort_tab = [
            {'category': 'list_items', 'title': 'Data dodania', 'url': c_item['url'] + '&order=created_at:desc'},
            {'category': 'list_items', 'title': 'Popularność', 'url': c_item['url'] + '&order=popularity:desc'},
            {'category': 'list_items', 'title': 'Data wydania', 'url': c_item['url'] + '&order=release_date:desc'},
            {'category': 'list_items', 'title': 'Ocena użytkowników', 'url': c_item['url'] + '&order=rating:desc'},
            {'category': 'list_items', 'title': 'Dochód', 'url': c_item['url'] + '&order=revenue:desc'},
            {'category': 'list_items', 'title': 'Budżet', 'url': c_item['url'] + '&order=budget:desc'},
        ]
        self.listsTab(sort_tab, c_item)

    def _fill_movie_filters(self, c_item):
        """Wypełnia cache filtrów dla filmów."""
        self.cache_movie_filters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        # fill sort
        sort_data = [
            ('&order=created_at:desc', 'Data dodania'),
            ('&order=popularity:desc', 'Popularność'),
            ('&order=release_date:desc', 'Data wydania'),
            ('&order=rating:desc', 'Ocena użytkowników'),
            ('&order=revenue:desc', 'Dochód'),
            ('&order=budget:desc', 'Budżet')
        ]
        for item in sort_data:
            self.cache_movie_filters['sort'].append({'title': item[1], 'sort': item[0]})

        # fill cats
        cat_data = [
            ('&genre=Akcja', 'Akcja'),
            ('&genre=Animacja', 'Animacja'),
            ('&genre=Dokumentalny', 'Data wydania'),
            ('&genre=Dramat', 'Dramat'),
            ('&genre=Familijny', 'Familijny'),
            ('&genre=Fantasy', 'Fantasy'),
            ('&genre=Historyczny', 'Historyczny'),
            ('&genre=Horror', 'Horror'),
            ('&genre=Komedia', 'Komedia'),
            ('&genre=Krymina%C5%82', 'Kryminał'),
            ('&genre=Muzyczny', 'Muzyczny'),
            ('&genre=Przygodowy', 'Przygodowy'),
            ('&genre=Romans', 'Romans'),
            ('&genre=Sci-Fi', 'Sci-Fi'),
            ('&genre=Tajemnica', 'Tajemnica'),
            ('&genre=Thriller', 'Thriller'),
            ('&genre=Western', 'Western'),
            ('&genre=Wojenny', 'Wojenny'),
            ('&genre=film%20TV', 'Film TV'),
            ('&genre=Sport%20LIVE', 'Sport LIVE')
        ]
        for item in cat_data:
            self.cache_movie_filters['cats'].append({'title': item[1], 'url': c_item['url'] + item[0]})

    def listMovieFilters(self, c_item, category):
        """Wyświetla filtry dla filmów."""
        printDBG("Premiumsmarteu.listMovieFilters")

        filter_type = c_item['category'].split('_')[-1]
        self._fill_movie_filters(c_item)

        if len(self.cache_movie_filters[filter_type]) > 0:
            filter_tab = []
            filter_tab.extend(self.cache_movie_filters[filter_type])
            self.listsTab(filter_tab, c_item, category)

    def listsTab(self, tab, c_item, category=None):
        """Wyświetla listę z zakładkami."""
        printDBG("Premiumsmarteu.listsTab")
        for item in tab:
            params = dict(c_item)
            if category is not None:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def _get_xsrf_token(self):
        """Pobiera token XSRF z ciasteczek."""
        token = self.cm.getCookieItem(self.COOKIE_FILE, 'XSRF-TOKEN')
        if token:
            return token.replace('%3D', '=')
        return ''

    def _parse_item_data(self, item):
        """
        Parsuje dane pojedynczego elementu z API.
        """
        icon = self.getFullIconUrl(item.get('poster', ''))
        if 'original' in icon:
            icon = icon.replace('/original/', '/w500/')

        title = item.get('name', '')
        desc = item.get('description', '')

        if item.get('is_series'):
            video_id = item.get('id')
        else:
            try:
                video_id = item['primary_video']['id']
            except (KeyError, TypeError):
                # Pobierz dodatkowe dane z API
                url = self.getFullUrl(self.API_URL + 'titles/%d?load=primaryVideo' % item['id'])
                sts, data = self.getPage(url)
                if not sts:
                    return None
                try:
                    data = json_loads(data)['title']
                    video_id = data['primary_video']['id']
                except Exception:
                    return None

        return {
            'icon': icon,
            'title': title,
            'desc': desc,
            'video_id': video_id,
            'is_series': item.get('is_series', False)
        }

    def _add_item_to_list(self, c_item, item_data):
        """
        Dodaje element do listy.
        """
        if item_data['is_series']:
            url = self.getFullUrl(self.API_URL + 'titles/%d/seasons' % item_data['video_id'])
            params = {
                'good_for_fav': True,
                'category': 'list_seasons',
                'url': url,
                'title': item_data['title'],
                'desc': item_data['desc'],
                'icon': item_data['icon']
            }
            self.addDir(params)
        else:
            url = self.getFullUrl(self.API_URL + 'watch/%d' % item_data['video_id'])
            params = {
                'good_for_fav': True,
                'url': url,
                'title': item_data['title'],
                'desc': item_data['desc'],
                'icon': item_data['icon']
            }
            self.addVideo(params)

    def listItems(self, c_item):
        """Wyświetla listę elementów."""
        printDBG("Premiumsmarteu.listItems [%s]" % c_item)
        page = c_item.get('page', 1)
        url = c_item['url']

        sort = c_item.get('sort', '')
        if sort not in url:
            url = url + sort

        if page > 1:
            url = url + '&page={0}'.format(page)

        # Pobierz token XSRF
        url_params = dict(self.default_params)
        sts, data = self.getPage(self.MAIN_URL, url_params)
        if not sts:
            return

        url_params['header']['x-xsrf-token'] = self._get_xsrf_token()
        sts, data = self.getPage(url, url_params)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        try:
            if '/search/' in url:
                data = json_loads(data)['results']
                next_page = False
            else:
                data = json_loads(data)['channel']['content']
                next_page = data.get('next_page', False)
                data = data['data']
        except Exception:
            printExc()
            return

        for item in data:
            item_data = self._parse_item_data(item)
            if item_data:
                self._add_item_to_list(c_item, item_data)

        if next_page:
            params = dict(c_item)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def _get_episodes(self, season_url):
        """
        Pobiera listę odcinków dla danego sezonu.
        """
        sts, data = self.getPage(season_url)
        if not sts:
            return []

        try:
            data = json_loads(data)
        except Exception:
            printDBG("Premiumsmarteu._get_episodes: invalid JSON")
            return []

        if 'pagination' not in data or 'data' not in data['pagination']:
            return []

        episodes = []
        for item in data['pagination']['data']:
            try:
                url = self.getFullUrl(self.API_URL + 'watch/%d' % item['primary_video']['id'])
            except Exception:
                continue

            icon = self.getFullIconUrl(item.get('poster', ' '))
            if 'original' in icon:
                icon = icon.replace('/original/', '/w500/')

            episodes.append({
                'url': url,
                'title': item.get('name', ''),
                'desc': item.get('description', ''),
                'icon': icon
            })

        return episodes

    def listSeriesSeasons(self, c_item, next_category):
        """Wyświetla listę sezonów dla serialu."""
        printDBG("Premiumsmarteu.listSeriesSeasons")
        sts, data = self.getPage(c_item['url'])
        if not sts:
            return

        if not data or not data.strip():
            printDBG("Premiumsmarteu.listSeriesSeasons: empty response")
            return

        if '<!DOCTYPE' in data or '<html' in data:
            printDBG("Premiumsmarteu.listSeriesSeasons: got HTML instead of JSON")
            return

        try:
            data = json_loads(data)
        except Exception:
            printDBG("Premiumsmarteu.listSeriesSeasons: invalid JSON response")
            return

        if 'pagination' not in data or 'data' not in data['pagination']:
            printDBG("Premiumsmarteu.listSeriesSeasons: no pagination data")
            return

        for s_item in data['pagination']['data']:
            season_url = self.getFullUrl(c_item['url'] + '/%d/episodes' % s_item['number'])
            episodes = self._get_episodes(season_url)

            if episodes:
                season_title = 'Sezon %d' % s_item['number']
                params = dict(c_item)
                params.update({
                    'good_for_fav': False,
                    'category': next_category,
                    'title': season_title,
                    'episodes': episodes,
                    'icon': c_item['icon'],
                    'desc': ''
                })
                self.addDir(params)

    def listSeriesEpisodes(self, c_item):
        """Wyświetla listę odcinków dla serialu."""
        printDBG("Premiumsmarteu.listSeriesEpisodes [%s]" % c_item)
        episodes = c_item.get('episodes', [])
        c_item = dict(c_item)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, c_item, search_pattern, search_type):
        """Wyświetla wyniki wyszukiwania."""
        printDBG(
            "Premiumsmarteu.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]"
            % (c_item, search_pattern, search_type)
        )
        url = self.getFullUrl(self.API_URL + 'search/%s?limit=20') % urllib_quote_plus(search_pattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, c_item):
        """Pobiera linki dla wideo."""
        printDBG("Premiumsmarteu.getLinksForVideo [%s]" % c_item)

        cache_key = c_item['url']
        cache_tab = self.cache_links.get(cache_key, [])
        if len(cache_tab):
            printDBG("Premiumsmarteu.getLinksForVideo using cache [%d] items" % len(cache_tab))
            return cache_tab

        self.cache_links = {}

        sts, data = self.getPage(c_item['url'])
        if not sts:
            printDBG("Premiumsmarteu.getLinksForVideo failed to get page")
            return []

        self.setMainUrl(data.meta['url'])

        try:
            data = json_loads(data)
            printDBG(
                "Premiumsmarteu.getLinksForVideo alternative_videos count[%d]"
                % len(data.get('alternative_videos', []))
            )
        except Exception:
            printExc()
            return []

        skip_hosts = ['drakkar.st', 'bysetayico.com', 'byse']
        ret_tab = []

        for item in data.get('alternative_videos', []):
            player_url = self.getFullUrl(item.get('src', '')).replace(' ', '%20')
            if not player_url:
                printDBG("Premiumsmarteu.getLinksForVideo empty playerUrl")
                continue

            host = self.up.getHostName(player_url)

            # Sprawdź czy host jest na liście do pominięcia
            skip = False
            for skip_host in skip_hosts:
                if skip_host in host:
                    printDBG("Premiumsmarteu.getLinksForVideo SKIPPING host[%s]" % host)
                    skip = True
                    break
            if skip:
                continue

            name = item.get('name', '') + ' - ' + self.up.getHostName(player_url)
            if item.get('category') == 'trailer':
                name = '[trailer] ' + name

            meta = {'Referer': self.MAIN_URL, 'User-Agent': self.USER_AGENT}
            printDBG("Premiumsmarteu.getLinksForVideo host[%s] playerUrl[%s]" % (host, player_url))

            ret_tab.append({
                'name': name,
                'url': strwithmeta(player_url, meta),
                'need_resolve': 1
            })

        printDBG("Premiumsmarteu.getLinksForVideo total links[%d]" % len(ret_tab))
        if len(ret_tab):
            self.cache_links[cache_key] = ret_tab
        return ret_tab

    def getVideoLinks(self, base_url):
        """Pobiera linki dla wideo."""
        printDBG("Premiumsmarteu.getVideoLinks [%s]" % base_url)
        base_url = strwithmeta(base_url)

        if len(self.cache_links.keys()):
            for key in self.cache_links:
                for idx in range(len(self.cache_links[key])):
                    if base_url in self.cache_links[key][idx]['url']:
                        if not self.cache_links[key][idx]['name'].startswith('*'):
                            self.cache_links[key][idx]['name'] = '*' + self.cache_links[key][idx]['name'] + '*'
                        break

        if 'User-Agent' not in base_url.meta:
            base_url.meta['User-Agent'] = self.USER_AGENT

        return self.up.getVideoLinkExt(base_url)

    def handleService(self, index, refresh=0, search_pattern='', search_type=''):
        """Główna metoda obsługi usługi."""
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, search_pattern, search_type)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))

        self.cache_links = {}
        self.currList = []

        if name is None and category == '':
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'})
        elif category == 'list_sort':
            self.listSort(self.currItem)
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_sort')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_az' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_seasons':
            self.listSeriesSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listSeriesEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            c_item = dict(self.currItem)
            c_item.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(c_item, search_pattern, search_type)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    """Klasa hosta dla IPTV."""

    def __init__(self):
        CHostBase.__init__(self, Premiumsmarteu(), True, [])
