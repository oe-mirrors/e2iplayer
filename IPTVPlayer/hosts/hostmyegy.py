# -*- coding: utf-8 -*-
# Last modified: 21/12/2025
# Myegy Host (Modified By Mohamed Elsafty)
# ===================== Standard library =====================
import re
try:
    from urllib.parse import urlparse, urlunparse
except ImportError:
    from urlparse import urlparse, urlunparse
# ===================== IPTVPlayer =====================
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
# ===================== COLORS =====================
Y = E2ColoR('yellow')
W = E2ColoR('white')
# ======================================================


def GetConfigList():
    return []


def gettytul():
    return 'https://myyegy.com/'


class MyYegy(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Myegy', 'cookie': 'Myegy.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + '?s='
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2025/11/cropped-favicon-238x238.png"
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        printDBG("Myegy.getPage [%s]" % base_url)
        if base_url and any(ord(c) > 127 for c in base_url):
            parts = list(urlparse(base_url))
            parts[2] = urllib_quote_plus(parts[2], safe='/')
            parts[4] = urllib_quote_plus(parts[4], safe='=&?')
            base_url = urlunparse(parts)
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("Myegy.getLinksForVideo [%s]" % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'Myegy - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("Myegy.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        printDBG('Myegy.listMainMenu')
        MAIN_CAT = [
            {'category': 'sub_folder', 'title': 'الأفلام', 'tab_id': 'MOVIES'},
            {'category': 'sub_folder', 'title': 'المسلسلات', 'tab_id': 'SERIES'},
            {'category': 'sub_folder', 'title': 'الأنمي', 'tab_id': 'ANIME'},
            {'category': 'list_items', 'title': 'عروض المصارعة', 'cat_id': 8198},
            {'category': 'list_items', 'title': 'برامج تلفزيونية', 'cat_id': 8178},
            {'category': 'list_items', 'title': 'عروض وحفلات', 'cat_id': 11471},
            {'category': 'list_items', 'title': 'غير مصنف', 'cat_id': 1},
            {'category': 'list_items', 'title': 'المضاف حديثا', 'cat_id': None},
            {'category': 'list_trending', 'title': 'التريند'},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT, cItem)

    def listSubFolder(self, cItem):
        tab_id = cItem.get('tab_id')
        tabs = {
            'MOVIES': [
                {'category': 'list_items', 'title': 'أفلام أجنبي', 'cat_id': 22},
                {'category': 'list_items', 'title': 'أفلام أجنبية مدبلجة', 'cat_id': 11153},
                {'category': 'list_items', 'title': 'أفلام آسيوي', 'cat_id': 2267},
                {'category': 'list_items', 'title': 'أفلام آسيوية مدبلجة', 'cat_id': 11132},
                {'category': 'list_items', 'title': 'أفلام تركية', 'cat_id': 11423},
                {'category': 'list_items', 'title': 'أفلام عربي', 'cat_id': 8164},
                {'category': 'list_items', 'title': 'أفلام هندي', 'cat_id': 8156},
                {'category': 'list_items', 'title': 'أفلام هندية', 'cat_id': 11404},
                {'category': 'list_items', 'title': 'أفلام وثائقية', 'cat_id': 11143},
            ],
            'SERIES': [
                {'category': 'list_items', 'title': 'مسلسلات اجنبي', 'cat_id': 2},
                {'category': 'list_items', 'title': 'مسلسلات اجنبي مدبلجة', 'cat_id': 11164},
                {'category': 'list_items', 'title': 'مسلسلات اسيوية', 'cat_id': 47},
                {'category': 'list_items', 'title': 'مسلسلات تركية', 'cat_id': 8129},
                {'category': 'list_items', 'title': 'مسلسلات عربية', 'cat_id': 8182},
                {'category': 'list_items', 'title': 'مسلسلات تركيه مدبلجة', 'cat_id': 10835},
                {'category': 'list_items', 'title': 'مسلسلات مدبلجة', 'cat_id': 8186},
                {'category': 'list_items', 'title': 'مسلسلات هندية', 'cat_id': 10520},
                {'category': 'list_items', 'title': 'مسلسلات لاتينية', 'cat_id': 10530},
                {'category': 'list_items', 'title': 'مسلسلات وثائقية', 'cat_id': 11012},
            ],
            'ANIME': [
                {'category': 'list_items', 'title': 'أفلام أنمي', 'cat_id': 3731},
                {'category': 'list_items', 'title': 'أفلام كرتون', 'cat_id': 11145},
                {'category': 'list_items', 'title': 'مسلسلات كرتون', 'cat_id': 10747},
                {'category': 'list_items', 'title': 'مسلسلات أنمي', 'cat_id': 75},
            ]
        }
        self.listsTab(tabs.get(tab_id, []), cItem)

    def getCategoryIdBySlug(self, slug):
        url = "%swp-json/wp/v2/categories?slug=%s" % (self.MAIN_URL, slug)
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("Cannot fetch category id for slug: %s" % slug)
            return None
        try:
            j = json_loads(data)
            if isinstance(j, list) and len(j) > 0:
                return j[0].get('id')
        except Exception as e:
            printDBG("getCategoryIdBySlug JSON error: %s" % e)
        return None

    def _cleanTitle(self, title):
        if not title:
            return ""
        title = self.cleanHtmlStr(title).replace('[', '(').replace(']', ')')
        while True:
            new_title = re.sub(r'^\s*(تحميل|مشاهدة|و|تحميل ومشاهدة|مشاهدة وتحميل)\s*', '', title, flags=re.IGNORECASE).strip()
            if new_title == title:
                break
            title = new_title
        title = re.sub(r'(مترجم[هة]?|مدبلج[هة]?)\s*.*$', r'\1', title, flags=re.IGNORECASE)
        patterns = [r'\s*نسخ[هة]\s*حصر[يياأآ]+\s*\s*', r'\s*حصر[يياأآ]+\s*ًا\s*', r'\s*نسخ[هة]\s*حصر[يياأآ]*\s*']
        for p in patterns:
            title = re.sub(p, ' ', title, flags=re.IGNORECASE)
        return re.sub(r'\s{2,}', ' ', title).strip()

    def listItems(self, cItem):
        printDBG("Myegy.listItems >>>>")
        page = cItem.get('page', 1)
        per_page = 20
        current_url = cItem.get('url', '')
        if current_url and '?s=' in current_url:
            params = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
            sts, data = self.cm.getPage(current_url, params)
            if not sts or not data:
                return
            cards_container = re.search(r'<div class="cards-container">(.*?)</div>\s*<!-- close cards-grid -->', data, re.DOTALL)
            if cards_container:
                cards_html = cards_container.group(1)
                card_pattern = r'<div class="card[^>]*>.*?<a href="([^"]+)"[^>]*title="([^"]*)".*?<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?>.*?<div class="title">([^<]+)</div>.*?</div>'
                matches = re.findall(card_pattern, cards_html, re.DOTALL)
                for link, title_attr, icon, alt_attr, title_text in matches:
                    title = self._cleanTitle(title_text.strip())
                    clean_icon = self.cm.getFullUrl(icon)
                    if clean_icon:
                        try:
                            parsed_url = urlparse(clean_icon)
                            encoded_path = urllib_quote_plus(parsed_url.path, safe='/')
                            clean_icon = urlunparse(parsed_url._replace(path=encoded_path))
                        except Exception:
                            printExc()
                    description = ""
                    if title_attr:
                        description = self.cleanHtmlStr(title_attr)
                    elif alt_attr:
                        description = self.cleanHtmlStr(alt_attr)
                    else:
                        description = title
                    self.addDir({'title': title, 'desc': description, 'icon': clean_icon, 'url': link, 'category': 'explore_item', 'good_for_fav': True})
            next_pg = re.search(r'<a[^>]+class="nextpostslink"[^>]+href="([^"]+)"', data)
            if next_pg:
                self.addDir({'title': Y + "▶ NEXT عرض المزيد" + W, 'url': self.cm.getFullUrl(next_pg.group(1)), 'category': 'list_items'})
        else:
            cat_id = cItem.get('cat_id') or (self.getCategoryIdBySlug(cItem.get('slug')) if cItem.get('slug') else None)
            if cat_id:
                api_url = "%swp-json/wp/v2/posts?categories=%s&per_page=%s&page=%s&_embed" % (self.MAIN_URL, cat_id, per_page, page)
            else:
                api_url = "%swp-json/wp/v2/posts?orderby=date&per_page=%s&page=%s&_embed" % (self.MAIN_URL, per_page, page)
            sts, data = self.getPage(api_url)
            if not sts:
                return
            try:
                posts = json_loads(data)
                for post in posts:
                    title = post.get("title", {}).get("rendered", "No Title")
                    icon = (post.get('jetpack_featured_media_url') or
                            (post.get('_embedded', {}).get('wp:featuredmedia', [{}])[0].get('source_url')) or "")
                    desc = self.cleanHtmlStr(post.get("excerpt", {}).get("rendered", ""))
                    if icon:
                        try:
                            p = list(urlparse(icon))
                            p[2] = urllib_quote_plus(p[2], safe='/')
                            icon = urlunparse(p)
                        except Exception:
                            icon = urllib_quote_plus(icon, safe=':/%#?=&')
                    self.addDir({'title': self._cleanTitle(title), 'desc': desc, 'icon': icon, 'url': post.get('link'), 'category': 'explore_item', 'good_for_fav': True})
                if len(posts) == per_page:
                    self.addDir({'title': Y + "▶ NEXT عرض المزيد" + W, 'page': page + 1, 'url': current_url, 'category': 'list_items', 'cat_id': cat_id})
            except Exception:
                printExc()

    def exploreItems(self, cItem):
        printDBG('Myegy.exploreItems [%s]' % cItem['url'])
        params = {
            'header': {k: v for k, v in self.HEADER.items() if k != 'Accept-Encoding'},
            'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE
        }
        sts, data = self.cm.getPage(cItem['url'], params)
        if not sts or not data:
            self.addDir({'title': 'Failed to load page', 'category': 'none'})
            return
        clean_title = self._cleanTitle(cItem.get('title', 'Video'))
        if not cItem.get('from_episodes_list'):
            seasons_section = re.search(r'<div class="seasons-episodes-section">(.*?)</div>\s*</div>', data, re.DOTALL)
            if seasons_section:
                eps_matches = re.findall(r'<a href="([^"]+)"[^>]*>\s*<span class="ep-number">([^<]+)</span>', seasons_section.group(1), re.DOTALL)
                if eps_matches:
                    episodes_list = [{'title': t.strip(), 'url': self.cm.getFullUrl(u)} for u, t in eps_matches]
                    params2 = dict(cItem)
                    params2.update({'category': 'list_episodes', 'title': 'المواسم والحلقات', 'episodes_list': episodes_list})
                    self.addDir(params2)
        servers_found = False
        servers_section = re.search(r'<div class="server-list"[^>]*>(.*?)</div>', data, re.DOTALL)
        if servers_section:
            servers = re.findall(r'<button[^>]+data-src="([^"]+)"[^>]*>([^<]+)</button>', servers_section.group(1))
            for link, name in servers:
                servers_found = True
                srv_name = self.cleanHtmlStr(name)
                full_url = self.cm.getFullUrl(link)
                quality = ""
                quality_match = re.search(r'(\d+p)', srv_name, re.IGNORECASE)
                if quality_match:
                    quality = " %s" % quality_match.group(1)
                final_title = "%s [ %s ]%s" % (clean_title, srv_name, quality)
                self.addVideo({'title': final_title, 'url': strwithmeta(full_url, {'Referer': cItem['url'], 'Origin': self.up.getDomain(full_url)}), 'need_resolve': 1})
        if not servers_found:
            iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', data)
            for iframe in iframes:
                full_url = self.cm.getFullUrl(iframe)
                host_name = self.up.getHostName(full_url)
                self.addVideo({'title': "%s [ %s ]" % (clean_title, host_name), 'url': strwithmeta(full_url, {'Referer': cItem['url']}), 'need_resolve': 1})

    def listEpisodes(self, cItem):
        printDBG("Myegy.listEpisodes >>>>")
        episodes = cItem.get('episodes_list', [])
        for ep in episodes:
            params = {'title': ep['title'], 'url': ep['url'], 'category': 'explore_item', 'good_for_fav': True, 'from_episodes_list': True}
            self.addDir(params)

    def exploreSeriesItems(self, cItem):
        printDBG('Myegy.exploreSeriesItems [%s]' % cItem['url'])
        self.exploreItems(cItem)

    def listTrending(self, cItem):
        url = "https://myyegy.com/trends/"
        sts, data = self.getPage(url)
        if not sts:
            return
        items = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', 'class="card'), ('</div>', '>'))
        for item in items:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', '</div>')[1]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="category">', '</div>')[1])
            img = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if img:
                try:
                    p = list(urlparse(img))
                    p[2] = urllib_quote_plus(p[2], safe='/')
                    img = urlunparse(p)
                except Exception:
                    printExc()
            self.addDir({'title': self._cleanTitle(title), 'desc': desc if desc else self._cleanTitle(title), 'url': url, 'icon': img, 'category': 'explore_item'})

    def getArticleContent(self, cItem):
        printDBG('Myegy.getArticleContent [%s]' % cItem)
        simple_header = dict(self.HEADER)
        if 'Accept-Encoding' in simple_header:
            del simple_header['Accept-Encoding']
        params = {'header': simple_header, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        sts, data = self.cm.getPage(cItem['url'], params)
        if not sts or not data:
            return []
        story_text = ""
        story_match = re.search(r'<div[^>]*class=["\']movie-story["\'][^>]*>(.*?)</div>', data, re.DOTALL)
        if story_match:
            story_text = self.cleanHtmlStr(story_match.group(1)).strip()
        meta_info = {}
        info_match = re.search(r'<div[^>]*class=["\']info-box["\'][^>]*>(.*?)</div>', data, re.DOTALL)
        if info_match:
            info_html = info_match.group(1)
            parts = re.split(r'(<span[^>]*class=["\']info-title["\'][^>]*>[^<]+?</span>)', info_html)
            current_label = None
            for part in parts:
                if 'info-title' in part:
                    lbl_match = re.search(r'<span[^>]*class=["\']info-title["\'][^>]*>([^:<]+):?\s*</span>', part)
                    if lbl_match:
                        current_label = lbl_match.group(1).strip()
                        meta_info[current_label] = []
                elif current_label:
                    values = re.findall(r'<span[^>]*class=["\']tag["\'][^>]*>.*?<a[^>]*>([^<]+)</a>', part)
                    clean_vals = [v.strip() for v in values if v.strip()]
                    meta_info[current_label].extend(clean_vals)
        full_desc = ""
        extra_info = ""
        if story_text:
            full_desc = Y + "القصة :" + W + " " + story_text
        if meta_info:
            desired_order = ["سنة الإصدار", "التصنيف", "الجودة", "اللغة", "الدولة", "الممثلين"]
            details_list = []
            for key in desired_order:
                if key in meta_info and meta_info[key]:
                    value_str = "، ".join(meta_info[key])
                    details_list.append(Y + key + " :" + W + " " + value_str)
            if details_list:
                extra_info = "\n\n" + " | ".join(details_list)
        final_text = full_desc + extra_info
        icon = cItem.get('icon', '')
        poster_match = re.search(r'<div class="movie-poster">\s*<img src="([^"]+)"', data)
        if poster_match:
            icon = self.cm.getFullUrl(poster_match.group(1))
        otherInfo = {}
        return [{"title": cItem.get("title", "Information"), "text": final_text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Myegy.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG('Myegy.getFavouriteData')
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('Myegy.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('Myegy.setInitListFromFavouriteItem')
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("type", "")
        self.currList = []
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'sub_folder':
            self.listSubFolder(self.currItem)
        elif category == 'list_trending':
            self.listTrending(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        elif mode == 'video' or self.currItem.get('need_resolve'):
            pass
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MyYegy(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
