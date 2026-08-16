# # -*- coding: utf-8 -*-
# # MovizHome plugin for oe-mirrors IPTVPlayer
# # Author : MohamedOS (Modified By Mohamed Elsafty)
# # Last modified: 17/05/2026
# # Description: A plugin to access MovizHome website content
# ###############################################################
# # LOCAL import
# ###############################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

# ###############################################################
# # FOREIGN import
# ###############################################################
import re
import html

try:
    from html import unescape
except ImportError:
    from cgi import unescapeHTML as unescape

# ###############################################################
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote
###############################################################
Y = E2ColoR("yellow")
W = E2ColoR("white")
LB = E2ColoR("lightblue")
G = E2ColoR("green")
R = E2ColoR("red")


###############################################################
def GetConfigList():
    return []


def gettytul():
    return "https://movizhome.click/"


class MovizHome(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "movizhome", "cookie": "movizhome.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("https://movizhome.click/wp-content/uploads/2024/12/MovizHome-LoGo-238x238.png")
        self.cacheLinks = {}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if isinstance(baseUrl, str):
            try:
                baseUrl = quote(baseUrl, safe=":/?&=%")
            except Exception:
                pass
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self):
        base = "https://movizhome.click"
        self.addDir({"name": "category", "category": "list_items", "title": "مضاف حديثا", "url": self.getFullUrl("/recent/")})
        menu_data = {"افلام اجنبيه": ["category/افلام-movis/افلام-اجنبية", [("الأكشن", "genre/اكشن"), ("الرعب", "genre/رعب"), ("الخيال العلمي", "genre/خيال-علمي"), ("الفانتازيا", "genre/fantasy-movies"), ("رومانسية", "genre/رومانسية"), ("الكوميديا", "genre/كوميديا"), ("الإثارة والتشويق", "genre/إثارة"), ("الجريمة", "genre/جريمة"), ("المغامرات", "genre/مغامرات"), ("الدراما", "genre/دراما"), ("كلاسيكية", "tag/افلام-كلاسيكية"), ("الغموض", "genre/غموض"), ("عائلية", "genre/عائلي"), ("تاريخية", "genre/تاريخي"), ("الويسترن", "genre/ويسترن")]], "افلام هندية": ["category/افلام-movis/افلام-هنديه", [("التيلجو", "tag/telugu"), ("تاميلية", "tag/افلام-تاميلية"), ("ماليالامية", "tag/افلام-ماليالامية"), ("كنادية", "tag/افلام-كنادية"), ("بنجابية", "tag/punjabi"), ("ماراثية", "tag/افلام-ماراثية"), ("بنغالية", "tag/افلام-بنغالية"), ("كجراتية", "tag/افلام-كجراتية")]], "افلام آسيوية": ["category/افلام-movis/افلام-اسيويه", [("كورية", "language/الكورية"), ("يابانية", "language/اليابانية"), ("صينية", "language/الصينية"), ("تايلاندية", "language/التايلاندية"), ("إندونيسية", "language/الاندونيسية"), ("فلبينية", "language/الفلبينية"), ("منغولية", "language/المغولية")]], "افلام فرنسية": ["category/افلام-movis/افلام-فرنسية/", []], "افلام تركية": ["category/افلام-movis/افلام-تركية", []], "افلام مدبلجة": ["category/افلام-movis/افلام-مدبلجة", []], "انيميشن": ["category/افلام-كارتون/", []]}
        for title, (main_path, subs) in menu_data.items():
            sub_items = [{"title": "افلام %s" % s[0], "url": "%s/%s" % (base, s[1])} for s in subs]
            self.addDir({"name": "category", "category": "list_sub_menu", "title": title, "url": "%s/%s" % (base, main_path), "subs": sub_items, "good_for_fav": True})
        self.listsTab(self.searchItems(), {"name": "category"})

    def listSubMenu(self, cItem):
        direct_sections = ["افلام فرنسية", "افلام تركية", "افلام مدبلجة", "انيميشن"]
        if cItem["title"] in direct_sections:
            self.addDir({"name": "category", "category": "list_items", "title": cItem["title"], "url": cItem["url"]})
            return
        subs = cItem.get("subs")
        if subs:
            for sub in subs:
                self.addDir({"name": "category", "category": "list_items", "title": sub["title"], "good_for_fav": True, "url": sub["url"]})
        if cItem.get("url"):
            self.addDir({"name": "category", "category": "list_items", "title": "%s%s%s" % (Y, "عرض الكل", W), "url": cItem["url"]})

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.HEADER.get("User-Agent")})

    def listItems(self, cItem, nextCategory=None):
        printDBG("movizhome.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, '<div class="Small--Box">', "</a>", withMarkers=True)
        if not data:
            return
        for item in data:
            try:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '<a[^>]+href="([^"]+)"')[0])
            except:
                continue
            try:
                title = unescape(self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)"')[0]))
                title = re.sub(r"^(فيلم|مسلسل|انمي|برنامج)\s+", "", title).strip()
            except:
                try:
                    title = unescape(self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '<h3 class="title">([^<]+)</h3>')[0]))
                except:
                    title = ""
            try:
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)"')[0])
            except:
                icon = ""
            genre = self.cm.ph.getSearchGroups(item, r'<li[^>]*class="genre"[^>]*>\s*([^<]+)')
            quality = self.cm.ph.getSearchGroups(item, r'<li[^>]*class="quality"[^>]*>\s*([^<]+)')
            imdb = self.cm.ph.getSearchGroups(item, r"imdbRating[^>]*>.*?([\d\.]+)")
            genre = genre[0].strip() if genre else ""
            quality = quality[0].strip() if quality else ""
            imdb = imdb[0].strip() if imdb else ""
            desc_lines = []
            if genre:
                desc_lines.append("%sGenre:%s %s" % (Y, W, genre))
            if quality:
                desc_lines.append("%sQuality:%s %s" % (Y, W, quality))
            if imdb:
                try:
                    imdb_val = float(imdb)
                    imdb_color = G if imdb_val >= 6.0 else R
                except:
                    imdb_color = W
                desc_lines.append("%sIMDB Rating:%s %s%s%s" % (Y, W, imdb_color, imdb, W))
            desc = "\n".join(desc_lines)
            params = dict(cItem)
            params.update({"title": title, "url": url, "icon": icon, "desc": desc, "short_desc": desc, "good_for_fav": True, "category": "video"})
            self.addVideo(params)
        nextPage = self.cm.ph.getSearchGroups(htm, '<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')
        if nextPage:
            params = dict(cItem)
            params.update({"title": "%s%s%s" % (Y, ("Next Page") + " ▶▶▶", W), "url": self.getFullUrl(nextPage[0]), "good_for_fav": False, "category": "list_items"})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        addParams = {"header": {"User-Agent": self.cm.getDefaultHeader()["User-Agent"]}, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE, "CFProtection": True}
        sts, data = self.getPage("https://movizhome.click/?s=%s" % searchPattern, addParams)
        if not sts:
            return
        items = re.findall(r'<div class="Small--Box">(.*?)</a>\s*</div>', data, re.S)
        printDBG("SEARCH ITEMS COUNT: %d" % len(items))
        for item in items:
            try:
                url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            except:
                url = ""
            try:
                title = self.cm.ph.getSearchGroups(item, r'<h3 class="title">(.*?)</h3>')[0]
                title = self.cleanHtmlStr(title)
                title = re.sub(r"^(فيلم|مسلسل|انمي|برنامج)\s+", "", title).strip()
            except:
                title = ""
            try:
                icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            except:
                icon = ""
            genre = self.cm.ph.getSearchGroups(item, r'<li[^>]*class="genre"[^>]*>\s*([^<]+)')
            quality = self.cm.ph.getSearchGroups(item, r'<li[^>]*class="quality"[^>]*>\s*([^<]+)')
            imdb = self.cm.ph.getSearchGroups(item, r"imdbRating[^>]*>.*?([\d\.]+)")
            genre = genre[0].strip() if genre else ""
            quality = quality[0].strip() if quality else ""
            imdb = imdb[0].strip() if imdb else ""
            desc_lines = []
            if genre:
                desc_lines.append("%sGenre:%s %s" % (Y, W, genre))
            if quality:
                desc_lines.append("%sQuality:%s %s" % (Y, W, quality))
            if imdb:
                try:
                    imdb_val = float(imdb)
                    imdb_color = G if imdb_val >= 6.0 else R
                except:
                    imdb_color = W
                desc_lines.append("%sIMDB Rating:%s %s%s%s" % (Y, W, imdb_color, imdb, W))
            desc = "\n".join(desc_lines)
            params = dict(cItem)
            params.update({"title": title, "url": self.cm.getFullUrl(url), "icon": self.cm.getFullUrl(icon), "desc": desc, "short_desc": desc, "good_for_fav": True, "category": "video"})
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("MovizHome.getLinksForVideo %s" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem["url"] + "watch/")
        if not sts:
            return []
        servers = re.findall(r'<li[^>]+data-watch="([^"]+)"[^>]*>(.*?)</li>', data, re.S)
        for link, item in servers:
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span[^>]*id="serverName"[^>]*>([^<]+)</span>')[0])
            link = self.getFullUrl(link)
            printDBG("SERVER FOUND: %s -> %s" % (name, link))
            urlTab.append({"name": name, "url": link, "need_resolve": 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("MovizHome.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("movizhome.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = ""
        desc_list = re.findall(r'<div class="StoryArea">\s*<p>(.*?)</p>', data, re.S)
        story_str = ""
        if desc_list:
            story_str = self.cleanHtmlStr(desc_list[0])
        full_story = "Story : " + story_str if story_str else ""
        genre_li = re.findall(r'<li>\s*<i class="fa fa-play"></i>[\s\S]*?<span>نوع الفيلم : </span>([\s\S]*?)</li>', data, re.S)
        genre_list = []
        if genre_li:
            genre_list = re.findall(r"<a[^>]+>([^<]+)</a>", genre_li[0])
        genre_str = " - ".join(genre_list) if genre_list else ""
        lang_list = re.findall(r'<li>\s*<i class="fa fa-language"></i>[\s\S]*?<span>لغة الفيلم : </span>([\s\S]*?)</li>', data, re.S)
        if lang_list:
            lang_list = re.findall(r"<a[^>]+>([^<]+)</a>", lang_list[0])
        language_str = " - ".join(lang_list) if lang_list else ""
        country = re.findall(r"دولة : </span>[\s\S]*?<a[^>]+>([^<]+)</a>", data)
        country_str = country[0] if country else ""
        quality = re.findall(r"جودة الفيلم : </span>[\s\S]*?<a[^>]+>([^<]+)</a>", data)
        quality_str = quality[0] if quality else ""
        date = re.findall(r"تاريخ اصدار الفيلم : </span>[\s\S]*?<a[^>]+>([^<]+)</a>", data)
        date_str = date[0] if date else ""
        user_age = re.findall(r"التصنيف العمرى الفيلم : </span>[\s\S]*?<a[^>]+>([^<]+)</a>", data)
        user_age_str = user_age[0] if user_age else ""
        imdb = re.findall(r'<div class="imdbR"><i class="fa fa-star"></i><span>([\d\.]+)</span>', data)
        imdb_str = imdb[0] if imdb else ""
        extra_desc = ""
        if genre_str:
            extra_desc += "%sGenre :%s %s\n" % (Y, W, genre_str)
        if language_str:
            extra_desc += "%sLanguage :%s %s\n" % (Y, W, language_str)
        if country_str:
            extra_desc += "%sCountry :%s %s\n" % (Y, W, country_str)
        if quality_str:
            extra_desc += "%sQuality :%s %s\n" % (Y, W, quality_str)
        if date_str:
            extra_desc += "%sDate :%s %s\n" % (Y, W, date_str)
        if user_age_str:
            extra_desc += "%sUser Age :%s %s\n" % (Y, W, user_age_str)
        if imdb_str:
            extra_desc += "%sIMDB Rating :%s %s" % (Y, W, imdb_str)
        full_desc = "%sStory :%s %s" % (Y, W, story_str) if story_str else ""
        if extra_desc:
            full_desc += "\n\n" + extra_desc
        icon_match = re.findall(r'<div class="image">[\s\S]*?<img[^>]+src="([^"]+)"', data)
        icon = self.getFullIconUrl(icon_match[0]) if icon_match else cItem.get("icon", "")
        actors = re.findall(r'itemprop="actor.*?itemprop="name">([^<]+)', data)
        if actors:
            otherInfo["actors"] = ", ".join(actors)
        return [{"title": cItem["title"], "text": full_desc, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        direct_sections = ["افلام فرنسية", "افلام تركية", "افلام مدبلجة", "انيميشن"]
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "list_sub_menu" and self.currItem["title"] in direct_sections:
            self.listItems(self.currItem, "video")
        elif category == "list_sub_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem, "video")
        elif "list_value" == category:
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, MovizHome(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
