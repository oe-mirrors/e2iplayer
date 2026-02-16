# -*- coding: utf8 -*-
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import unpack, detect, get_packed_data
from Plugins.Extensions.IPTVPlayer.libs import ph
import base64
import urllib
import re
import time
import os
import requests
import hashlib
import subprocess
import threading
import json
import sys
import html

from datetime import datetime
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist

try:
    from urllib.parse import quote_plus, urljoin, quote  # Python 3
except ImportError:
    from urllib import quote_plus, quote  # Python 2
    from urlparse import urljoin


#################################################
def gettytul():
    return "https://lodynet.watch"


class Lodynet(CBaseHostClass):
    def __init__(self):
        params = {"history": "lodynet.history", "cookie": "lodynet.cookie", "history_store_type": False}
        CBaseHostClass.__init__(self, params)
        self.MAIN_URL = "https://lodynet.watch"
        self.DEFAULT_ICON_URL = "https://lodynet.watch/wp-content/themes/Lodynet2020/Img/Logo.webp"
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    def searchItems(self):
        if self._historyLenTextFunction:
            return [
                {
                    "category": "search",
                    "title": "بحث",
                    "search_item": True,
                },
                {"category": "search_history", "title": "سجل البحث", "desc": "تاريخ العبارات التي تم البحث عنها."},
                {"category": "delete_history", "title": "حذف سجل البحث", "desc": self._historyLenTextFunction},
            ]
        else:
            return []

    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "ar,en-US;q=0.7,en;q=0.3", "Accept-Encoding": "gzip, deflate", "Referer": self.MAIN_URL}
        params.update({"header": HTTP_HEADER})
        url = self.encodeUrl(url)
        return self.cm.getPage(url, params, post_data)

    def getFullUrl(self, url):
        if not url:
            return self.DEFAULT_ICON_URL
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = self.MAIN_URL + url
        elif not url.startswith("http"):
            url = self.MAIN_URL + "/" + url
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            if not url.startswith("http"):
                return self.DEFAULT_ICON_URL
        url = self.encodeUrl(url)
        return url

    def cleanHtmlStr(self, data):
        data = data.replace("&nbsp;", " ")
        data = data.replace("&quot;", '"')
        data = re.sub(r"\s+", " ", data)
        return data.strip()

    def encodeUrl(self, url):
        try:
            if isinstance(url, str):
                parts = re.match(r"^(https?://)(.*)$", url)
                if parts:
                    base, rest = parts.groups()
                    rest_encoded = quote(rest, safe="/:%#?=&")
                    return base + rest_encoded
            return url
        except Exception as e:
            printExc()
            return url

    def listsTab(self, tab, cItem):
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listMainMenu(self, cItem):
        printDBG("Lodynet.listMainMenu")
        MAIN_CAT_TAB = [
            {"category": "sub_menu", "title": "مسلسلات", "mode": "10", "sub_mode": 0},
            {"category": "sub_menu", "title": "أفلام", "mode": "10", "sub_mode": 1},
            {"category": "list_items", "title": "برامج و حفلات", "url": "/category/البرامج-و-حفلات-tv/"},
            {"category": "sub_menu", "title": "أغاني", "mode": "10", "sub_mode": 2},
            {"category": "list_items", "title": "المضاف حديثاً", "url": "/", "sub_mode": "newly"},
        ]
        self.listsTab(MAIN_CAT_TAB, cItem)
        search_items = self.searchItems()
        for item in search_items:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listSubMenu(self, cItem):
        printDBG("Lodynet.listSubMenu")
        gnr = cItem.get("sub_mode", "")
        SUB_CAT_TAB = []
        if gnr == 0:
            SUB_CAT_TAB = [
                {"category": "list_items", "title": "مسلسلات هندية", "url": "/category/مسلسلات-هندية-مترجمة/"},
                {"category": "list_items", "title": "مسلسلات هندية مدبلجة", "url": "/dubbed-indian-series-p5/"},
                {"category": "list_items", "title": "مسلسلات ويب هندية", "url": "/category/مسلسل-ويب-هندية/"},
                {"category": "list_items", "title": "مسلسلات هندية 2020", "url": "/release-year/مسلسلات-هندية-2020-a/"},
                {"category": "list_items", "title": "مسلسلات هندية 2019", "url": "/release-year/مسلسلات-هندية-2019/"},
                {"category": "list_items", "title": "مسلسلات هندية 2018", "url": "/release-year/مسلسلات-هندية-2018/"},
                {"category": "list_items", "title": "مسلسلات تركية", "url": "/category/مسلسلات-تركي/"},
                {"category": "list_items", "title": "مسلسلات تركية مدبلجة", "url": "/dubbed-turkish-series-g/"},
                {"category": "list_items", "title": "مسلسلات كورية", "url": "/korean-series-b/"},
                {"category": "list_items", "title": "مسلسلات صينية", "url": "/category/مسلسلات-صينية-مترجمة/"},
                {"category": "list_items", "title": "مسلسلات تايلاندية", "url": "/مشاهدة-مسلسلات-تايلندية/"},
                {"category": "list_items", "title": "مسلسلات باكستانية", "url": "/category/المسلسلات-باكستانية/"},
                {"category": "list_items", "title": "مسلسلات آسيوية حديثة", "url": "/tag/new-asia/"},
                {"category": "list_items", "title": "مسلسلات مكسيكية", "url": "/category/مسلسلات-مكسيكية-a/"},
                {"category": "list_items", "title": "مسلسلات أجنبية", "url": "/category/مسلسلات-اجنبية/"},
            ]
        elif gnr == 1:
            SUB_CAT_TAB = [
                {"category": "list_items", "title": "افلام هندية", "url": "/category/افلام-هندية/"},
                {"category": "list_items", "title": "أفلام هندية مدبلجة", "url": "/category/أفلام-هندية-مدبلجة/"},
                {"category": "list_items", "title": "افلام هندية جنوبية", "url": "/tag/الافلام-الهندية-الجنوبية/"},
                {"category": "list_items", "title": "أفلام هندي 2025", "url": "/release-year/أفلام-هندي-2025/"},
                {"category": "list_items", "title": "أفلام هندي 2024", "url": "/release-year/أفلام-هندي-2024/"},
                {"category": "list_items", "title": "أفلام هندي 2023", "url": "/release-year/أفلام-هندية-2023/"},
                {"category": "list_items", "title": "أفلام هندي 2021", "url": "/release-year/movies-hindi-2021/"},
                {"category": "list_items", "title": "أفلام هندي 2020", "url": "/release-year/افلام-هندي-2020-a/"},
                {"category": "list_items", "title": "افلام هندي 2019", "url": "/release-year/افلام-هندي-2019/"},
                {"category": "list_items", "title": "افلام هندي 2018", "url": "/release-year/افلام-هندي-2018/"},
                {"category": "list_items", "title": "افلام هندي 2017", "url": "/release-year/افلام-هندي-2017/"},
                {"category": "list_items", "title": "افلام هندي 2016", "url": "/release-year/2016/"},
                {"category": "list_items", "title": "افلام هندية 4K", "url": "/tag/افلام-هندية-مترجمة-بجودة-4k/"},
                {"category": "list_items", "title": "أميتاب باتشان", "url": "/actor/أميتاب-باتشان/"},
                {"category": "list_items", "title": "اعمال شاروخان", "url": "/actor/شاه-روخ-خان-a/"},
                {"category": "list_items", "title": "أعمال سلمان خان", "url": "/actor/سلمان-خان-a/"},
                {"category": "list_items", "title": "أعمال عامر خان", "url": "/actor/عامر-خان-a/"},
                {"category": "list_items", "title": "أعمال شاهد كابور", "url": "/actor/شاهيد-كابور/"},
                {"category": "list_items", "title": "أعمال رانبير كابور", "url": "/actor/رانبير-كابور/"},
                {"category": "list_items", "title": "أعمال ديبيكا بادكون", "url": "/actor/ديبيكا-بادكون/"},
                {"category": "list_items", "title": "أعمال جينيفر ونجت", "url": "/actor/جينيفر-ونجت/"},
                {"category": "list_items", "title": "أعمال هريتيك روشان", "url": "/actor/هريتيك-روشان/"},
                {"category": "list_items", "title": "أعمال اكشاي كومار", "url": "/actor/اكشاي-كومار/"},
                {"category": "list_items", "title": "أعمال تابسي بانو", "url": "/actor/تابسي-بانو/"},
                {"category": "list_items", "title": "أعمال سانجاي دوت", "url": "/actor/سانجاي-دوت-a/"},
                {"category": "list_items", "title": "ترجمات احمد بشير", "url": "/tag/جميع-الأفلام-في-هذا-القسم-من-ترجمة-أحمد/"},
                {"category": "list_items", "title": "افلام تركية مترجم", "url": "/category/افلام-تركية-مترجم/"},
                {"category": "list_items", "title": "افلام باكستانية", "url": "/tag/افلام-باكستانية-مترجمة/"},
                {"category": "list_items", "title": "افلام اسيوية", "url": "/category/افلام-اسيوية-a/"},
                {"category": "list_items", "title": "افلام اجنبي", "url": "/category/افلام-اجنبية-مترجمة-a/"},
                {"category": "list_items", "title": "انيمي", "url": "/category/انيمي/"},
            ]
        elif gnr == 2:
            SUB_CAT_TAB = [
                {"category": "list_items", "title": "أغاني المسلسلات", "url": "/category/اغاني/اغاني-المسلسلات-الهندية/"},
                {"category": "list_items", "title": "تصاميم مسلسلات هندية", "url": "/category/تصاميم-مسلسلات-هندية/"},
                {"category": "list_items", "title": "أغاني الأفلام", "url": "/category/اغاني-الافلام/"},
                {"category": "list_items", "title": "اغاني هندية mp3", "url": "/category/اغاني/اغاني-هندية-mp3/"},
            ]
        self.listsTab(SUB_CAT_TAB, cItem)

    # ==========================================================================================
    def listItems(self, cItem):
        printDBG("Lodynet.listItems [%s]" % cItem)
        url = cItem.get("url", "")
        page = cItem.get("page", 1)
        if not url.startswith("http"):
            url = self.getFullUrl(url)
        if page > 1:
            if "/page/" in url:
                url = re.sub(r"/page/\d+", "/page/%d" % page, url)
            else:
                url = url.rstrip("/") + "/page/%d" % page
        sts, data = self.getPage(url)
        if not sts:
            return
        items = re.findall(r'<div class="ItemNewly">(.*?)</div>\s*</a>\s*</div>', data, re.S)
        for item in items:
            title = re.search(r'title="([^"]+)"', item)
            link = re.search(r'href="([^"]+)"', item)
            img = re.search(r'data-src="([^"]*)"', item)
            if not title or not link:
                continue
            title = title.group(1).strip()
            item_url = self.getFullUrl(link.group(1))
            icon = self.getFullUrl(img.group(1)) if img and img.group(1) else self.DEFAULT_ICON_URL
            desc = self.extractDescFromNewly(item)
            if self.determineContentType(title, item_url) == "series":
                self.addDir({"category": "list_episodes", "title": title, "url": item_url, "desc": desc, "icon": icon, "good_for_fav": True})
            else:
                self.addVideo({"title": title, "url": item_url, "desc": desc, "icon": icon, "good_for_fav": True})
        # ===== الصفحات التالية للمضاف حديثاً =====
        if cItem.get("sub_mode") == "newly" and items:
            next_page = page + 1
            next_url = self.MAIN_URL + "/page/%d/" % next_page
            self.addDir({"category": "list_items", "title": "\\c00FFFF00 الصفحة التالية (%d)" % next_page, "url": next_url, "icon": "", "page": next_page, "desc": "\\c00????00 الانتقال إلى الصفحة " + str(next_page), "sub_mode": "newly"})
            return
        # ===== زر عرض المزيد =====
        more = re.search(r"GetMoreCategory\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", data)
        if more:
            order = more.group(1)
            pick_id = more.group(2)
            parent_id = more.group(3)
            data_type = more.group(4)
            taxonomy = more.group(5)
            self.addDir({"category": "load_more", "title": "\\c00FFFF00 عرض المزيد", "pick_up_order": order, "pick_up_id": pick_id, "parent_id": parent_id, "data_type": data_type, "taxonomy": taxonomy})
            printDBG("Load more detected: order=%s id=%s parent=%s type=%s taxonomy=%s" % (order, pick_id, parent_id, data_type, taxonomy))

    # ==========================================================================================
    def listEpisodes(self, cItem):
        printDBG("Lodynet.listEpisodes [%s]" % cItem)
        url = self.getFullUrl(cItem.get("url", ""))
        sts, data = self.getPage(url)
        if not sts:
            return
        blocks = re.findall(r'(<div class="ItemNewly">.*?</div>\s*</a>\s*</div>)', data, re.S)
        for block in blocks:
            title = re.search(r'title="([^"]+)"', block)
            link = re.search(r'href="([^"]+)"', block)
            img = re.search(r'data-src="([^"]*)"', block)
            if not title or not link:
                continue
            icon = self.getFullUrl(img.group(1)) if img and img.group(1) else self.DEFAULT_ICON_URL
            self.addVideo({"title": title.group(1).strip(), "url": self.getFullUrl(link.group(1)), "desc": self.extractDescFromNewly(block), "icon": icon, "good_for_fav": True})
        more = re.search(r"GetMoreCategory\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", data)
        if more:
            self.addDir({"category": "load_more", "title": "\\c00FFFF00 عرض المزيد من الحلقات", "pick_up_type": more.group(1), "pick_up_id": more.group(2), "parent_id": more.group(3), "data_type": more.group(4), "taxonomy": more.group(5), "is_episodes": True})  # order  # id الجديد  # parent المسلسل  # type  # taxonomy
            printDBG("Add 'عرض المزيد من الحلقات' button")
        else:
            printDBG("No more episodes button found")

    # ==========================================================================================
    def loadMore(self, cItem):
        printDBG("Lodynet.loadMore [%s]" % cItem)
        API_URL = self.MAIN_URL + "/wp-content/themes/Lodynet2020/Api/RequestMoreCategory.php"
        if cItem.get("is_episodes"):
            post_data = {"order": cItem.get("pick_up_type", "post"), "parent": cItem.get("parent_id", ""), "type": cItem.get("data_type", "Category"), "taxonomy": cItem.get("taxonomy", "category"), "id": cItem.get("pick_up_id", "")}
        else:
            post_data = {"order": cItem.get("pick_up_order", ""), "parent": cItem.get("parent_id", ""), "type": cItem.get("data_type", ""), "taxonomy": cItem.get("taxonomy", ""), "id": cItem.get("pick_up_id", "")}
        params = {"header": {"X-Requested-With": "XMLHttpRequest", "Referer": self.MAIN_URL}}
        sts, data = self.cm.getPage(API_URL, params, post_data)
        if not sts:
            return
        try:
            items = json.loads(data)
        except:
            return
        last_id = None
        new_items_count = 0
        for item in items:
            title = item.get("post_title") or item.get("name") or ""
            url = item.get("url") or item.get("post_name") or ""
            if not title or not url:
                continue
            current_id = item.get("ID") or item.get("id")
            if url.split("/")[-1] == cItem.get("url", "").split("/")[-1]:
                continue
            last_id = current_id
            new_items_count += 1
            full_url = self.getFullUrl(url)
            icon = item.get("cover") or item.get("post_cover") or self.DEFAULT_ICON_URL
            icon = self.getFullUrl(icon)
            ribbon = item.get("ribbon", "")
            ago = item.get("ago", "")
            episode = item.get("episode", "")
            content = item.get("post_content", "")
            desc_parts = []
            if ribbon:
                desc_parts.append("\\c00????00 النوع: \\c00FFFFFF" + ribbon)
            if ago:
                desc_parts.append("\\c00????00 وقت النشر: \\c00FFFFFF" + ago)
            if episode:
                desc_parts.append("\\c00????00 الحلقة: \\c00FFFFFF" + str(episode))
            if content:
                story = self.cm.ph.getDataBeetwenMarkers(content, "تتحدث القصة عن", "بطولة", False)[1]
                if not story:
                    story = content.split("\r\n")[0]
                clean_story = re.sub(r"<[^>]+>", "", story).strip()
                if clean_story:
                    desc_parts.append("\\c0000FF00 القصة:\\n\\c00FFFFFF" + clean_story)
            full_desc = "\\n".join(desc_parts)
            params = {"title": title, "url": full_url, "icon": icon, "desc": full_desc, "good_for_fav": True}
            if self.determineContentType(title, full_url) == "series":
                params["category"] = "list_episodes"
                self.addDir(params)
            else:
                self.addVideo(params)
        if last_id and new_items_count >= 20:
            newItem = dict(cItem)
            newItem.update({"pick_up_id": last_id, "url": url})
            self.addDir(newItem)

    # ==========================================================================================
    def determineContentType(self, title, url=""):
        title_lower = title.lower()
        url_lower = url.lower() if url else ""
        printDBG("=== determineContentType DEBUG ===")
        printDBG(f"Title: {title}")
        printDBG(f"URL: {url}")
        printDBG(f"Title Lower: {title_lower}")
        printDBG(f"URL Lower: {url_lower}")
        episode_keywords = [
            "حلقة",
            "الحلقة",
            "episode",
            "الحلقة الأخيرة",
            "حلقة جديدة",
            "اعلان",
        ]
        series_keywords = ["مسلسل", "المسلسل", "series", "مسلسلات", "المسلسلات", "season", "موسم", "الموسم", "سلسلة", "برنامج"]
        movie_keywords = ["فيلم", "الفيلم", "movie", "film", "أفلام", "الأفلام", "أغنية", "اغنية", "أغاني", "اغاني", "كليب", "كلب", "تصميم", "تصاميم", "مقطع", "مقاطع"]
        if any(keyword in url_lower for keyword in ["/اغاني/", "/أغاني/", "/music/", "/songs/", "/تصاميم-", "/design/"]):
            result = "movie"
            printDBG(f"Music/Design section detected: {result}")
            return result
        if any(keyword in title_lower for keyword in ["أغنية", "اغنية", "أغاني", "اغاني", "music", "كليب", "كلب", "تصميم", "تصاميم"]):
            result = "movie"
            printDBG(f"Music/Design title detected: {result}")
            return result
        for keyword in episode_keywords:
            if keyword in title_lower:
                result = "episode"
                printDBG(f"Episode keyword '{keyword}' detected: {result}")
                return result
        for keyword in series_keywords:
            if keyword in title_lower:
                result = "series"
                printDBG(f"Series keyword '{keyword}' detected: {result}")
                return result
        for keyword in movie_keywords:
            if keyword in title_lower:
                result = "movie"
                printDBG(f"Movie keyword '{keyword}' detected: {result}")
                return result
        if re.search(r"(season|موسم|s)\s*\d+", title_lower):
            result = "series"
            printDBG(f"Season pattern detected: {result}")
            return result
        if any(keyword in url_lower for keyword in ["/series/", "/مسلسلات/", "/مسلسل/", "/seasons/"]):
            result = "series"
            printDBG(f"Series URL pattern detected: {result}")
            return result
        if any(keyword in url_lower for keyword in ["/movies/", "/أفلام/", "/فيلم/", "/film/"]):
            result = "movie"
            printDBG(f"Movie URL pattern detected: {result}")
            return result
        if any(keyword in url_lower for keyword in ["/category/مسلسلات-اجنبية", "/category/", "/series-", "/مسلسل-"]) and not any(keyword in url_lower for keyword in ["/افلام/", "/movies/", "/أغاني/", "/music/"]):
            result = "series"
            printDBG(f"Foreign series section detected: {result}")
            return result
        if "/أفلام" in url_lower or "/movies" in url_lower:
            result = "movie"
            printDBG(f"Movies section detected: {result}")
            return result
        result = "movie"
        printDBG(f"Default result: {result}")
        return result

    # ==========================================================================================
    def getTimeAgo(self, date_str):
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            elapsed = int(time.time() - time.mktime(dt.timetuple()))
        except:
            return date_str
        if elapsed < 60:
            return "قبل ثواني"
        units = [
            (31207680, "سنة", "سنتين", "سنوات"),
            (2600640, "شهر", "شهرين", "أشهر"),
            (604800, "أسبوع", "أسبوعين", "أسابيع"),
            (86400, "يوم", "يومان", "أيام"),
            (3600, "ساعة", "ساعتين", "ساعات"),
            (60, "دقيقة", "دقيقتين", "دقائق"),
        ]
        for seconds, one, two, many in units:
            if elapsed >= seconds:
                value = int(round(float(elapsed) / seconds))
                if value == 1:
                    return "قبل %s واحدة" % one
                elif value == 2:
                    return "قبل (2) %s" % two
                elif value < 11:
                    return "قبل %s %s" % (value, many)
                else:
                    return "قبل %s %s" % (value, one)
        return "قبل ثواني"

    # ==========================================================================================
    def extractDescFromNewly(self, html_block):
        desc_parts = []
        type_match = re.search(r'NewlyRibbon">([^<]+)</div>', html_block)
        if type_match:
            desc_parts.append("\\c00????00 النوع: \\c00????FF" + type_match.group(1).strip())
        time_match = re.search(r'NewlyTimeAgo[^>]*data-date="([^"]+)"', html_block)
        if time_match:
            ago = self.getTimeAgo(time_match.group(1).strip())
            desc_parts.append("\\c00????00 وقت النشر: \\c00????FF" + ago)
        episode_match = re.search(r"NewlyEpNumber[^>]*>.*?(\d+)</div>", html_block)
        if episode_match:
            desc_parts.append("\\c00????00 الحلقة: \\c00????FF" + episode_match.group(1).strip())
        summary_match = re.search(r'class="NewlySummary"[^>]*>([^<]+)</div>', html_block)
        if summary_match:
            desc_parts.append("\\c00????00 الملخص: \\c00FFFFFF" + summary_match.group(1).strip())
        return "\n".join(desc_parts) if desc_parts else "\\c00????00 محتوى مضاف حديثاً"

    # ==========================================================================================
    def getLinksForVideo(self, cItem):
        printDBG("### ENTER getLinksForVideo ###")
        printDBG("Lodynet.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        printDBG("Loading page: %s" % url)
        sts, data = self.getPage(url)
        if not sts:
            printDBG("Failed to load page")
            return []
        if isinstance(data, bytes):
            data = data.decode("utf-8", "ignore")
        printDBG("Page loaded successfully, size: %d bytes" % len(data))
        links = []
        referer = url
        # ===== PostID =====
        post_id = None
        for m in re.findall(r"SwitchServer\(this,\s*\d+,\s*(\d+)\)", data):
            post_id = m
            break
        printDBG("PostID = %s" % post_id)
        # ===== Servers =====
        servers = re.findall(r'<button[^>]+id="ServerWatch(\d+)"[^>]*>([^<]+)</button>', data)
        printDBG("Found %d server buttons" % len(servers))
        if not post_id or not servers:
            printDBG("No servers or no post_id")
            return []
        api_url = self.MAIN_URL + "/wp-content/themes/Lodynet2020/Api/RequestServerEmbed.php"
        green_servers = ["ViD LO", "Vinovo", "ok.ru", "Doodws", "VidHide", "Strmtap", "Ninjastm", "Fembed", "Uqload", "Vidoza", "playtube"]
        for server_id, server_name in servers:
            server_name = server_name.strip()
            display_name = server_name
            if any(g in server_name for g in green_servers):
                display_name = "\\c0000FF00" + server_name
            links.append({"name": " " + display_name, "url": strwithmeta(api_url, {"post_data": {"PostID": post_id, "ServerID": server_id}, "Referer": referer}), "need_resolve": 1})
        printDBG("Final result: %d links" % len(links))
        return links

    # ==========================================================================================
    def getVideoLinks(self, videoUrl):
        printDBG("Lodynet.getVideoLinks [%s]" % videoUrl)
        videoUrlStr = str(videoUrl)
        if "ok.ru" in videoUrlStr:
            printDBG("Direct OK.ru URL detected in getVideoLinks, using custom resolver")
            return self.getOkRuLinks(videoUrlStr)
        if hasattr(videoUrl, "meta"):
            post_data = videoUrl.meta.get("post_data")
            if post_data:
                printDBG("Found POST data: %s" % str(post_data))
                return self.processAPIRequest(str(videoUrl), post_data, videoUrl.meta.get("Referer", self.MAIN_URL))
        if any(x in videoUrlStr for x in ["vidlo.us", "viidshar.com", "govad.xyz", "vadbam.net"]):
            return self.getVidloDirectLinks(videoUrlStr)
        if videoUrlStr.endswith(".mp4"):
            return [{"name": "Direct MP4", "url": videoUrlStr}]
        headers = {"User-Agent": self.USER_AGENT, "Referer": self.MAIN_URL}
        url_with_meta = strwithmeta(videoUrlStr, headers)
        return self.up.getVideoLinkExt(url_with_meta)

    # ==========================================================================================
    def getOkRuLinks(self, baseUrl):
        printDBG("========= getOkRuLinks baseUrl[%r]" % baseUrl)
        # ===================== HTTP headers setup =====================
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.91 Safari/537.36", "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,ar;q=0.8", "Accept-Encoding": "gzip, deflate", "Content-Type": "application/json", "Referer": baseUrl, "Origin": "https://ok.ru", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin", "Connection": "keep-alive"}
        # ===================== Fetch the video page =====================
        sts, pageData = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []  # Changed from False to [] for safe list handling
        urlsTab = []
        # Extract 'data-options' attribute from the page
        data_options_match = re.search(r'data-options="([^"]+)"', pageData)
        if not data_options_match:
            printDBG("========= No data-options found!")
            return []
        data_options_str = html.unescape(data_options_match.group(1))
        # Parse metadata from flashvars
        try:
            # Replaced json_loads with json.loads
            data_options = json.loads(data_options_str)
            flashvars = data_options.get("flashvars", {})
            metadata_str = flashvars.get("metadata", "")
            metadata_str = metadata_str.replace('\\"', '"').replace("\\\\", "\\").replace("\\u0026", "&")
            metadata = json.loads(metadata_str)
        except Exception as e:
            printDBG("========= Failed to parse metadata JSON: %s" % e)
            return []
        all_links = []
        # ===================== Extract MP4 video links =====================
        if "videos" in metadata:
            for video in metadata["videos"]:
                url = video.get("url", "")
                if not url or ("okcdn.ru" not in url and "vkuser.net" not in url):
                    continue
                url = url.replace("\\u0026", "&")
                q = video.get("name") or video.get("type") or ""
                quality_map = {"mobile": "144p", "lowest": "144p", "low": "360p", "sd": "480p", "hd": "720p", "full": "1080p", "4k": "2160p"}
                q_str = quality_map.get(q, q)  # e.g., "720p"
                quality_val = re.sub(r"\D", "", q_str)  # extract number only, e.g., 720
                display_quality = {"2160": "4K [2160p]", "1080": "FULL HD [1080p]", "720": "HD [720p]", "480": "SD [480p]", "360": "LOW [360p]", "240": "[240p]", "144": "[144p]"}.get(quality_val, q_str)
                bitrate = video.get("bitrate") or "unknown"
                res = video.get("res") or video.get("resolution") or "unknown"
                codecs = video.get("codecs") or "avc1,mp4a"
                display = f"{display_quality} - MP4 - bitrate: {bitrate} res: {res} {codecs}"
                all_links.append({"name": display, "url": strwithmeta(url, {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]}), "quality_val": quality_val, "is_hls": False, "is_dash": False})
        # ===================== Extract HLS (m3u8) links =====================
        if "ondemandHls" in metadata:
            hls_url = metadata["ondemandHls"].replace("\\u0026", "&")
            hls_url2 = strwithmeta(hls_url, {"iptv_proto": "m3u8", "Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            hls_links = getDirectM3U8Playlist(hls_url2, checkContent=False)
            for link in hls_links:
                raw = link.get("name", "")
                bitrate = re.search(r"bitrate:\s*(\d+)", raw)
                bitrate = bitrate.group(1) if bitrate else "unknown"
                res = re.search(r"res:\s*(\d+x\d+)", raw)
                res = res.group(1) if res else "unknown"
                # Infer quality from resolution height
                quality_val = 0
                if "x" in res:
                    try:
                        quality_val = int(res.split("x")[1])
                    except:
                        quality_val = 0
                if quality_val >= 1080:
                    q_disp = "FULL HD [1080p]"
                elif quality_val >= 720:
                    q_disp = "HD [720p]"
                elif quality_val >= 480:
                    q_disp = "SD [480p]"
                elif quality_val >= 360:
                    q_disp = "LOW [360p]"
                elif quality_val >= 240:
                    q_disp = "LOW [240p]"
                else:
                    q_disp = "[144p]"
                display = f"{q_disp} - HLS - bitrate: {bitrate} res: {res} avc1,mp4a"
                all_links.append({"name": display, "url": link["url"], "quality_val": quality_val, "is_hls": True, "is_dash": False})
        # ===================== Extract DASH links =====================
        if "ondemandDash" in metadata:
            dash_url = metadata["ondemandDash"].replace("\\u0026", "&")
            all_links.append({"name": "DASH (Adaptive)", "url": strwithmeta(dash_url, {"iptv_proto": "mpd", "Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]}), "quality_val": "0", "is_hls": False, "is_dash": True})
        # ===================== Standardize MP4 name and infer resolution/bitrate =====================
        for item in all_links:
            if not item.get("is_hls", False) and not item.get("is_dash", False):
                qv = int(item["quality_val"]) if str(item["quality_val"]).isdigit() else 0
                # Infer resolution from quality_val
                if "res" not in item["name"] or "unknown" in item["name"]:
                    if qv == 2160:
                        res = "3840x2160"
                    elif qv == 1080:
                        res = "1920x1080"
                    elif qv == 720:
                        res = "1280x720"
                    elif qv == 480:
                        res = "854x480"
                    elif qv == 360:
                        res = "640x360"
                    elif qv == 240:
                        res = "426x240"
                    elif qv == 144:
                        res = "256x144"
                    else:
                        res = "unknown"
                else:
                    res = "unknown"
                # Infer approximate bitrate
                if "bitrate: unknown" in item["name"]:
                    if qv == 2160:
                        bitrate = "8000000"
                    elif qv == 1080:
                        bitrate = "5000000"
                    elif qv == 720:
                        bitrate = "2500000"
                    elif qv == 480:
                        bitrate = "1200000"
                    elif qv == 360:
                        bitrate = "800000"
                    elif qv == 240:
                        bitrate = "500000"
                    elif qv == 144:
                        bitrate = "300000"
                    else:
                        bitrate = "500000"
                else:
                    bitrate = "unknown"
                # Rebuild display name
                item["name"] = f"{item['name'].split(' - ')[0]} - MP4 - bitrate: {bitrate} res: {res} avc1,mp4a"

        # ===================== Sort links by quality descending =====================
        def sort_key(item):
            qv = str(item.get("quality_val", "0"))  # always convert to string
            q = int(qv) if qv.isdigit() else 0
            return q

        all_links.sort(key=sort_key, reverse=True)  # Sort from highest to lowest
        urlsTab = [{"name": x["name"], "url": x["url"]} for x in all_links]
        printDBG("========= parserOKRU extracted %d links" % len(urlsTab))
        for u in urlsTab:
            printDBG("========= - %s: %s" % (u["name"], u["url"]))
        return urlsTab

    # ==========================================================================================
    def processAPIRequest(self, api_url, post_data, referer):
        """معالجة طلبات API للسيرفرات"""
        printDBG("processAPIRequest")
        printDBG("API URL: %s" % api_url)
        printDBG("POST Data: %s" % str(post_data))
        printDBG("Referer: %s" % referer)
        headers = {"User-Agent": self.USER_AGENT, "X-Requested-With": "XMLHttpRequest", "Referer": referer, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        try:
            printDBG("Sending POST request to API...")
            response = requests.post(api_url, data=post_data, headers=headers, timeout=30)
            response_text = response.text.strip()
            printDBG("API Response: %s" % response_text)
            printDBG("Response length: %d chars" % len(response_text))
            printDBG("Response starts with: %s" % response_text[:100])
            if response_text and response_text.startswith("http"):
                embed_url = response_text
                printDBG("Success! Embed URL: %s" % embed_url)
                if "ok.ru" in embed_url:
                    printDBG("Detected OK.ru, using enhanced resolver")
                    return self.getOkRuLinks(embed_url)
                elif any(domain in embed_url for domain in ["hglink.to", "davioad.com", "haxloppd.com", "jaw", "jawcloud", "streamhls.to"]):
                    headers = {"User-Agent": self.USER_AGENT, "Referer": embed_url}
                    url_with_meta = strwithmeta(embed_url, headers)
                    return self.up.getVideoLinkExt(url_with_meta)
                elif "larhu.com" in embed_url:
                    headers = {"User-Agent": self.USER_AGENT, "Referer": embed_url}
                    url_with_meta = strwithmeta(embed_url, headers)
                    return self.up.getVideoLinkExt(url_with_meta)
                elif any(domain in embed_url for domain in ["vidlo", "viidshar", "govad", "vadbam", "dood", "fembed", "uqload", "vidoza"]):
                    return self.getVidloDirectLinks(embed_url)
                else:
                    headers = {"User-Agent": self.USER_AGENT, "Referer": api_url}
                    url_with_meta = strwithmeta(embed_url, headers)
                    return self.up.getVideoLinkExt(url_with_meta)
            else:
                printDBG("API returned empty or invalid response")
                return []
        except Exception as e:
            printDBG("Error in processAPIRequest: %s" % str(e))
            return []

    # ==========================================================================================
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Lodynet.listSearchResult [%s]" % searchPattern)
        if not searchPattern:
            return
        search_url = self.MAIN_URL + "/wp-content/themes/Lodynet2020/Api/RequestSearch.php?value=" + quote_plus(searchPattern)
        printDBG("Search URL: %s" % search_url)
        headers = {"User-Agent": self.USER_AGENT, "X-Requested-With": "XMLHttpRequest", "Referer": self.MAIN_URL, "Accept": "application/json, text/javascript, */*; q=0.01"}
        try:
            response = requests.get(search_url, headers=headers, timeout=30)
            response_text = response.text
            printDBG("Search API Response: %s" % response_text)
            if response_text and response_text.strip():
                try:
                    data = json.loads(response_text)
                    if isinstance(data, list) and len(data) >= 2:
                        search_results = data[1]
                        if isinstance(search_results, list) and search_results:
                            printDBG("تم العثور على %d نتيجة بحث" % len(search_results))
                            for item in search_results:
                                if not isinstance(item, dict):
                                    continue
                                title = item.get("Title", "")
                                item_url = item.get("Url", "")
                                category = item.get("Category", "")
                                cover = item.get("Cover", "")
                                if not title or not item_url:
                                    continue
                                try:
                                    if "\\u" in title:
                                        title = title.encode("utf-8").decode("unicode_escape")
                                    elif "&#x" in title:
                                        title = html.unescape(title)
                                except:
                                    pass
                                if item_url.startswith("http"):
                                    full_url = item_url
                                else:
                                    try:
                                        decoded_url = urllib.parse.unquote(item_url)
                                        if decoded_url.startswith("/"):
                                            full_url = self.MAIN_URL + decoded_url
                                        else:
                                            full_url = self.MAIN_URL + "/" + decoded_url
                                    except:
                                        full_url = self.MAIN_URL + "/" + item_url
                                icon = self.DEFAULT_ICON_URL
                                if cover:
                                    try:
                                        if "\\/" in cover:
                                            cover = cover.replace("\\/", "/")
                                        icon = self.getFullUrl(cover)
                                    except:
                                        icon = self.DEFAULT_ICON_URL
                                desc_parts = []
                                if category:
                                    desc_parts.append("\\c00????00القسم: \\c00????FF" + category)
                                desc = "\n".join(desc_parts) if desc_parts else "نتيجة بحث"
                                content_type = self.determineContentType(title, full_url)
                                if content_type == "series":
                                    params = {"category": "list_episodes", "title": title.strip(), "url": full_url, "desc": desc, "icon": icon, "good_for_fav": True}
                                    self.addDir(params)
                                else:
                                    params = {"category": "video", "title": title.strip(), "url": full_url, "desc": desc, "icon": icon, "good_for_fav": True}
                                    self.addVideo(params)
                        else:
                            self.addDir({"category": "search", "title": "\\c00FF0000لم يتم العثور على نتائج", "url": "", "desc": "لم يتم العثور على أي نتائج للبحث: " + searchPattern})
                    else:
                        self.addDir({"category": "search", "title": "\\c00FF0000خطأ في تنسيق البيانات", "url": "", "desc": "استجابة غير متوقعة من خادم البحث"})
                except Exception as e:
                    printDBG("Error parsing search JSON: %s" % str(e))
                    printDBG("Raw response: " + response_text)
                    self.addDir({"category": "search", "title": "\\c00FF0000خطأ في تحليل النتائج", "url": "", "desc": "تعذر تحليل نتائج البحث: " + str(e)})
            else:
                self.addDir({"category": "search", "title": "\\c00FF0000استجابة فارغة من الخادم", "url": "", "desc": "لم يستجب خادم البحث للطلب"})
        except Exception as e:
            printDBG("Error in search: %s" % str(e))
            self.addDir({"category": "search", "title": "\\c00FF0000خطأ في البحث", "url": "", "desc": "حدث خطأ أثناء البحث: " + str(e)})

    # ==========================================================================================
    def getArticleContent(self, cItem):
        printDBG("Lodynet.getArticleContent [%s]" % cItem)
        retTab = []
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            return []
        title = cItem.get("title", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        summary = ""
        content_block = self.cm.ph.getDataBeetwenMarkers(data, '<div id="ContentDetails"', "</div>", False)[1]
        if content_block:
            if "ملخص أحداث الحلقة" in content_block:
                summary = content_block.split("ملخص أحداث الحلقة")[-1]
            elif "تبدأ الحلقة" in content_block:
                summary = "تبدأ الحلقة" + content_block.split("تبدأ الحلقة")[-1]
            else:
                summary = self.cm.ph.getDataBeetwenMarkers(content_block, "<p>", "</p>", False)[1]
        if summary:
            summary = summary.split("قراءة المزيد")[0]
            summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary.replace("&#8211;", "-").replace("&#8220;", '"').replace("&#8221;", '"').replace("&nbsp;", " ")
            summary = summary.strip()
        old_desc = cItem.get("desc", "")
        final_text = ""
        if summary:
            final_text = "\\c0000FF00 الملخص: \\n\\c00FFFFFF" + summary
            if old_desc:
                final_text = old_desc + "\\n-------------------\\n" + final_text
        else:
            final_text = old_desc if old_desc else "لا يوجد ملخص متاح حالياً."
        if title:
            retTab.append({"title": title, "text": final_text, "images": [{"title": "", "url": icon}], "other_info": {}})
        return retTab

    # ==========================================================================================
    def getVidloDirectLinks(self, baseUrl):
        printDBG("getVidloDirectLinks [%s]" % baseUrl)
        PRIMARY_PATH = "/media/hdd/IPTVCache/cookies"
        FALLBACK_PATH = "/tmp/IPTV_Cookies"
        if os.path.isdir(PRIMARY_PATH) and os.access(PRIMARY_PATH, os.W_OK):
            COOKIE_PATH = PRIMARY_PATH
        else:
            COOKIE_PATH = FALLBACK_PATH
        if not os.path.exists(COOKIE_PATH):
            try:
                os.makedirs(COOKIE_PATH)
            except Exception as e:
                printDBG("Cookie dir error: %s" % e)
                COOKIE_PATH = "/tmp"
        COOKIE_FILE = os.path.join(COOKIE_PATH, "vidlo.cookie")
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0", "Referer": baseUrl}
        params = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE, "return_data": True, "follow_redirects": True}
        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            printDBG("فشل تحميل الصفحة")
            return []
        final_url = self.cm.meta.get("url", baseUrl)
        printDBG("الرابط النهائي: %s" % final_url)
        video_urls = []
        sources_match = re.search(r"sources\s*:\s*\[([^\]]+)\]", data)
        if sources_match:
            sources_content = sources_match.group(1)
            printDBG("تم العثور على مصادر الفيديو")
            video_objects = re.findall(r"\{[^{}]*\}", sources_content)
            for obj in video_objects:
                url_match = re.search(r'file["\']?\s*:\s*["\'](https?://[^"\']+)["\']', obj)
                label_match = re.search(r'label["\']?\s*:\s*["\']([^"\']+)["\']', obj)
                if url_match:
                    video_url = url_match.group(1)
                    if label_match:
                        label = label_match.group(1)
                        if "720" in label or "hd" in label.lower():
                            label = "HD [720p]"
                        elif "480" in label or "sd" in label.lower():
                            label = "SD [480p]"
                        elif "360" in label or "low" in label.lower():
                            label = "LOW [360p]"
                        elif "576" in label:
                            label = "576p"
                        elif "384" in label:
                            label = "384p"
                        else:
                            label = label
                    else:
                        if ".m3u8" in video_url.lower():
                            label = "HLS Stream"
                        elif "720p" in video_url.lower() or "/hd/" in video_url.lower():
                            label = "HD [720p]"
                        elif "1080p" in video_url.lower() or "/fullhd/" in video_url.lower():
                            label = "FULL HD [1080p]"
                        elif "480p" in video_url.lower() or "/sd/" in video_url.lower():
                            label = "SD [480p]"
                        elif "360p" in video_url.lower() or "/low/" in video_url.lower():
                            label = "LOW [360p]"
                        elif "576p" in video_url.lower():
                            label = "576p"
                        elif "384p" in video_url.lower():
                            label = "384p"
                        else:
                            label = "MP4"
                    if video_url not in [v["url"] for v in video_urls]:
                        video_urls.append({"url": video_url, "label": label})
                        printDBG("تم استخراج: %s [%s]" % (video_url, label))
        if not video_urls:
            printDBG("البحث عن روابط MP4 مباشرة")
            quality_patterns = [(r'https?://[^\s"\']+?720p[^\s"\']*\.mp4', "HD [720p]"), (r'https?://[^\s"\']+?1080p[^\s"\']*\.mp4', "FULL HD [1080p]"), (r'https?://[^\s"\']+?480p[^\s"\']*\.mp4', "SD [480p]"), (r'https?://[^\s"\']+?576p[^\s"\']*\.mp4', "576p"), (r'https?://[^\s"\']+?384p[^\s"\']*\.mp4', "384p"), (r'https?://[^\s"\']+?360p[^\s"\']*\.mp4', "LOW [360p]"), (r'https?://[^\s"\']+?\.mp4[^\s"\']*', "MP4")]
            for pattern, quality in quality_patterns:
                matches = re.findall(pattern, data)
                for url in matches:
                    if url not in [v["url"] for v in video_urls]:
                        video_urls.append({"url": url, "label": quality})
                        printDBG("تم العثور على MP4: %s [%s]" % (url, quality))
        hls_patterns = [r'https?://[^\s"\']+?\.m3u8[^\s"\']*', r'file["\']?\s*:\s*["\'](https?://[^"\']+?\.m3u8[^"\']*)["\']']
        for pattern in hls_patterns:
            matches = re.findall(pattern, data)
            for hls_url in matches:
                if "master.m3u8" in hls_url:
                    label = "HLS Master"
                elif "playlist.m3u8" in hls_url:
                    label = "HLS Playlist"
                else:
                    label = "HLS Stream"
                if hls_url not in [v["url"] for v in video_urls]:
                    video_urls.append({"url": hls_url, "label": label})
                    printDBG("تم العثور على HLS: %s [%s]" % (hls_url, label))
        if video_urls:
            quality_priority = {"FULL HD [1080p]": 0, "HD [720p]": 1, "SD [480p]": 2, "576p": 3, "384p": 4, "LOW [360p]": 5, "MP4": 6, "HLS Master": 7, "HLS Playlist": 8, "HLS Stream": 9, "direct": 10}

            def get_quality_priority(item):
                label = item["label"]
                return quality_priority.get(label, 999)

            video_urls.sort(key=get_quality_priority)
            result = []
            for item in video_urls:
                result.append({"name": item["label"], "url": strwithmeta(item["url"], {"Referer": final_url, "User-Agent": HTTP_HEADER["User-Agent"]})})
            printDBG("تم العثور على %d رابط" % len(result))
            for item in result:
                printDBG("   - %s: %s" % (item["name"], item["url"]))
            return result
        printDBG("لم يتم العثور على أي رابط فيديو")
        return []

    # ==========================================================================================
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Lodynet.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: || name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "sub_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "load_more":
            self.loadMore(self.currItem)
        elif category == "load_more_episodes":
            self.loadMore(self.currItem)
        elif category == "search":
            self.listSearchResult(self.currItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"category": "search", "name": "history"})
        elif category == "delete_history":
            self.delHistory(self.sessionEx)

    # ==========================================================================================
    def listsHistory(self, baseItem={"name": "history", "category": "search"}, desc_key="plot", desc_base=("النوع: ")):
        list = self.history.getHistoryList()
        for histItem in list:
            plot = ""
            try:
                if type(histItem) is type({}):
                    pattern = histItem.get("pattern", "")
                    search_type = histItem.get("type", "")
                    if "" != search_type:
                        plot = desc_base + search_type
                else:
                    pattern = histItem
                    search_type = None
                params = dict(baseItem)
                params.update({"title": pattern, "search_type": search_type, desc_key: plot})
                self.addDir(params)
            except Exception:
                printExc()

    def start(self, cItem):
        return self.handleService(cItem)


# ==========================================================================================
class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Lodynet(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "list_episodes" == cItem.get("category", ""):
            return True
        return False


###################################################################### الحمد لله
