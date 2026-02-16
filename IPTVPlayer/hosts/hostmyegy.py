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
Y = E2ColoR("yellow")
W = E2ColoR("white")


# ======================================================
def GetConfigList():
    return []


def gettytul():
    return "https://myigy.online/"


class MyYegy(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Myegy", "cookie": "Myegy.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "search.php?keywords="
        self.DEFAULT_ICON_URL = gettytul() + "uploads/custom-logo.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        printDBG("Myegy.getPage [%s]" % base_url)
        if base_url and any(ord(c) > 127 for c in base_url):
            parts = list(urlparse(base_url))
            parts[2] = urllib_quote_plus(parts[2], safe="/")
            parts[4] = urllib_quote_plus(parts[4], safe="=&?")
            base_url = urlunparse(parts)
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("Myegy.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "Myegy - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("Myegy.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        printDBG("Myegy.listMainMenu")
        MAIN_CAT = [
            {"category": "sub_folder", "title": "المسلسلات", "tab_id": "SERIES"},
            {"category": "sub_folder", "title": "الأفلام", "tab_id": "MOVIES"},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT, cItem)

    def listSubFolder(self, cItem):
        tab_id = cItem.get("tab_id")
        tabs = {
            "SERIES": [
                {"category": "list_items", "title": "كل المسلسلات", "url": self.MAIN_URL + "category.php?cat=mslslat", "icon": self.MAIN_URL + "uploads/thumbs/be81557d06c7a.jpg"},
                {"category": "list_items", "title": "مسلسلات اجنبي", "url": self.MAIN_URL + "category.php?cat=mslslat-ajnbyh", "icon": self.MAIN_URL + "uploads/thumbs/7dadcd71536a9.jpg"},
                {"category": "list_items", "title": "مسلسلات عربي", "url": self.MAIN_URL + "category.php?cat=mslslat-arby", "icon": self.MAIN_URL + "uploads/thumbs/be81557d06c7a.jpg"},
                {"category": "list_items", "title": "مسلسلات كورية", "url": self.MAIN_URL + "category.php?cat=mslslat-kwryh", "icon": self.MAIN_URL + "uploads/thumbs/76c27da37535d.jpg"},
                {"category": "list_items", "title": "مسلسلات تركية", "url": self.MAIN_URL + "category.php?cat=mslslat-trkyh", "icon": self.MAIN_URL + "uploads/thumbs/35ebb181ecc2c.jpg"},
                {"category": "list_items", "title": "مسلسلات انمي", "url": self.MAIN_URL + "category.php?cat=mslslat-anmy", "icon": self.MAIN_URL + "uploads/thumbs/3da6320ddeb52.jpg"},
                {
                    "category": "list_items",
                    "title": "أحدث الحلقات",
                    "url": self.MAIN_URL + "episodes.php",
                },
                {
                    "category": "list_items",
                    "title": "أحدث المسلسلات",
                    "url": self.MAIN_URL + "all-series.php",
                },
                {
                    "category": "list_items",
                    "title": "الجديد",
                    "url": self.MAIN_URL + "newvideos.php",
                },
            ],
            "MOVIES": [
                {"category": "list_items", "title": "أفلام عربية", "url": self.MAIN_URL + "category.php?cat=aflam-arby", "icon": self.MAIN_URL + "uploads/thumbs/63c01feef1d47.jpg"},
                {"category": "list_items", "title": "أفلام مغامرة", "url": self.MAIN_URL + "category.php?cat=aflam-mghamrh", "icon": self.MAIN_URL + "uploads/thumbs/22b6dd5d3592a.jpg"},
                {"category": "list_items", "title": "سلاسل أفلام", "url": self.MAIN_URL + "category.php?cat=slasl-aflam", "icon": self.MAIN_URL + "uploads/thumbs/3769afde8bae5.jpg"},
                {"category": "list_items", "title": "أفلام غموض", "url": self.MAIN_URL + "category.php?cat=aflam-ghmwd", "icon": self.MAIN_URL + "uploads/thumbs/1c97a3861fa17.jpg"},
                {"category": "list_items", "title": "أفلام خيال علمي", "url": self.MAIN_URL + "category.php?cat=aflam-khyal-almy", "icon": self.MAIN_URL + "uploads/thumbs/c313f47971925.jpg"},
                {"category": "list_items", "title": "أفلام كوميدي", "url": self.MAIN_URL + "category.php?cat=aflam-kwmydy", "icon": self.MAIN_URL + "uploads/thumbs/9e5a950e9628d.jpg"},
                {"category": "list_items", "title": "أفلام 2026", "url": self.MAIN_URL + "category.php?cat=aflam-2026", "icon": self.MAIN_URL + "uploads/thumbs/616a7d0dd4b47.jpg"},
                {"category": "list_items", "title": "أفلام 2025", "url": self.MAIN_URL + "category.php?cat=aflam-2025", "icon": self.MAIN_URL + "uploads/thumbs/dfff689122cc7.jpg"},
                {"category": "list_items", "title": "أفلام 2024", "url": self.MAIN_URL + "category.php?cat=aflam-2024", "icon": self.MAIN_URL + "uploads/thumbs/ad1a529ba94cc.jpg"},
                {"category": "list_items", "title": "أفلام 2023", "url": self.MAIN_URL + "category.php?cat=aflam-2023", "icon": self.MAIN_URL + "uploads/thumbs/9be801bc95dc6.jpg"},
                {"category": "list_items", "title": "أفلام أكشن", "url": self.MAIN_URL + "category.php?cat=aflam-akshn", "icon": self.MAIN_URL + "uploads/thumbs/455b46bfd90d0.jpg"},
                {"category": "list_items", "title": "أفلام رعب", "url": self.MAIN_URL + "category.php?cat=aflam-rab", "icon": self.MAIN_URL + "uploads/thumbs/cdfab7df6f641.jpg"},
                {"category": "list_items", "title": "أفلام حرب", "url": self.MAIN_URL + "category.php?cat=aflam-hrb", "icon": self.MAIN_URL + "uploads/thumbs/455b46bfd90d0.jpg"},
                {"category": "list_items", "title": "أفلام دراما", "url": self.MAIN_URL + "category.php?cat=aflam-drama", "icon": self.MAIN_URL + "uploads/thumbs/9e5a950e9628d.jpg"},
                {"category": "list_items", "title": "أفلام فانتازيا", "url": self.MAIN_URL + "category.php?cat=aflam-fantazya", "icon": self.MAIN_URL + "uploads/thumbs/dfff689122cc7.jpg"},
                {"category": "list_items", "title": "أفلام إثارة", "url": self.MAIN_URL + "category.php?cat=aflam-atharh", "icon": self.MAIN_URL + "uploads/thumbs/2b98d0de29177.jpg"},
                {"category": "list_items", "title": "أفلام أجنبية", "url": self.MAIN_URL + "category.php?cat=aflam-ajnby", "icon": self.MAIN_URL + "uploads/thumbs/9e5a950e9628d.jpg"},
                {"category": "list_items", "title": "أفلام غربية", "url": self.MAIN_URL + "category.php?cat=aflam-ghrby", "icon": self.MAIN_URL + "uploads/thumbs/581c1a76f72c4.jpg"},
                {"category": "list_items", "title": "أفلام هندية", "url": self.MAIN_URL + "category.php?cat=aflam-hndy", "icon": self.MAIN_URL + "uploads/thumbs/f801404a37fae.jpg"},
                {"category": "list_items", "title": "أفلام كورية", "url": self.MAIN_URL + "category.php?cat=aflam-kwryh", "icon": self.MAIN_URL + "uploads/thumbs/22b6dd5d3592a.jpg"},
                {"category": "list_items", "title": "أفلام تركية", "url": self.MAIN_URL + "category.php?cat=aflam-trkyh", "icon": self.MAIN_URL + "uploads/thumbs/9307e0a6feea9.jpg"},
                {"category": "list_items", "title": "أفلام جريمة", "url": self.MAIN_URL + "category.php?cat=aflam-jrymh", "icon": self.MAIN_URL + "uploads/thumbs/2b98d0de29177.jpg"},
                {"category": "list_items", "title": "أفلام رومانسية", "url": self.MAIN_URL + "category.php?cat=aflam-rwmansyh", "icon": self.MAIN_URL + "uploads/thumbs/9e5a950e9628d.jpg"},
                {"category": "list_items", "title": "أفلام للكبار فقط", "url": self.MAIN_URL + "category.php?cat=aflam-llkbar-fqt", "icon": self.MAIN_URL + "uploads/thumbs/3061ebc101d86.jpg"},
                {"category": "list_items", "title": "أفلام تاريخية", "url": self.MAIN_URL + "category.php?cat=aflam-tarykhyh", "icon": self.MAIN_URL + "uploads/thumbs/27959524ccdd7.jpg"},
                {"category": "list_items", "title": "أفلام موسيقى", "url": self.MAIN_URL + "category.php?cat=aflam-mwsyqa", "icon": self.MAIN_URL + "uploads/thumbs/dfff689122cc7.jpg"},
                {"category": "list_items", "title": "أفلام سيرة ذاتية", "url": self.MAIN_URL + "category.php?cat=aflam-syrh-thatyh", "icon": self.MAIN_URL + "uploads/thumbs/27959524ccdd7.jpg"},
                {"category": "list_items", "title": "أفلام عائلية", "url": self.MAIN_URL + "category.php?cat=aflam-aaylyh", "icon": self.MAIN_URL + "uploads/thumbs/dfff689122cc7.jpg"},
                {"category": "list_items", "title": "أفلام رياضة", "url": self.MAIN_URL + "category.php?cat=aflam-ryadh", "icon": self.MAIN_URL + "uploads/thumbs/9e5a950e9628d.jpg"},
                {"category": "list_items", "title": "أفلام أنمي وكرتون", "url": self.MAIN_URL + "category.php?cat=aflam-anmy-wkartwn", "icon": self.MAIN_URL + "uploads/thumbs/22b6dd5d3592a.jpg"},
                {
                    "category": "list_items",
                    "title": "أحدث الأفلام",
                    "url": self.MAIN_URL + "movies.php",
                },
            ],
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
                return j[0].get("id")
        except Exception as e:
            printDBG("getCategoryIdBySlug JSON error: %s" % e)
        return None

    def _cleanTitle(self, title):
        if not title:
            return ""
        title = self.cleanHtmlStr(title).replace("[", "(").replace("]", ")")
        while True:
            new_title = re.sub(r"^\s*(تحميل|مشاهدة|و|تحميل ومشاهدة|مشاهدة وتحميل)\s*", "", title, flags=re.IGNORECASE).strip()
            if new_title == title:
                break
            title = new_title
        title = re.sub(r"(مترجم[هة]?|مدبلج[هة]?)\s*.*$", r"\1", title, flags=re.IGNORECASE)
        patterns = [r"\s*نسخ[هة]\s*حصر[يياأآ]+\s*\s*", r"\s*حصر[يياأآ]+\s*ًا\s*", r"\s*نسخ[هة]\s*حصر[يياأآ]*\s*"]
        for p in patterns:
            title = re.sub(p, " ", title, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", title).strip()

    def listItems(self, cItem):
        printDBG("Myegy.listItems >>>>")
        url = cItem.get("url")
        if not url:
            return
        page = int(cItem.get("page", 1))
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        blocks = re.findall(r'<div\s+class="video-card-inner">(.*?)</div>\s*</div>\s*</div>', data, re.DOTALL)
        for item in blocks:
            link = self.cm.ph.getSearchGroups(item, r'href="([^"]+watch\.php\?vid=[^"]+)"')[0]
            title_match = re.search(r'title="([^"]+)"', item)
            title = title_match.group(1) if title_match else ""
            img_match = re.search(r'data-src="([^"]+\.jpg)"', item)
            img = img_match.group(1) if img_match else ""
            if not img:
                img_match = re.search(r'src="([^"]+uploads/thumbs/[^"]+\.jpg)"', item)
                img = img_match.group(1) if img_match else ""
            duration = ""
            meta_match = re.search(r'<div\s+class="video-meta">(.*?)</div>', item, re.DOTALL)
            if meta_match:
                meta_content = meta_match.group(1)
                duration_match = re.search(r"<span[^>]*>(.*?)</span>", meta_content)
                if duration_match:
                    duration = duration_match.group(1).strip()
            if not duration:
                duration_match = re.search(r'<i\s+class="[^"]*fa-clock[^"]*"[^>]*></i>\s*<span[^>]*>(.*?)</span>', item)
                duration = duration_match.group(1).strip() if duration_match else ""
            if not link or not title:
                continue
            desc = "مدة العرض: " + duration if duration else "مدة العرض غير متوفرة"
            icon = self.cm.getFullUrl(img)
            self.addDir({"title": self._cleanTitle(title), "url": self.cm.getFullUrl(link), "icon": icon, "desc": Y + desc + W, "category": "explore_item", "good_for_fav": True})
        # ===== pagination =====
        next_page = page + 1
        baseUrl = url.split("&page=")[0] if "&page=" in url else url
        sep = "&" if "?" in baseUrl else "?"
        next_url = f"{baseUrl}{sep}page={next_page}&order=DESC"
        self.addDir({"title": Y + _("Next Page") + " ▶▶▶" + W, "url": next_url, "category": "list_items", "page": next_page})

    def _extractSeasonsAndEpisodes(self, data):
        """
        استخراج المواسم والحلقات من صفحة المسلسل
        """
        seasons = []
        episodes_section = re.search(r'<div\s+class="modern-watch-layout">.*?<div\s+class="modern-classic-episodes">(.*?)</div>\s*</div>', data, re.DOTALL)
        if not episodes_section:
            return seasons
        episodes_content = episodes_section.group(1)
        season_tabs = re.findall(r'<button\s+class="season-tab[^"]*"[^>]*onclick="openSeason\(event, \'([^\']+)\'"[^>]*>.*?<span>([^<]*)</span>', episodes_content)
        for season_id, season_name in season_tabs:
            season_panel = re.search(r'<div\s+id="' + re.escape(season_id) + r'"\s+class="[^"]*season-panel[^"]*">(.*?)</div>', episodes_content, re.DOTALL)
            if not season_panel:
                continue
            episodes = []
            episodes_html = season_panel.group(1)
            episode_items = re.findall(r'<a\s+href="([^"]+watch\.php\?vid=[^"]+)"[^>]*class="[^"]*classic-episode-item[^"]*"[^>]*>.*?<div\s+class="episode-number-large">(\d+)</div>.*?<div\s+class="episode-label">([^<]*)</div>', episodes_html, re.DOTALL)
            for episode_url, episode_num, episode_label in episode_items:
                episodes.append({"url": self.cm.getFullUrl(episode_url), "title": f"{episode_label} {episode_num}", "num": episode_num})
            if not season_name:
                season_name = f"الموسم {len(seasons) + 1}"
            seasons.append({"id": season_id, "name": season_name, "episodes": episodes})
        if not seasons:
            episodes_html = re.search(r'<div\s+class="episodes-grid-classic[^"]*">(.*?)</div>', episodes_content, re.DOTALL)
            if episodes_html:
                episodes = []
                episode_items = re.findall(r'<a\s+href="([^"]+watch\.php\?vid=[^"]+)"[^>]*class="[^"]*classic-episode-item[^"]*"[^>]*>.*?<div\s+class="episode-number-large">(\d+)</div>.*?<div\s+class="episode-label">([^<]*)</div>', episodes_html.group(1), re.DOTALL)
                for episode_url, episode_num, episode_label in episode_items:
                    episodes.append({"url": self.cm.getFullUrl(episode_url), "title": f"{episode_label} {episode_num}", "num": episode_num})
                if episodes:
                    seasons.append({"id": "season-0", "name": "الموسم 1", "episodes": episodes})
        return seasons

    def exploreItems(self, cItem):
        printDBG("Myegy.exploreItems [%s]" % cItem["url"])
        url = cItem["url"].replace("watch.php", "view.php")
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        icon = cItem.get("icon", "")
        series_title = self._cleanTitle(cItem.get("title", "Video"))
        seasons_found = False
        if not cItem.get("from_episodes_list"):
            season_tabs = re.findall(r'onclick="openSeason\(event,\s*\'(season-(\d+))\'\)"[^>]*>.*?<span>(.*?)</span>', data, re.DOTALL)
            if season_tabs:
                self.addMarker({"title": f"{Y}المواسم والحلقات{W}", "icon": icon})
                for season_id, season_num, season_name in season_tabs:
                    panel_pattern = r'id="%s"[\s\S]*?>([\s\S]*?)(?=<div id="season-|\s*</div>\s*</div>\s*</div>)' % re.escape(season_id)
                    panel_match = re.search(panel_pattern, data)
                    if panel_match:
                        episodes_html = panel_match.group(1)
                        episode_items = re.findall(r'href="(watch\.php\?vid=[^"]+)"[^>]*>[\s\S]*?episode-number-large[^>]*>\s*(\d+)\s*</div>[\s\S]*?episode-label[^>]*>([^<]+)</div>', episodes_html)
                        if episode_items:
                            seasons_found = True
                            episodes_list = []
                            for ep_url, ep_num, ep_label in episode_items:
                                episodes_list.append({"url": self.getFullUrl(ep_url), "title": "%s %s" % (ep_label.strip(), ep_num), "num": ep_num})
                            s_name = season_name.strip()
                            if not s_name:
                                display_num = str(int(season_num) + 1)
                                s_title = "الموسم %s" % display_num
                            else:
                                s_title = s_name
                            self.addDir({"category": "list_episodes", "title": s_title, "url": url, "icon": icon, "episodes_list": episodes_list})
        if not seasons_found:
            printDBG("Showing servers directly...")
            self.addMarker({"title": f"{Y}سيرفرات المشاهدة{W}", "icon": icon})
            servers = re.findall(r'data-embed="([^"]+)"[^>]*>.*?<span>([^<]+)</span>', data, re.DOTALL)
            for embed_link, srv_name in servers:
                host_name = self.up.getHostName(embed_link)
                self.addVideo({"title": "%s [%s] - %s" % (series_title, srv_name.strip(), host_name), "url": strwithmeta(self.getFullUrl(embed_link), {"Referer": url}), "icon": icon, "need_resolve": 1})

    def listEpisodes(self, cItem):
        printDBG("Myegy.listEpisodes >>>>")
        episodes = cItem.get("episodes_list", [])
        self.addMarker({"title": f"{Y}قائمة الحلقات{W}", "icon": cItem.get("icon", "")})
        for ep in episodes:
            params = {"category": "explore_item", "title": ep["title"], "url": ep["url"], "icon": cItem.get("icon", ""), "from_episodes_list": True, "good_for_fav": True}
            self.addDir(params)

    def getArticleContent(self, cItem):
        printDBG("Myegy.getArticleContent [%s]" % cItem)
        simple_header = dict(self.HEADER)
        if "Accept-Encoding" in simple_header:
            del simple_header["Accept-Encoding"]
        params = {"header": simple_header, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        sts, data = self.cm.getPage(cItem["url"], params)
        if not sts or not data:
            return []
        # ---------------- القصة ----------------
        story_text = ""
        story_match = re.search(r'<div class="description-text[^"]*">(.*?)</div>', data, re.DOTALL)
        if story_match:
            story_text = self.cleanHtmlStr(story_match.group(1)).strip()
        # ---------------- مدة العرض ----------------
        duration = ""
        duration_match = re.search(r'<span class="total-time">\s*([^<]+)\s*</span>', data)
        if duration_match:
            duration = duration_match.group(1).strip()
        # ---------------- معلومات إضافية القديمة ----------------
        meta_info = {}
        info_match = re.search(r'<div[^>]*class=["\']info-box["\'][^>]*>(.*?)</div>', data, re.DOTALL)
        if info_match:
            info_html = info_match.group(1)
            parts = re.split(r'(<span[^>]*class=["\']info-title["\'][^>]*>[^<]+?</span>)', info_html)
            current_label = None
            for part in parts:
                if "info-title" in part:
                    lbl_match = re.search(r'<span[^>]*class=["\']info-title["\'][^>]*>([^:<]+):?\s*</span>', part)
                    if lbl_match:
                        current_label = lbl_match.group(1).strip()
                        meta_info[current_label] = []
                elif current_label:
                    values = re.findall(r'<span[^>]*class=["\']tag["\'][^>]*>.*?<a[^>]*>([^<]+)</a>', part)
                    clean_vals = [v.strip() for v in values if v.strip()]
                    meta_info[current_label].extend(clean_vals)
        # ---------------- بناء الوصف ----------------
        full_desc = ""
        extra_info = ""
        if duration:
            full_desc += Y + "مدة العرض :" + W + " " + duration + "\n\n"
        if story_text:
            full_desc += Y + "القصة :" + W + " " + story_text
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
        # ---------------- الصورة ----------------
        icon = cItem.get("icon", "")
        poster_match = re.search(r'<div class="movie-poster">\s*<img src="([^"]+)"', data)
        if poster_match:
            icon = self.cm.getFullUrl(poster_match.group(1))
        otherInfo = {}
        return [{"title": cItem.get("title", "Information"), "text": final_text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Myegy.listSearchResult searchPattern[%s]" % searchPattern)
        encoded_search = searchPattern.replace(" ", "+")
        url = self.SEARCH_URL + encoded_search + "&video-id="
        sts, data = self.getPage(url)
        if not sts:
            return
        blocks = re.findall(r'<div class="video-card">([\s\S]*?)</div>\s*</div>\s*</div>\s*</div>', data)
        for item in blocks:
            match = re.search(r'href="([^"]+watch\.php\?vid=[^"]+)"[\s\S]*?title="([^"]+)"', item)
            if not match:
                continue
            link = match.group(1)
            title = match.group(2)
            img = re.search(r'data-src="([^"]+)"', item)
            icon = self.getFullUrl(img.group(1)) if img else ""
            duration = re.search(r"fa-clock[\s\S]*?<span>\s*([\d:]+)\s*</span>", item)
            desc = f"{Y}مدة العرض: {duration.group(1)}{W}" if duration else ""
            self.addDir({"category": "explore_item", "title": self._cleanTitle(title), "url": self.getFullUrl(link), "icon": icon, "desc": desc, "good_for_fav": True})

    def getFavouriteData(self, cItem):
        printDBG("Myegy.getFavouriteData")
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("Myegy.getLinksForFavourite")
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("Myegy.setInitListFromFavouriteItem")
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        mode = self.currItem.get("type", "")
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "sub_folder":
            self.listSubFolder(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        elif mode == "video" or self.currItem.get("need_resolve"):
            pass
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MyYegy(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
