# -*- coding: utf-8 -*-
# Last modified: 19/04/2026
# Asi1TV Host (Modified By Mohamed Elsafty)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_quote

###################################################
# FOREIGN import
###################################################
import re
import time
import json

###################################################
Y = E2ColoR("yellow")
W = E2ColoR("white")
LB = E2ColoR("lightblue")
G = E2ColoR("green")
R = E2ColoR("red")


def GetConfigList():
    return []


def gettytul():
    return "https://asiatvdrama.com/"


class Asi1TV(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "asi1tv", "cookie": "asi1tv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://asiatvdrama.com/wp-content/uploads/2021/09/cropped-asiadrama-192x192.png"  # fallback icon
        self.SEARCH_URL = self.MAIN_URL + "?s="
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                sts, data = self.cm.getPage(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG("Asi1TV.getPage retry %d failed: %s" % (attempt + 1, str(e)))
            time.sleep(1.2)
        return False, ""

    def _fixUrl(self, url):
        if url:
            url = self.getFullUrl(url)
            if any(ord(c) > 127 for c in url):
                return urllib_quote(url.encode("utf-8"), safe=":/%?&=+@#,")
        return url

    def listMainMenu(self, cItem):
        printDBG("Asi1TV.listMainMenu")
        self.DRAMA_CAT_TAB = [
            {"category": "list_drama", "title": "الدراما الكورية", "url": self.getFullUrl("/types/الدراما-الكورية/")},
            {"category": "list_drama", "title": "الدراما الصينية", "url": self.getFullUrl("/types/الدراما-الصينية/")},
            {"category": "list_drama", "title": "الدراما التايلاندية", "url": self.getFullUrl("/types/الدراما-التايلندية/")},
            {"category": "list_drama", "title": "الدراما التايونية", "url": self.getFullUrl("/types/الدراما-التايونية/")},
            {"category": "list_drama", "title": "الدراما اليابانية", "url": self.getFullUrl("/types/الدراما-اليابانية/")},
        ]
        MAIN_CAT_TAB = [
            {"category": "list_items", "title": "الحلقات الجديدة", "url": self.getFullUrl("/الحلقات-الجديدة/")},
            {"category": "list_drama_menu", "title": "قائمة الدراما"},
            {"category": "list_items", "title": "افلام اسيوية", "url": self.getFullUrl("/types/افلام-اسيوية/")},
            {"category": "list_items", "title": "دراما تبث حاليا", "url": self.getFullUrl("/دراما-تبث-حاليا/")},
            {"category": "list_items", "title": "دراما مكتملة", "url": self.getFullUrl("/دراما-مكتملة/")},
            {"category": "list_items", "title": "الدراما الاكثر تقييما", "url": self.getFullUrl("/الدراما-الاكثر-تقييما/")},
            {"category": "list_items", "title": "قائمة الفنانين", "url": self.getFullUrl("/قائمة-الفنانين/")},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listDramaMenu(self, cItem):
        printDBG("Asi1TV.listDramaMenu")
        self.listsTab(self.DRAMA_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("Asi1TV.listItems [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        is_actor_list = '<div class="listActors">' in data
        if is_actor_list:
            actor_blocks = self.cm.ph.getDataBeetwenMarkers(data, '<div class="listActors">', "</div>", False)[1]
            if actor_blocks:
                actor_links = self.cm.ph.getAllItemsBeetwenMarkers(actor_blocks, "<a ", "</a>")
                if cItem.get("url", "").endswith("/قائمة-الفنانين/") or "/page/" not in cItem.get("url", ""):
                    all_list_title = Y + "All List A to Z" + W
                    all_list_desc = Y + "ترتيب أبجدي .. يرجي الانتظار لان تحميل قائمة الفنانين الكاملة تأخذ بعض الوقت ... يمكن تصفح القوائم بشكل أسرع" + W
                    self.addDir({"title": all_list_title, "desc": all_list_desc, "icon": self.DEFAULT_ICON_URL, "category": "list_all_actors", "url": "https://asiatvdrama.com/قائمة-الفنانين/", "type": "all_actors", "good_for_fav": True})
                for link in actor_links:
                    url = self.cm.ph.getSearchGroups(link, r'href="([^"]+)"')[0]
                    title = self.cm.ph.getSearchGroups(link, r"<h2>([^<]+)</h2>")[0].strip()
                    if not url or not title:
                        continue
                    icon = self.cm.ph.getSearchGroups(link, r'<img[^>]+src=["\']([^"\']+)[^>]*>')[0].strip()
                    icon = self._fixUrl(icon) if icon else self.DEFAULT_ICON_URL
                    params = dict(cItem)
                    params.update({"title": "%s%s%s" % (LB, title, W), "url": self.getFullUrl(url), "icon": icon, "desc": Y + _("Actor profile and Works") + W, "category": "explore_item", "good_for_fav": True})
                    self.addDir(params)
        else:
            items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="post">', "</article>")
            items += self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="postEp">', "</article>")
            printDBG("Asi1TV: Found %d items" % len(items))
            for item in items:
                url_match = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
                title_attr = self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
                if not url_match or not title_attr:
                    continue
                url = self.getFullUrl(url_match.strip())
                clean_title = self.cleanHtmlStr(title_attr)
                clean_title = re.sub(r"\s*تقرير\s*\+\s*حلقات\s*مترجمة", "", clean_title).strip()
                clean_title = re.sub(r"\s*تقرير\s*\+\s*حلقات\s*مترجمة", "", clean_title).strip()
                is_vip = '<div class="vip-ribbon">' in item
                if is_vip:
                    clean_title = "%s[ VIP ] - %s%s" % (Y, clean_title, W)
                icon = self.cm.ph.getSearchGroups(item, r'data-img="([^"]+)"')[0].strip()
                if not icon:
                    icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0].strip()
                icon = self._fixUrl(icon) if icon else self.DEFAULT_ICON_URL
                translate = ""
                sound = ""
                translate_block = self.cm.ph.getDataBeetwenMarkers(item, '<div class="translate">', "</div>", False)[1]
                if translate_block:
                    translate = self.cleanHtmlStr(translate_block).replace("الترجمة : ", "").strip()
                sound_block = self.cm.ph.getDataBeetwenMarkers(item, '<div class="sound">', "</div>", False)[1]
                if sound_block:
                    sound = self.cleanHtmlStr(sound_block).replace("الصوت : ", "").strip()
                episode_info = ""
                eps_block = self.cm.ph.getDataBeetwenMarkers(item, '<div class="eps">', "</div>", False)[1]
                if eps_block:
                    episode_info = self.cleanHtmlStr(eps_block).strip()
                section = ""
                genre = ""
                info_block = self.cm.ph.getDataBeetwenMarkers(item, '<div class="info">', "</article>", False)[1]
                if info_block:
                    raw_spans = re.findall(r"<span[^>]*>\s*<i[^>]*>.*?</i>\s*([^<]+)", info_block, re.DOTALL)
                    cleaned_parts = []
                    for raw_text in raw_spans:
                        clean_text = self.cleanHtmlStr(raw_text).strip()
                        if clean_text and clean_text not in cleaned_parts:
                            cleaned_parts.append(clean_text)
                    if len(cleaned_parts) >= 1:
                        section = cleaned_parts[0]
                    if len(cleaned_parts) >= 2:
                        genre = cleaned_parts[1]
                desc_lines = []
                fields = [
                    ("Translate", translate),
                    ("Sound", sound),
                    ("Episode", episode_info),
                    ("Section", section),
                    ("Type", genre),
                ]
                for label, value in fields:
                    if value:
                        desc_lines.append("%s%s :%s %s" % (Y, label, W, value))
                desc = "\n".join(desc_lines)
                params = dict(cItem)
                params.update({"title": clean_title, "url": url, "icon": icon, "desc": desc, "category": "explore_item", "good_for_fav": True})
                self.addDir(params)
        pagination_match = re.search(r'<ul\s+class=["\']page-numbers["\'][^>]*>(.*?)</ul>', data, re.DOTALL)
        pagination = pagination_match.group(1) if pagination_match else ""
        next_page_url = ""
        current_page = 1
        total_pages = 1
        if pagination:
            current_match = re.search(r'<span[^>]*class=["\'][^"\']*current[^"\']*["\'][^>]*>(\d+)</span>', pagination)
            if current_match:
                try:
                    current_page = int(current_match.group(1))
                except:
                    current_page = 1
            all_page_numbers = re.findall(r'<a[^>]+href=["\'][^"\']*page/(\d+)/?["\'][^>]*>([\d,٬]+)</a>', pagination)
            if all_page_numbers:
                last_num_str = all_page_numbers[-1][1]
                clean_num = last_num_str.replace(",", "").replace("٬", "")
                try:
                    total_pages = int(clean_num)
                except:
                    total_pages = current_page + 1
            else:
                total_pages = current_page + 1
            if current_page == 1:
                next_page_url = cItem["url"].rstrip("/") + "/page/2/"
            else:
                base_url = cItem["url"].rsplit("/page/", 1)[0]
                next_page_url = base_url + "/page/%d/" % (current_page + 1)
            if next_page_url:
                sts_next, data_next = self.getPage(next_page_url)
                has_items = False
                if sts_next and data_next:
                    if '<article class="post">' in data_next or '<article class="postEp">' in data_next or '<div class="listActors">' in data_next:
                        has_items = True
                if has_items:
                    pages_left = total_pages - current_page
                    next_title = Y + _("Next Page") + " ▶▶▶" + W
                    next_desc = Y + _("There are %d more pages in this section") % pages_left + W
                    params = dict(cItem)
                    params.update({"title": next_title, "desc": next_desc, "url": next_page_url, "category": cItem["category"]})
                    self.addDir(params)

    def listAllActors(self, cItem):
        printDBG("Asi1TV.listAllActors")
        base_url = "https://asiatvdrama.com/قائمة-الفنانين/"
        page = 1
        total_added = 0
        max_pages = 200
        while page <= max_pages:
            url = base_url if page == 1 else base_url + "page/%d/" % page
            sts, data = self.getPage(url)
            if not sts or not data:
                break
            if '<div class="listActors">' not in data:
                break
            actor_blocks = self.cm.ph.getDataBeetwenMarkers(data, '<div class="listActors">', "</div>", False)[1]
            if not actor_blocks:
                break
            actor_links = self.cm.ph.getAllItemsBeetwenMarkers(actor_blocks, "<a ", "</a>")
            if not actor_links:
                break
            for link in actor_links:
                url_actor = self.cm.ph.getSearchGroups(link, r'href="([^"]+)"')[0]
                title = self.cm.ph.getSearchGroups(link, r"<h2>([^<]+)</h2>")[0].strip()
                if not url_actor or not title:
                    continue
                icon = self.cm.ph.getSearchGroups(link, r'<img[^>]+src=["\']([^"\']+)[^>]*>')[0].strip()
                icon = self.getFullUrl(icon) if icon else self.DEFAULT_ICON_URL
                self.addDir({"title": "%s%s%s" % (LB, title, W), "url": self.getFullUrl(url_actor), "icon": icon, "desc": Y + _("Actor profile and Works") + W, "category": "explore_item", "good_for_fav": True})
                total_added += 1
            if '<a class="next page-numbers"' not in data:
                break
            page += 1
        printDBG("Asi1TV: Loaded %d actors from %d pages" % (total_added, page - 1))

    def exploreItem(self, cItem):
        printDBG("Asi1TV.exploreItem [%s]" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        url = cItem["url"]
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        if '<ul class="eplist2 list-eps">' in data or '<ul class="list-seasons">' in data:
            printDBG("Page is a TV Show page. Listing Seasons/Episodes.")
            self.listSeasonsAndEpisodes(cItem, data)
            return
        if "/team/" in url:
            actor_name = self.cm.ph.getDataBeetwenMarkers(data, "<h2>", "</h2>", False)[1].strip()
            actor_bio = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<p>", "</p>", False)[1].strip()).strip()
            actor_section_content = self.cm.ph.getDataBeetwenMarkers(data, '<div class="actorSection">', "</h2>", False)[1]
            image_url = ""
            if actor_section_content:
                image_url = self.cm.ph.getSearchGroups(actor_section_content, r'data-lazy-src="([^"]+)"')[0].strip()
                if not image_url:
                    image_url = self.cm.ph.getSearchGroups(actor_section_content, r'src="([^"]+)"')[0].strip()
            if image_url:
                icon = self.getFullUrl(image_url)
            details_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="DetailsLists">', "</div>", False)[1]
            details_parts = []
            if details_block:
                li_items = self.cm.ph.getAllItemsBeetwenMarkers(details_block, "<li>", "</li>")
                for li in li_items:
                    label_match = self.cm.ph.getDataBeetwenMarkers(li, "<span>", "</span>", False)
                    label = self.cleanHtmlStr(label_match[1]) if label_match[0] else ""
                    value = li
                    if label_match[0]:
                        value = li.split("</span>", 1)[-1]
                    value = self.cleanHtmlStr(value)
                    label_en = ""
                    if "الاسم :" in label:
                        label_en = "Name"
                    elif "الاسم بالعربي" in label:
                        label_en = "Arabic Name"
                    elif "تاريخ الميلاد" in label:
                        label_en = "Birthday"
                    elif "مكان الولادة" in label:
                        label_en = "Country"
                    elif "الطول" in label:
                        label_en = "Height"
                    elif "الوزن" in label:
                        label_en = "Weight"
                    elif "توقيع الفنان" in label:
                        label_en = "Signature"
                    elif "فصيلة الدم" in label:
                        label_en = "Blood Type"
                    if label_en and value:
                        colored_label = "%s%s%s" % (Y, label_en, W)
                        details_parts.append("%s : %s" % (colored_label, value))
            full_desc_lines = []
            if actor_bio:
                full_desc_lines.append("%sBio :%s %s" % (Y, W, actor_bio))
            if details_parts:
                full_desc_lines.append(" | ".join(details_parts))
            full_desc = "\n".join(full_desc_lines) if full_desc_lines else _("No biography available")
            self.addMarker({"title": "%s%s%s" % (LB, actor_name or title, W), "icon": icon, "desc": full_desc})
            works = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="post">', "</article>")
            for item in works:
                url_match = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0].strip()
                title_attr = self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0].strip()
                if not url_match or not title_attr:
                    continue
                work_url = self.getFullUrl(url_match)
                work_title = self.cleanHtmlStr(title_attr)
                work_title = re.sub(r"\s*تقرير\s*\+\s*حلقات\s*مترجمة", "", work_title).strip()
                work_icon = self.cm.ph.getSearchGroups(item, r'data-img="([^"]+)"')[0].strip()
                if not work_icon:
                    work_icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0].strip()
                work_icon = self._fixUrl(work_icon) if work_icon else self.DEFAULT_ICON_URL
                episode_info = ""
                eps_match = re.search(r'<div class="eps">[^<]*<span>[^<]*<i[^>]*>[^<]*</i>\s*([^<]+)', item)
                if eps_match:
                    episode_info = self.cleanHtmlStr(eps_match.group(1)).strip()
                raw_spans = re.findall(r"<span[^>]*>\s*<i[^>]*>.*?</i>\s*([^<]+)", item, re.DOTALL)
                cleaned_parts = []
                for raw_text in raw_spans:
                    clean_text = self.cleanHtmlStr(raw_text).strip()
                    if clean_text and clean_text not in cleaned_parts:
                        cleaned_parts.append(clean_text)
                episode_info = ""
                genre_parts = []
                for part in cleaned_parts:
                    if re.search(r"(حلقة|\d+\s*حلقة)", part):
                        episode_info = part
                    else:
                        genre_parts.append(part)
                desc_parts = []
                if episode_info:
                    desc_parts.append(episode_info)
                if genre_parts:
                    desc_parts.extend(genre_parts)
                work_desc = "\n".join(desc_parts) if desc_parts else _("Work of this actor")
                self.addDir({"title": "%s%s%s" % (Y, work_title, W), "url": work_url, "icon": work_icon, "desc": work_desc, "category": "explore_item"})
            return
        else:
            embed_player_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="embed-player">', "</div>", False)[1]
            if embed_player_block and ("iframe" in embed_player_block or "asiatvplayer.com/embed-" in embed_player_block):
                printDBG("Page is an Episode/Movie with a playable embed block.")
                desc_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="entry-content">', "</div>", False)[1]
                if not desc_block:
                    desc_block = self.cm.ph.getDataBeetwenMarkers(data, "<p>", "</p>", False)[1]
                if not desc_block:
                    desc_block = self.cleanHtmlStr(data[:800])
                self.addVideo({"title": title, "url": url, "icon": icon, "desc": self.cleanHtmlStr(desc_block)[:600] + "..." if len(self.cleanHtmlStr(desc_block)) > 600 else self.cleanHtmlStr(desc_block), "type": "video", "urlSeparateRequest": True, "good_for_fav": True})
            else:
                printDBG("Page contains neither episodes list nor an embed player. Content is currently unavailable.")
                self.addMarker({"title": "%s المسلسل/الفيلم غير متاح حاليًا %s" % (Y, W), "desc": "لا توجد حلقات أو روابط تشغيل متاحة لهذه الصفحة بعد."})

    def listEpisodes(self, cItem):
        printDBG("Asi1TV.listEpisodes: Opening Season Page")
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        self.listSeasonsAndEpisodes(cItem, data)

    def getLinksForVideo(self, cItem):
        printDBG("Asi1TV.getLinksForVideo [%s]" % cItem["url"])
        urlTab = []
        try:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return urlTab
            epwatch_match = re.search(r'name="epwatch"\s+value="(\d+)"', data)
            if not epwatch_match:
                return urlTab
            ajax_url = "https://asiawiki.me/wp-admin/admin-ajax.php?action=fetch_episode&id=%s" % epwatch_match.group(1)
            ajax_params = dict(self.defaultParams)
            ajax_params["header"] = dict(self.HEADER)
            ajax_params["header"]["Referer"] = "https://asiawiki.me/"
            sts, json_data = self.cm.getPage(ajax_url, ajax_params)
            if not sts:
                return urlTab
            response = json.loads(json_data)
            for server_name, iframe_html in response.get("servers", {}).items():
                src_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', iframe_html, re.IGNORECASE)
                if src_match:
                    link = src_match.group(1).replace("\\/", "/")
                    if link.startswith("//"):
                        link = "https:" + link
                    name = self.cleanHtmlStr(server_name).strip() or "مشغل فيديو"
                    if not any(l["url"] == link for l in urlTab):
                        urlTab.append({"name": name, "url": link, "need_resolve": 1})
        except Exception as e:
            printDBG("Error: %s" % e)
            printExc()
        return urlTab

    def getVideoLinks(self, url):
        printDBG("Asi1TV.getVideoLinks [%s]" % url)
        urlTab = []
        if "asiatvplayer.com/embed-" in url:
            return self.resolve_asiatvplayer_link(url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def resolve_asiatvplayer_link(self, embed_url):
        printDBG("Asi1TV.resolve_asiatvplayer_link: Processing embed URL: %s" % embed_url)
        urlTab = []
        try:
            custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://asiawiki.me/",
            }
            addParams = dict(self.defaultParams)
            if "header" not in addParams:
                addParams["header"] = {}
            addParams["header"].update(custom_headers)
            sts, html = self.getPage(embed_url, addParams=addParams)
            if not sts or not html:
                printDBG("Failed to load embed page or empty content")
                return urlTab
            k_match = re.search(r"'([^']+)'\.split\('\|'\)", html, re.DOTALL) or re.search(r'"([^"]+)"\.split\("\|"\)', html, re.DOTALL)
            k_list = k_match.group(1).split("|") if k_match else []
            p_match = re.search(r"eval\(function\([^)]*\)\{.*?\}\s*\(\s*(?:'(?P<p>.*?)'|\"(?P<p2>.*?)\")\s*,\s*(?P<a>\d+)\s*,\s*(?P<c>\d+)\s*,\s*(?:'(?P<k1>[^']*)'|\"(?P<k2>[^\"]*)\")\.split\('\|'\)", html, re.DOTALL)
            p_string = None
            a = 36
            c = 0
            if p_match:
                p_string = p_match.group("p") or p_match.group("p2")
                a = int(p_match.group("a"))
                c = int(p_match.group("c"))
                if not k_list:
                    tmpk = p_match.group("k1") or p_match.group("k2")
                    if tmpk:
                        k_list = tmpk.split("|")

            def to_base(n, base):
                digits = "0123456789abcdefghijklmnopqrstuvwxyz"
                if n == 0:
                    return "0"
                s = ""
                while n > 0:
                    s = digits[n % base] + s
                    n //= base
                return s

            def replace_numbers_with_klist(text):
                if not k_list:
                    return text

                def repl(m):
                    try:
                        idx = int(m.group(0))
                        return k_list[idx] if idx < len(k_list) else m.group(0)
                    except:
                        return m.group(0)

                return re.sub(r"\b\d+\b", repl, text)

            decoded_js = None
            if p_string:
                decoded = p_string
                max_i = min(c, len(k_list)) if k_list else c
                for i in range(max_i - 1, -1, -1):
                    key = to_base(i, a)
                    val = k_list[i] if i < len(k_list) else key
                    decoded = re.sub(r"\b" + re.escape(key) + r"\b", val, decoded)
                decoded_js = decoded
            else:
                eval_block = None
                mblock = re.search(r"eval\(function\([^)]*\)\{.*?\}\s*\((.*?)\)\s*\)\s*;", html, re.DOTALL)
                if mblock:
                    eval_block = mblock.group(1)
                elif re.search(r"eval\(function\([^)]*\)\{(.+?)</script>", html, re.DOTALL):
                    eval_block = re.search(r"eval\(function\([^)]*\)\{(.+?)</script>", html, re.DOTALL).group(1)
                decoded_js = replace_numbers_with_klist(eval_block) if eval_block else html
            mp4_links = []
            mpd_link = None
            mp4_matches = re.findall(r'file\s*:\s*"([^"]+\.mp4)"\s*,\s*label\s*:\s*"([^"]+)"', decoded_js or "")
            for mp4_url, label in mp4_matches:
                mp4_links.append({"name": f"AsiaTVPlayer {label}", "url": mp4_url, "need_resolve": 0, "extra_headers": custom_headers, "iptv_proto": "mp4"})
            mpd_matches = re.findall(r'https?://[^\s\'"]+?\.mpd', decoded_js or "")
            m3u8_matches = re.findall(r'https?://[^\s\'"]+?(?:/master\.m3u8|\.urlset/manifest\.m3u8)', decoded_js or "")
            auto_link = None
            if mpd_matches:
                auto_link = mpd_matches[0]
            elif m3u8_matches:
                auto_link = m3u8_matches[0]
            if auto_link:
                mpd_link = {"name": "AsiaTVPlayer Auto", "url": auto_link, "need_resolve": 0, "extra_headers": custom_headers, "iptv_proto": "mpd" if auto_link.endswith(".mpd") else "m3u8"}
            urlTab = mp4_links[:3]
            if mpd_link:
                urlTab.append(mpd_link)
        except Exception as e:
            printDBG("AsiaTvPlayer parsing error: %s" % str(e))
        return urlTab

    def listSeasonsAndEpisodes(self, cItem, data):
        printDBG("Asi1TV.listSeasonsAndEpisodes")
        full_desc = ""
        ar_name = ""
        wrapper = self.cm.ph.getDataBeetwenMarkers(data, '<div class="wrapper-info">', '<div class="description">', False)[1]
        if wrapper:

            def clean_between(src, start, end):
                val = self.cm.ph.getDataBeetwenMarkers(src, start, end, False)[1]
                return self.cleanHtmlStr(val).strip() if val else ""

            def desc_line(label, value):
                return "%s%s%s : %s" % (Y, label, W, value) if value else "%s%s%s : " % (Y, label, W)

            genres = " - ".join([self.cleanHtmlStr(g) for g in self.cm.ph.getAllItemsBeetwenMarkers(wrapper, '<a href="https://asiatvdrama.com/genre/', "</a>")])
            country = self.cm.ph.getSearchGroups(wrapper, r"<span>البلد  المنتج : </span>\s*<a[^>]*>([^<]+)</a>")[0].strip()
            orig_name = clean_between(wrapper, "<span>اسم العمل  :</span>", "</div>")
            ar_name = clean_between(wrapper, "<span>الاسم العربي  :</span>", "</div>")
            aka = clean_between(wrapper, "<span>يعرف  ايضا :</span>", "</div>")
            dates = clean_between(wrapper, "<span>مواعيد البث :</span>", "</div>")
            eps = clean_between(wrapper, "<span>عدد الحلقات : </span>", "</div>")
            story = clean_between(data, '<div class="description">', "</div>")
            show_days = ""
            days_block = self.cm.ph.getDataBeetwenMarkers(wrapper, "<span>ايام العرض : </span>", "</div>", False)[1]
            if days_block:
                a = self.cm.ph.getDataBeetwenMarkers(days_block, "<a", "</a>", False)[1]
                if ">" in a:
                    show_days = self.cleanHtmlStr(a.split(">", 1)[1])
            cast = []
            cast_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="team">', "</ul>", False)[1]
            if cast_block:
                cast = [self.cleanHtmlStr(c) for c in self.cm.ph.getAllItemsBeetwenMarkers(cast_block, "<span>", "</span>") if self.cleanHtmlStr(c)]
            full_desc = "\n".join(
                filter(
                    None,
                    [
                        " | ".join(
                            filter(
                                None,
                                [
                                    desc_line("Genre", genres),
                                    desc_line("Country", country),
                                    desc_line("Orignal Name", orig_name),
                                    desc_line("AR Name", ar_name),
                                ],
                            )
                        ),
                        desc_line("AKA", aka),
                        " | ".join(
                            filter(
                                None,
                                [
                                    desc_line("Broadcast Dates", dates),
                                    desc_line("Show Days", show_days),
                                    desc_line("Episodes", eps),
                                ],
                            )
                        ),
                        desc_line("Cast", " - ".join(cast)),
                        desc_line("Story", story),
                    ],
                )
            )
        seasons_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="list-seasons">', "</ul>", False)[1]
        season_items = []
        for link in self.cm.ph.getAllItemsBeetwenMarkers(seasons_block, "<a ", "</a>"):
            url = self.cm.ph.getSearchGroups(link, r'href="([^"]+)"')[0].strip()
            title = self.cleanHtmlStr(link).strip()
            if url and title:
                season_items.append({"title": title, "url": self.getFullUrl(url), "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": _("Season") + " " + title})
        if len(season_items) > 1:
            for s in season_items:
                self.addDir({"category": "listEpisodesForSeason", "title": Y + s["title"] + W, "url": s["url"], "icon": s["icon"], "desc": s["desc"]})
        elif len(season_items) == 1:
            s = season_items[0]
            self.addMarker({"title": Y + s["title"] + W, "icon": s["icon"], "desc": s["desc"]})
        episodes_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="eplist2 list-eps">', "</ul>", False)[1]
        if episodes_block:
            episodes = []
            for link in self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, "<a ", "</a>"):
                url = self.cm.ph.getSearchGroups(link, r'href="([^"]+)"')[0].strip()
                if not url:
                    continue
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(link, r'title="([^"]+)"')[0]).strip()
                season_block = self.cm.ph.getDataBeetwenMarkers(link, "<span>", "</span>", False)[1]
                season_name = self.cleanHtmlStr(season_block).strip() if season_block else ""
                if not ep_title:
                    ep_num = self.cm.ph.getSearchGroups(url, r"[حH]\d+.*?\D(\d+)/")[0]
                    ep_title = "الحلقة %s" % ep_num if ep_num else "حلقة غير معروفة"
                show_name = ar_name
                if ar_name and season_name and season_name not in ar_name and season_name != "الموسم الأول":
                    show_name = "%s %s" % (ar_name, season_name)
                elif not ar_name:
                    show_name = season_name
                title = "%s - %s" % (ep_title, show_name) if show_name else ep_title
                episodes.append({"title": title, "url": self.getFullUrl(url), "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": full_desc or "لا توجد معلومات.", "type": "video", "good_for_fav": True, "urlSeparateRequest": True})
            episodes.reverse()
            for ep in episodes:
                self.addVideo(ep)
        elif not season_items:
            self.addMarker({"title": "%s المسلسل غير مكتمل حاليًا %s" % (Y, W), "desc": "لم يتم إضافة حلقات أو مواسم لهذا المسلسل بعد."})
        return True

    def listEpisodesForSeason(self, cItem):
        printDBG("Asi1TV.listEpisodesForSeason: Opening Season Page [%s]" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        episodes_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="eplist2 list-eps">', "</ul>", False)[1]
        if episodes_block:
            wrapper = self.cm.ph.getDataBeetwenMarkers(data, '<div class="wrapper-info">', '<div class="description">', False)[1]
            ar_name = ""
            if wrapper:
                arab = self.cm.ph.getDataBeetwenMarkers(wrapper, "<span>الاسم العربي  :</span>", "</div>", False)[1]
                ar_name = self.cleanHtmlStr(arab).strip() if arab else ""
            full_desc = cItem.get("desc", "لا توجد معلومات.")
            episodes_list = []
            for link in self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, "<a ", "</a>"):
                url = self.cm.ph.getSearchGroups(link, r'href="([^"]+)"')[0].strip()
                if not url:
                    continue
                episode_title = self.cm.ph.getSearchGroups(link, r'title="([^"]+)"')[0]
                episode_title = self.cleanHtmlStr(episode_title).strip()
                season_year_block = self.cm.ph.getDataBeetwenMarkers(link, "<span>", "</span>", False)[1]
                season_year_name = self.cleanHtmlStr(season_year_block).strip() if season_year_block else ""
                if not episode_title:
                    episode_num = self.cm.ph.getSearchGroups(url, r"[حH]\d+.*?\D(\d+)/")[0]
                    if episode_num:
                        episode_title = "الحلقة %s" % episode_num
                    else:
                        episode_title = "حلقة غير معروفة"
                full_show_name = ar_name
                if ar_name and season_year_name:
                    if season_year_name not in ar_name and season_year_name != "الموسم الأول":
                        full_show_name = "%s - %s" % (ar_name, season_year_name)
                elif not ar_name:
                    full_show_name = season_year_name
                if full_show_name:
                    title = "%s - %s" % (episode_title, full_show_name)
                else:
                    title = episode_title
                episodes_list.append({"title": title, "url": self.getFullUrl(url), "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": full_desc, "type": "video", "good_for_fav": True, "urlSeparateRequest": True})
            episodes_list.reverse()
            for ep in episodes_list:
                self.addVideo(ep)
        else:
            self.addMarker({"title": "%s لا توجد حلقات متاحة في هذا الموسم %s" % (Y, W), "desc": "لم يتم إضافة حلقات لهذا الموسم بعد."})
        return True

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Asi1TV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Asi1TV.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        category = self.currItem.get("category", "")
        self.currList = []
        if self.currItem.get("name", "") is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "explore_item":
            self.exploreItem(self.currItem)
        elif category == "list_drama_menu":
            self.listDramaMenu(self.currItem)
        elif category == "list_drama":
            self.listItems(self.currItem)
        elif category == "listEpisodes":
            self.listEpisodes(self.currItem)
        elif category == "play_dummy":
            self.exploreItems(self.currItem)
        elif category == "list_all_actors":
            self.listAllActors(self.currItem)
        elif category == "listEpisodesForSeason":
            self.listEpisodesForSeason(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Asi1TV(), True, [])

    def withArticleContent(self, cItem):
        return "play_dummy" == cItem.get("category", "")
