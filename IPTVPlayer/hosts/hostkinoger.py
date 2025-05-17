# -*- coding: utf-8 -*-
import re

from Components.config import (ConfigSelection, ConfigText, config,
                               getConfigListEntry)
from Plugins.Extensions.IPTVPlayer.components.ihost import (CBaseHostClass,
                                                            CHostBase)
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import \
    TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (MergeDicts,
                                                           printDBG, printExc)
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest

from urllib.parse import quote as urllib_quote

config.plugins.iptvplayer.kinoger_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                   ("proxy_1", _("Alternative proxy server (1)")),
                                                                                   ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.kinoger_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kinoger_proxy))
    if config.plugins.iptvplayer.kinoger_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.kinoger_alt_domain))
    return optionList


def gettytul():
    return 'https://kinoger.to/'


class KinoGer(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kinoger', 'cookie': 'kinoger.cookie'})

        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = 'https://kinoger.to/templates/kinoger/images/logo.png'

        config.plugins.iptvplayer.cloudflare_user = ConfigText(default='Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', fixed_size=False)
        self.USER_AGENT = config.plugins.iptvplayer.cloudflare_user.value
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getProxy(self):
        proxy = config.plugins.iptvplayer.kinoger_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
        else:
            proxy = None
        return proxy

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = MergeDicts(self.defaultParams, {'Referer': self.cm.getBaseUrl(baseUrl), 'Origin': self.cm.getBaseUrl(baseUrl)[:-1]})

            proxy = self.getProxy()
            if proxy != None:
                addParams = MergeDicts(addParams, {'http_proxy': proxy})

        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if data.meta.get('cf_user', self.USER_AGENT) != self.USER_AGENT:
            self.__init__()
        return sts, data

    def selectDomain(self):
        domains = ['https://kinoger.to/']
        domain = config.plugins.iptvplayer.kinoger_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts:
                if 'KinoGer' in data:
                    self.setMainUrl(self.cm.meta['url'])
                    break
            elif self.MAIN_URL != None:
                break

        if self.MAIN_URL == None:
            self.MAIN_URL = domains[0]

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '':
            return ''
        proxy = self.getProxy()
        if proxy != None:
            url = strwithmeta(url, {'iptv_http_proxy': proxy})

        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance', '__cfduid'])
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def listMainMenu(self, cItem):
        printDBG("KinoGer.listMainMenu")
        MAIN_CAT_TAB = [
            {'category': 'list_items', 'title': 'Neues', 'url': self.getMainUrl()},
            {'category': 'list_items', 'title': _("Series"), 'url': self.getFullUrl('/stream/serie/')},
            {'category': 'list_genres', 'title': 'Genres'},
            {'category': 'search', 'title': _('Search'), 'search_item': True, },
            {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG(f"KinoGer.listItems cItem[{cItem}]")
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'<a[^>]href="([^"]+)">vorw')[0]
        data = re.compile(r'class="title".*?href="([^"]+)">([^<]+).*?src="([^"]+)(.*?)"footercontrol">', re.DOTALL).findall(data)

        for url, title, icon, dummy in data:
            desc = re.compile(r'<div style="text-align:right;">(.*?)<div[^>]class', re.DOTALL).findall(dummy)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'url': url, 'icon': icon, 'desc': self.cleanHtmlStr(desc[0]) if desc else ''})
            if 'taffel' in title or 'serie' in cItem['url'] or '>S0' in dummy:
                params.update({'category': 'list_seasons'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG(f"KinoGer.listSeasons cItem[{cItem}]")
        url = cItem['url']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        season_lists = {}
        total = 0
        for key in ['sst', 'ollhd', 'pw', 'go']:
            container = re.compile(fr'{key}.show.*?</script>', re.DOTALL).findall(data)
            if container:
                container = container[0]
                container = container.replace('[', '<').replace(']', '>')
                season_lists[key] = re.compile(r"<'([^>]+)", re.DOTALL).findall(container)
                if container:
                    total = len(season_lists[key])
        for i in range(total):
            params = dict(cItem)
            title = f"{cItem.get('title')} - Staffel {i + 1}"
            for key in ['sst', 'ollhd', 'pw', 'go']:
                if key in season_lists and i < len(season_lists[key]):
                    params.update({key: season_lists[key][i]})
            params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': title, 'url': url, 'icon': icon, 'desc': cItem.get('desc', '')})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG(f"KinoGer.listEpisodes cItem[{cItem}]")
        icon = cItem['icon']
        episode_lists = {}
        for key in ['sst', 'ollhd', 'pw', 'go']:
            if cItem.get(key):
                episode_lists[key] = re.compile(r"(http[^']+)", re.DOTALL).findall(cItem[key])
        liste = zip_longest(*[episode_lists[key] for key in ['sst', 'ollhd', 'pw', 'go'] if key in episode_lists])
        for i, url in enumerate(liste, start=1):
            title = f'{cItem.get("title")} - Episode {i}'
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'Episode': url, 'icon': icon, 'desc': cItem.get('desc', '')})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG(f"KinoGer.listGenres cItem[{cItem}]")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="sidelinks', '</ul>')[0]
        data = re.compile(r'href="([^"]+).*?/>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if 'erie' in title or url == '/':
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG(f"KinoGer.listSearchResult cItem[{cItem}], searchPattern[{searchPattern}] searchType[{searchType}]")

        cItem = dict(cItem)
        if 'url' not in cItem:
            cItem['url'] = self.getFullUrl(f'?do=search&subaction=search&titleonly=3&story={urllib_quote(searchPattern)}&x=0&y=0&submit=submit')
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG(f"KinoGer.getLinksForVideo [{cItem}]")
        linksTab = []
        if cItem.get('Episode'):
            data = re.compile(r"(http[^']+)", re.DOTALL).findall(str(cItem['Episode']))
        else:
            sts, data = self.getPage(cItem['url'], self.defaultParams)
            if not sts:
                return []
            data = re.compile(r"show[^>]\d,[^>][^>]'([^']+)", re.DOTALL).findall(data)

        for url in data:
            title = self.up.getHostName(url)
            linksTab.append({'name': title.capitalize(), 'url': strwithmeta(url, {'Referer': self.getMainUrl()}), 'need_resolve': 1})
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG(f"KinoGer.getVideoLinks [{videoUrl}]")

        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG(f"KinoGer.getArticleContent cItem[{cItem}]")
        otherInfo = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'description" content="([^"]+)')[0])
        desc = desc if desc else cItem.get('desc', '')
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r">Schauspieler:([^<]+)")[0])
        if actors:
            otherInfo['actors'] = actors
        d = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'>Regie:([^<]+)')[0])
        if d:
            otherInfo['director'] = d
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'>Spielzeit:([^<]+)')[0])
        if duration:
            otherInfo['duration'] = duration
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG(f"handleService: |||||||||||||||||||||||||||||||||||| name[{name}], category[{category}] ")
        self.currList = []

    # MAIN MENU
        if name is None and not category:
            self.listMainMenu({'name': 'category', 'type': 'category'})
        elif 'list_items' == category:
            self.listItems(self.currItem, 'video')
        elif 'list_seasons' == category:
            self.listSeasons(self.currItem)
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_genres' == category:
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, KinoGer(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
