# -*- coding: utf-8 -*-
# Last modified: 13/10/2025 - popking (odem2014)
# Last updated:  20/05/2025 - M.Elsafty (angel_heart)
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
import re
import base64
import json

try:
    from urllib.parse import urlparse, parse_qs, urlencode, unquote, quote
except ImportError:
    from urllib import urlencode, urlopen, unquote, quote


def GetConfigList():
    return []


def gettytul():
    return "https://m.asd.ink/"  # M.elsafty.20260516


class ArabSeed(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "arabseed", "cookie": "arabseed.cookie"})  # names for history and cookie files in cache
        self.urlencode = urlencode
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = "https://m.asd.ink/search"
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/arabseed.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        if any(ord(c) > 127 for c in base_url):
            base_url = urllib_quote_plus(base_url, safe="://")
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def listMainMenu(self, cItem):
        printDBG("ArabSeed.listMainMenu")
        self.MAIN_CAT_TAB = [
            {"category": "movies_folder", "title": "الافلام"},
            {"category": "series_folder", "title": "المسلسلات"},
            {"category": "ramadan_folder", "title": "رمضان"},
            {"category": "anime_folder", "title": "انمي"},
            {"category": "series_packs_folder", "title": "مواسم مسلسلات - برامج - أنمي"},
            {"category": "other_folder", "title": "اخري"},
        ] + self.searchItems()
        self.MOVIES_CAT_TAB = [
            {"category": "list_items", "title": "افلام عربي", "url": self.getFullUrl("/category/arabic-movies-14/")},
            {"category": "list_items", "title": "افلام اجنبي", "url": self.getFullUrl("/category/foreign-movies-14/")},
            {"category": "list_items", "title": "افلام Netfilx", "url": self.getFullUrl("/category/netflix/netflix-movies/")},
            {"category": "list_items", "title": "افلام هندى", "url": self.getFullUrl("/category/indian-movies-2/")},
            {"category": "list_items", "title": "افلام تركية", "url": self.getFullUrl("/category/turkish-movies/")},
            {"category": "list_items", "title": "افلام اسيوية", "url": self.getFullUrl("/category/asian-movies-2/")},
            {"category": "list_items", "title": "افلام كلاسيكيه", "url": self.getFullUrl("/category/افلام-كلاسيكيه/")},
            {"category": "list_items", "title": "افلام مدبلجة", "url": self.getFullUrl("/category/dubbed-movies/")},
        ]
        self.SERIES_CAT_TAB = [
            {"category": "series", "title": "مسلسلات عربية", "url": self.getFullUrl("/category/arabic-series-14/")},
            {"category": "series", "title": "مسلسلات مصرية", "url": self.getFullUrl("/category/مسلسلات-مصريه/")},
            {"category": "series", "title": "مسلسلات اجنبية", "url": self.getFullUrl("/category/foreign-series-7/")},
            {"category": "series", "title": "مسلسلات Netfilx", "url": self.getFullUrl("/category/netflix/netflix-series/")},
            {"category": "series", "title": "مسلسلات تركية", "url": self.getFullUrl("/category/turkish-series-2/")},
            {"category": "series", "title": "مسلسلات هندية", "url": self.getFullUrl("/category/مسلسلات-هندية/")},
            {"category": "series", "title": "مسلسلات كورية", "url": self.getFullUrl("/category/مسلسلات-كوريه/")},
            {"category": "series", "title": "مسلسلات مدبلجة", "url": self.getFullUrl("/category/dubbed-series/")},
            {"category": "series", "title": "مسلسلات كرتون", "url": self.getFullUrl("/category/cartoon-series/")},
        ]
        self.SERIES_PACKS_CAT_TAB = [
            {"category": "series_packs", "title": "مواسم مسلسلات عربية", "url": self.getFullUrl("/category/arabic-series-14/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات مصرية", "url": self.getFullUrl("/category/مسلسلات-مصريه/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات اجنبية", "url": self.getFullUrl("/category/foreign-series-7/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات تركية", "url": self.getFullUrl("/category/turkish-series-2/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات هندية", "url": self.getFullUrl("/category/مسلسلات-هندية/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات كورية", "url": self.getFullUrl("/category/مسلسلات-كوريه/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات مدبلجة", "url": self.getFullUrl("/category/dubbed-series/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2026", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2026-1/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2025", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2025/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2024", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2024/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2023", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2023/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2022", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2022/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2021", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2021/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2020", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2020-hd/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2019", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2019/packs/")},
            {"category": "series_packs", "title": "مواسم برامج تليفزيونية", "url": self.getFullUrl("/category/برامج-تلفزيونية/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات كرتون", "url": self.getFullUrl("/category/cartoon-series/packs/")},
        ]
        self.RAMADAN_CAT_TAB = [
            {"category": "series", "title": "مسلسلات رمضان 2026", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2026/")},
            {"category": "series", "title": "مسلسلات رمضان 2025", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2025/")},
            {"category": "series", "title": "مسلسلات رمضان 2024", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2024/")},
            {"category": "series", "title": "مسلسلات رمضان 2023", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/ramadan-series-2023/")},
            {"category": "series", "title": "مسلسلات رمضان 2022", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2022/")},
            {"category": "series", "title": "مسلسلات رمضان 2021", "url": self.getFullUrl("/category/مسل1لات-رمضان-1/مسلسلات-رمضان-2022/")},
            {"category": "series", "title": "مسلسلات رمضان 2020", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2020-hd/")},
            {"category": "series", "title": "مسلسلات رمضان 2019", "url": self.getFullUrl("/category/مسلسلات-رمضان-1/مسلسلات-رمضان-2019/")},
        ]
        self.ANIME_CAT_TAB = [
            {"category": "list_items", "title": "افلام انيميشن", "url": self.getFullUrl("/category/animation-movies/")},
            {"category": "series", "title": "مسلسلات كرتون", "url": self.getFullUrl("/category/cartoon-series/")},
        ]
        self.OTHER_CAT_TAB = [{"category": "list_items", "title": "اغاني عربي", "url": self.getFullUrl("/category/اغاني-عربي/")}, {"category": "list_items", "title": "مصارعه", "url": self.getFullUrl("/category/wwe-shows-1/")}, {"category": "list_items", "title": "برامج تلفزيونية", "url": self.getFullUrl("/category/برامج-تلفزيونية/")}, {"category": "list_items", "title": "مسرحيات عربيه", "url": self.getFullUrl("/category/مسرحيات-عربي/")}]
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG("ArabSeed.listMoviesFolder")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG("ArabSeed.listSeriesFolder")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listSeriesPacksFolder(self, cItem):
        printDBG("ArabSeed.listSeriesPacksFolder")
        self.listsTab(self.SERIES_PACKS_CAT_TAB, cItem)

    def listRamadanFolder(self, cItem):
        printDBG("ArabSeed.listRamadanFolder")
        self.listsTab(self.RAMADAN_CAT_TAB, cItem)

    def listAnimeFolder(self, cItem):
        printDBG("ArabSeed.listAnimeFolder")
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherFolder(self, cItem):
        printDBG("ArabSeed.listOtherFolder")
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    def getLinksForVideo(self, cItem):
        printDBG("ArabSeed.getLinksForVideo %s" % cItem)
        url = cItem.get("url", "")
        title = cItem.get("title", "")
        need_resolve = cItem.get("need_resolve", 1)
        common_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "DNT": "1"}
        # ===== YouTube / IMDB Direct =====
        if "youtube.com" in url or "youtu.be" in url:
            headers = {"User-Agent": common_headers["User-Agent"], "Referer": "https://www.youtube.com/"}
            return [{"name": "YouTube", "url": strwithmeta(url, headers), "need_resolve": 1}]
        if "imdb.com/video/" in url:
            imdb_links = self.getIMDBTrailer(url)
            if imdb_links:
                return imdb_links
            return []
        # ArabSeed Direct Server
        if "reviewrate.net" in url and "/embed-" in url:
            printDBG("ArabSeed: Parsing reviewrate embed page")
            headers = dict(common_headers)
            headers["Referer"] = "https://m.asd.ink/"
            headers["Origin"] = "https://m.asd.ink"
            sts, data = self.cm.getPage(url, {"header": headers})
            if sts and data:
                patterns = [r"""https?://[^"' ]+\.m3u8[^"' ]*""", r"""https?://[^"' ]+\.mp4[^"' ]*""", r"""file\s*:\s*["']([^"']+)["']""", r"""source\s+src=["']([^"']+)["']"""]
                found = []
                for pattern in patterns:
                    matches = re.findall(pattern, data, re.I)
                    for video_url in matches:
                        if not video_url:
                            continue
                        if not video_url.startswith("http"):
                            continue
                        if video_url in found:
                            continue
                        found.append(video_url)
                        printDBG("ArabSeed: Found video URL >>> %s" % video_url)
                        video_headers = {"User-Agent": common_headers["User-Agent"], "Referer": "https://m.asd.ink/", "Origin": "https://m.asd.ink"}
                        return [{"name": "سيرفر عرب سيد", "url": strwithmeta(video_url, video_headers), "need_resolve": 0}]
            printDBG("ArabSeed: No direct link found, returning embed")
            return [{"name": "سيرفر عرب سيد", "url": strwithmeta(url, headers), "need_resolve": 1}]
        # External Servers
        if need_resolve == 1:
            printDBG("ArabSeed: Resolving external server: %s" % url)
            domain_match = re.search(r"https?://([^/]+)", url)
            stream_domain = domain_match.group(1) if domain_match else ""
            dynamic_headers = {"User-Agent": common_headers["User-Agent"], "Referer": "https://%s/" % stream_domain if stream_domain else url, "Origin": "https://%s" % stream_domain if stream_domain else ""}
            try:
                linksTab = self.up.getVideoLinkExt(url)
                if linksTab and isinstance(linksTab, list):
                    fixed_links = []
                    for link in linksTab:
                        if not isinstance(link, dict):
                            link = {"url": link, "name": title}
                        fixed_link = dict(link)
                        video_url = fixed_link.get("url", "")
                        if video_url:
                            fixed_link["url"] = strwithmeta(video_url, headers)
                        fixed_links.append(fixed_link)
                    printDBG("ArabSeed: External server resolved OK")
                    return fixed_links
            except Exception as e:
                printDBG("ArabSeed.getVideoLinkExt error: %s" % str(e))
            return [{"name": title, "url": strwithmeta(url, dynamic_headers), "need_resolve": 1}]
        # Direct
        return [{"name": title, "url": strwithmeta(url, common_headers), "need_resolve": 0}]

    def getVideoLinks(self, url):
        printDBG("ArabSeed.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)

    def listItems(self, cItem):
        printDBG("ArabSeed.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        data_items = re.findall(r'<li[^>]*class="[^"]*box__xs__2[^"]*"[^>]*>(.*?)</li>', data, re.S)
        printDBG("Items found: %s" % len(data_items))
        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0] or ""
            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0] or ""
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0] or ""
            url = ""
            if pureurl and "/" in pureurl:
                baseurl, filenameurl = pureurl.rsplit("/", 1)
                url = baseurl + "/" + urllib_quote_plus(filenameurl) + "watch/"
            icon = ""
            if pureicon and "/" in pureicon:
                baseicon, filenameicon = pureicon.rsplit("/", 1)
                icon = baseicon + "/" + urllib_quote_plus(filenameicon)
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__genre hide__md">', "</div>", False)[1]).strip()
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__quality hide__md">', "</div>", False)[1]).strip()
            Ratings = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="post__ratings">', "</div>", False)[1]).strip()
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False)[1]).strip()
            line1_parts = []
            line2_parts = []
            if genre:
                line1_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if quality:
                q_color = "white"
                if re.search(r"4K|1080|HD|BluRay", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|HDRip|WEB", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                    q_color = "red"
                line1_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} {E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if Ratings:
                rate_match = re.search(r"(\d+(\.\d+)?)", Ratings)
                rate_color = "white"
                if rate_match:
                    rate_value = float(rate_match.group(1))
                    if rate_value >= 7:
                        rate_color = "green"
                    elif rate_value >= 5:
                        rate_color = "orange"
                    else:
                        rate_color = "red"
                line1_parts.append(f"{E2ColoR('yellow')}Ratings:{E2ColoR('white')} {E2ColoR(rate_color)}{Ratings}{E2ColoR('white')}")
            if story:
                line2_parts.append(f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}")
            desc = " | ".join(line1_parts)
            if line2_parts:
                desc += "\n" + " ".join(line2_parts)
            clean_title = self.clean_title_prefix(title, sub_mode=0, url=cItem.get("url", ""))
            colored_title = self.colorizeTitle(clean_title)
            params = {"category": "explore_item", "title": colored_title, "icon": icon, "url": url, "desc": desc}
            self.addDir(params)
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', "</div>", False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        if next_page:
            next_page = self.getFullUrl(next_page)
            printDBG("NEXT PAGE FOUND >>> %s" % next_page)
            params = dict(cItem)
            params.update(
                {
                    "title": "Next Page ▶",
                    "url": next_page,
                    "category": "list_items",
                }
            )
            self.addDir(params)

    def listSeriesItems(self, cItem):
        printDBG("ArabSeed.listSeriesItems ----------")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="box__xs__2', "</li>")
        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
            if pureurl:
                baseurl, filenameurl = pureurl.rsplit("/", 1)
                fixedfilenameurl = urllib_quote_plus(filenameurl)
                url = baseurl + "/" + fixedfilenameurl + "watch/"
            else:
                url = ""
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit("/", 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + "/" + fixedfilenameicon
            else:
                icon = ""
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__genre hide__md">', "</div>", False)[1]).strip()
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__quality hide__md">', "</div>", False)[1]).strip()
            Ratings = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="post__ratings">', "</div>", False)[1]).strip()
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False)[1]).strip()
            first_line_parts = []
            if genre:
                first_line_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if quality:
                q_color = "white"
                if re.search(r"4K|1080|HD|BluRay", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|HDRip|WEB", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                    q_color = "red"
                first_line_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} " f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if Ratings:
                rate_match = re.search(r"(\d+(\.\d+)?)", Ratings)
                rate_color = "white"
                rate_text = Ratings
                if rate_match:
                    rate_value = float(rate_match.group(1))
                    if rate_value >= 7:
                        rate_color = "green"
                    elif rate_value >= 5:
                        rate_color = "orange"
                    else:
                        rate_color = "red"
                first_line_parts.append(f"{E2ColoR('yellow')}Ratings:{E2ColoR('white')} " f"{E2ColoR(rate_color)}{rate_text}{E2ColoR('white')}")
            line1 = " | ".join(first_line_parts)
            line2 = ""
            if story:
                line2 = f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}"
            desc = line1
            if line2:
                desc += "\n" + line2
            clean_title = self.clean_title_prefix(title, sub_mode=1, url=cItem.get("url", ""))
            colored_title = self.colorizeTitle(clean_title)
            params = {"category": "explore_item", "title": colored_title, "icon": icon, "url": url, "desc": desc}
            printDBG(str(params))
            self.addDir(params)
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', "</div>", False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        if next_page:
            next_page = self.getFullUrl(next_page)
            printDBG("NEXT PAGE FOUND >>> %s" % next_page)
            params = dict(cItem)
            params.update(
                {
                    "title": "Next Page ▶",
                    "url": next_page,
                    "category": "series",
                }
            )
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("ArabSeed.exploreItems >>> %s" % cItem)
        import time

        url = cItem.get("url")
        sts, data = self.cm.getPage(url)
        if not sts or not data:
            return
        post_id = self.cm.ph.getSearchGroups(data, r'post_id["\']?\s*[:=]\s*["\']?(\d+)')[0] or self.cm.ph.getSearchGroups(data, r'psot_id["\']?\s*[:=]\s*["\']?(\d+)')[0]
        csrf_token = self.cm.ph.getSearchGroups(data, r'csrf__token["\']?\s*[:=]\s*["\']([^"\']+)')[0]
        if not post_id or not csrf_token:
            printDBG("Missing post_id or csrf_token")
            return
        printDBG("post_id: %s, csrf_token: %s" % (post_id, csrf_token))
        available_qualities = ["1080", "720", "480"]
        qual_block = self.cm.ph.getDataBeetwenMarkers(data, "quality__options", "</div>", False)[1]
        if qual_block:
            quals = re.findall(r'data-qu="(\d+)"', qual_block)
            if quals:
                available_qualities = sorted(list(set(quals)), reverse=True)
        ajax_url = self.MAIN_URL.rstrip("/") + "/get__watch__server/"
        referer = url
        results = []

        def fetch_server_link(quality, srv_idx):
            try:
                post_data = {"post_id": post_id, "quality": quality, "server": str(srv_idx), "csrf_token": csrf_token}
                headers = {"X-Requested-With": "XMLHttpRequest", "Referer": referer, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "User-Agent": self.HEADER.get("User-Agent", "Mozilla/5.0")}
                params = dict(self.defaultParams)
                params["header"] = headers
                params["timeout"] = 3
                params["connect_timeout"] = 1
                sts, response = self.cm.getPage(ajax_url, params, post_data)
                if sts and response and response.strip():
                    res = json_loads(response.strip())
                    if res.get("type") == "success" and res.get("server"):
                        video_url = res["server"]
                        enc_match = re.search(r"(?:url=|id=)([A-Za-z0-9+/=]+)", video_url)
                        if enc_match:
                            try:
                                encoded = enc_match.group(1)
                                padding = 4 - len(encoded) % 4
                                if padding != 4:
                                    encoded += "=" * padding
                                video_url = base64.b64decode(encoded).decode("utf-8")
                            except:
                                pass
                        if video_url and video_url.startswith("http"):
                            domain = re.search(r"https?://([^/]+)", video_url)
                            domain = domain.group(1) if domain else "unknown"
                            if srv_idx == 0:
                                server_name = "سيرفر عرب سيد"
                            else:
                                server_name = f"سيرفر {srv_idx} - {domain.capitalize()}"
                            server_colored = f"{E2ColoR('cyan')}{server_name}{E2ColoR('white')}"
                            quality_colored = self.colorizeQuality(quality)
                            label = f"{server_colored} [{quality_colored}]"
                            sort_value = 10000 + int(quality) * 10 if srv_idx == 0 else int(quality) * 10 + (5 - srv_idx)
                            return {"name": label, "url": video_url, "need_resolve": 1, "sort": sort_value, "header": {"Referer": "https://" + domain + "/", "User-Agent": self.HEADER.get("User-Agent", "Mozilla/5.0"), "Origin": "https://" + domain}}
            except Exception as e:
                printDBG("fetch_server_link error: %s" % str(e))
            return None

        for quality in available_qualities:
            result = fetch_server_link(quality, 0)
            if result:
                results.append(result)
                printDBG("Added: %s" % result["name"])
        for srv_idx in range(1, 6):
            for quality in available_qualities:
                result = fetch_server_link(quality, srv_idx)
                if result:
                    results.append(result)
                    printDBG("Added: %s" % result["name"])
                time.sleep(0.05)
        results.sort(key=lambda x: x.get("sort", 0), reverse=True)
        for item in results:
            item.pop("sort", None)
            original_title = cItem.get("title", "عنوان غير متاح")
            plain_title = re.sub(r"\\c00[0-9A-F]{6}", "", original_title)
            clean_title = self.clean_title_prefix(plain_title, sub_mode=-1, url=cItem.get("url", ""))
            colored_clean_title = self.colorizeTitle(clean_title)
            final_title = f"{colored_clean_title} {E2ColoR('white')}| {item['name']}"
            self.addVideo({"title": final_title, "url": item["url"], "type": "video", "need_resolve": item["need_resolve"], "header": item.get("header", {})})
        printDBG("ArabSeed.exploreItems <<< done - Found %d links" % len(results))

    def safe_b64decode_urlsafe(self, data):
        """Base64 decode with automatic padding fix and URL-safe characters."""
        if not data:
            return None
        data = data.replace("-", "+").replace("_", "/")
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        try:
            return base64.b64decode(data).decode("utf-8", errors="ignore")
        except:
            return None

    def exploreSeriesItems(self, cItem):
        printDBG("ArabSeed.exploreSeriesItems >>> %s" % cItem)
        url = cItem.get("url")
        if not url:
            return
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("[ArabSeed] Failed to load episode page: %s" % url)
            return

        def extract_first(patterns, data_src):
            for p in patterns:
                try:
                    v = self.cm.ph.getSearchGroups(data_src, p)[0]
                    if v:
                        return v.strip()
                except Exception:
                    continue
            return ""

        token = extract_first([r"csrf__token['\"]:\s*['\"]([^'\"]+)", r"csrf_token['\"]:\s*['\"]([^'\"]+)", r"name=['\"]csrf-token['\"]\s+content=['\"]([^'\"]+)"], data)
        post_id = extract_first([r"psot_id['\"]:\s*'([^']+)'", r"post_id['\"]:\s*['\"]([^'\"]+)", r"post_id\s*:\s*'([^']+)'"], data)
        if not token or not post_id:
            printDBG("[ArabSeed] Missing required POST params (csrf_token or post_id/psot_id)")
            return
        post_url = "https://m.asd.ink/get__watch__server/"
        servers = [0, 1, 2, 3, 4]
        qualities = [480, 720, 1080]
        for server in servers:
            for quality in qualities:
                payload = {"post_id": post_id, "quality": str(quality), "server": str(server), "csrf_token": token}
                headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest", "Referer": url}
                sts2, response = self.cm.getPage(post_url, {"header": headers, "raw_post_data": True}, self.urlencode(payload))
                if not sts2 or not response:
                    continue
                try:
                    result = json_loads(response)
                except Exception as e:
                    printDBG("JSON decode error (series): %s" % str(e))
                    continue
                if result.get("type") != "success":
                    continue
                link = result.get("server", "")
                if not link:
                    continue
                server_name = self.cm.ph.getSearchGroups(link, r"https?://([^/]+)/")[0]
                if server_name in ["m.reviewrate.net", "m.reviewtech.me"]:
                    server_name = "ArabSeed"
                if not server_name:
                    server_name = "server%d" % server
                colored_server = self.colorizeServer(server_name, quality)
                colored_title = self.colorizeTitle(cItem.get("title", "Episode"))
                params_video = MergeDicts(
                    cItem,
                    {
                        "title": f"{colored_title} - {colored_server}",
                        "url": link,
                        "type": "video",
                        "category": "video",
                        "need_resolve": 1,
                    },
                )
                self.addVideo(params_video)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabSeed.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get("page", 1)
        cItem = dict(cItem)
        cItem["search_pattern"] = searchPattern
        cItem["page"] = page
        cItem["url"] = self.getFullUrl("find/?word=") + urllib_quote_plus(searchPattern) + "&type&page_number=" + str(page)
        self.listSearchItems(cItem)

    def listSearchItems(self, cItem):
        printDBG("ArabSeed.listSearchItems [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="series__list">', '<div class="paginate">', False)[1]
        printDBG("tmp.listSearchItems [%s]" % tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li class="box__xs__2', "</li>")
        printDBG("data_items.listSearchItems [%s]" % data_items)
        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
            if pureurl:
                baseurl, filenameurl = pureurl.rsplit("/", 1)
                fixedfilenameurl = urllib_quote_plus(filenameurl)
                url = baseurl + "/" + fixedfilenameurl + "watch/"
            else:
                url = ""
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit("/", 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + "/" + fixedfilenameicon
            else:
                icon = ""
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__genre hide__md">', "</div>", False)[1]).strip()
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__quality hide__md">', "</div>", False)[1]).strip()
            section = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="post__category hide__md">', "</div>", False)[1]).strip()
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False)[1]).strip()
            line1_parts = []
            line2_parts = []
            if genre:
                line1_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if quality:
                q_color = "white"
                if re.search(r"4K|1080|HD|BluRay", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|HDRip|WEB", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                    q_color = "red"
                line1_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} " f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if section:
                line1_parts.append(f"{E2ColoR('yellow')}Section:{E2ColoR('white')} {section}")
            if story:
                line2_parts.append(f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}")
            desc = " | ".join(line1_parts)
            if line2_parts:
                desc += "\n" + " ".join(line2_parts)
            clean_title = self.clean_title_prefix(title, sub_mode=-1, url=cItem.get("url", ""))
            colored_title = self.colorizeTitle(clean_title)
            params = {"category": "explore_item", "title": colored_title, "icon": icon, "url": url, "desc": desc}
            printDBG(str(params))
            self.addDir(params)
        page = cItem.get("page", 1)
        next_page = page + 1
        if len(data_items) > 0:
            params = dict(cItem)
            params.update(
                {
                    "title": _("Next Page") + " ▶",
                    "page": next_page,
                }
            )
            self.addDir(params)

    def getFavouriteData(self, cItem):
        printDBG("ArabSeed.getFavouriteData")
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("ArabSeed.getLinksForFavourite")
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("ArabSeed.setInitListFromFavouriteItem")
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def listSeriesPacks(self, cItem):
        printDBG("ArabSeed.listSeriesPacks >>> %s" % cItem)
        url = cItem.get("url", "").strip()
        if not url:
            return
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("[ArabSeed] Failed to load packs page: %s" % url)
            return
        token = self.cm.ph.getSearchGroups(data, r"csrf__token['\"]:\s*[\"']([^\"']+)")[0]
        if not token:
            token = self.cm.ph.getSearchGroups(data, r"csrf_token['\"]:\s*[\"']([^\"']+)")[0]
        ajax_area = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie__blocks" id="ajax__area">', "</div></section>", False)[1]
        if not ajax_area:
            ajax_area = data
        items = re.findall(r'(<li class="box__xs__1.*?)(?=<li class="box__xs__1|\Z)', ajax_area, re.DOTALL)
        printDBG("Found %d items in packs page" % len(items))
        for item in items:
            link_tag = self.cm.ph.getDataBeetwenMarkers(item, '<a href="', ">", False)[1]
            href = self.cm.ph.getSearchGroups(link_tag, r'^([^"]+)')[0].strip() if link_tag else ""
            title = self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0].strip()
            if not title:
                title = self.cm.ph.getSearchGroups(item, r'<div class="title___"[^>]*>([^<]+)</div>')[0].strip()
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0].strip()
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0].strip()
            if not href or not title:
                continue
            href = quote(href, safe=":/?&=%")
            icon = quote(icon, safe=":/?&=%") if icon else self.DEFAULT_ICON_URL
            bottom_ul = self.cm.ph.getDataBeetwenMarkers(item, '<ul class="bottom__ul">', "</ul>", False)[1]
            bottom_items = self.cm.ph.getAllItemsBeetwenMarkers(bottom_ul, "<li>", "</li>") if bottom_ul else []
            quality = self.cleanHtmlStr(bottom_items[0]) if len(bottom_items) > 0 else ""
            genre = self.cleanHtmlStr(bottom_items[1]) if len(bottom_items) > 1 else ""
            dots_info = self.cm.ph.getDataBeetwenMarkers(item, '<ul class="dots__info">', "</ul>", False)[1]
            dot_spans = self.cm.ph.getAllItemsBeetwenMarkers(dots_info, "<span>", "</span>") if dots_info else []
            year = self.cleanHtmlStr(dot_spans[0]) if len(dot_spans) > 0 else ""
            country = self.cleanHtmlStr(dot_spans[1]) if len(dot_spans) > 1 else ""
            story = self.cm.ph.getSearchGroups(item, r'<p class="story">([^<]+)</p>')[0].strip()
            desc_parts = []
            if quality:
                q_color = "green" if re.search(r"4K|1080|BluRay|FHD", quality, re.I) else "orange" if re.search(r"720|WEB|HDRip", quality, re.I) else "white"
                desc_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} {E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if genre:
                desc_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if year:
                desc_parts.append(f"{E2ColoR('yellow')}Year:{E2ColoR('white')} {year}")
            if country:
                desc_parts.append(f"{E2ColoR('yellow')}Country:{E2ColoR('white')} {country}")
            desc = " | ".join(desc_parts)
            if story:
                desc += f"\n{E2ColoR('yellow')}Story:{E2ColoR('white')} {story[:200]}{'...' if len(story) > 200 else ''}"
            clean_title = self.clean_title_prefix(title, sub_mode=2, url=cItem.get("url", ""))
            colored_title = self.colorizeTitle(clean_title)
            params = dict(cItem)
            params.update({"category": "series_seasons_list", "title": colored_title, "url": href, "icon": icon, "desc": desc, "csrf_token": token})
            self.addDir(params)
            printDBG(f"✓ Added: {title[:50]}...")
        next_match = re.search(r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"', data)
        if next_match:
            next_page = next_match.group(1).strip()
            if "arabseed.show" in next_page:
                next_page = next_page.replace("arabseed.show", "asd.ink")
            if next_page.startswith("//"):
                next_page = "https:" + next_page
            elif next_page.startswith("/"):
                next_page = self.MAIN_URL.rstrip("/") + next_page
            params = dict(cItem)
            params.update({"title": _("Next Page »»»"), "url": next_page, "category": "series_packs"})
            self.addDir(params)
            printDBG("Next page: %s" % next_page)
        printDBG("ArabSeed.listSeriesPacks <<< done")

    def listSeasons(self, cItem):
        printDBG("ArabSeed.listSeasons >>> %s" % cItem)
        url = cItem.get("url")
        csrf_token = cItem.get("csrf_token", "")
        if not url or not csrf_token:
            printDBG("[ArabSeed] Missing params in listSeasons")
            return
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("[ArabSeed] Failed to load series page")
            return
        trailer_url = self.cm.ph.getSearchGroups(data, r'data-iframe="([^"]+)"')[0]
        if trailer_url:
            if "youtube.com/embed/" in trailer_url:
                trailer_url = trailer_url.replace("youtube.com/embed/", "youtube.com/watch?v=")
            elif "imdb.com/video/" in trailer_url:
                pass
            params = dict(cItem)
            params.update({"title": f"{E2ColoR('lime')}TRAILER{E2ColoR('white')}", "url": trailer_url, "type": "video", "need_resolve": 1})
            self.addVideo(params)
        printDBG("[ArabSeed] trailer_url = %s" % trailer_url)
        seasons_block = self.cm.ph.getDataBeetwenMarkers(data, 'id="seasons__list"', "</div></div>", False)[1]
        if seasons_block:
            season_items = self.cm.ph.getAllItemsBeetwenMarkers(seasons_block, "<li", "</li>")
            for s in season_items:
                season_id = self.cm.ph.getSearchGroups(s, r'data-term="([^"]+)"')[0]
                title = self.cm.ph.getSearchGroups(s, r"<span>([^<]+)</span>")[0]
                if not season_id or not title:
                    continue
                params = dict(cItem)
                params.update({"category": "series_episodes_list", "title": title.strip(), "url": url, "season_id": season_id, "csrf_token": csrf_token})
                self.addDir(params)
            printDBG("ArabSeed.listSeasons <<< done with seasons")
        else:
            printDBG("[ArabSeed] No seasons found → trying direct episodes")
            episodes_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="episodes__list', "</ul>", False)[1]
            if episodes_block:
                episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, "<li", "</li>")
                episodes.reverse()
                for ep in episodes:
                    ep_url = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
                    if not ep_url:
                        continue
                    ep_num = self.cm.ph.getSearchGroups(ep, r"<b>(\d+)</b>")[0]
                    title = "الحلقة %s" % ep_num if ep_num else "حلقة"
                    params = dict(cItem)
                    params.update({"title": title, "url": ep_url + "watch/", "type": "video", "category": "explore_episodes"})
                    self.addDir(params)
                printDBG("ArabSeed.listSeasons <<< done with direct episodes")
                return
            promo_url = self.cm.ph.getSearchGroups(
                data,
                r'<div class="watch__and__download.*?<a href="([^"]+/watch/)"',
            )[0]
            if promo_url:
                printDBG("[ArabSeed] Single promo episode detected")
                params = dict(cItem)
                params.update({"title": f"{E2ColoR('yellow')}برومو المسلسل{E2ColoR('white')}", "url": promo_url, "type": "video", "category": "explore_episodes"})
                self.addDir(params)
                return
            printDBG("[ArabSeed] No episodes found at all")

    def getIMDBTrailer(self, url):
        printDBG("IMDB resolver start >>> %s" % url)
        links = []
        vid = self.cm.ph.getSearchGroups(url, r"(vi\d+)")[0]
        if not vid:
            printDBG("IMDB: video id not found")
            return []
        embed_url = "https://www.imdb.com/video/embed/%s/" % vid
        printDBG("IMDB embed URL >>> %s" % embed_url)
        sts, data = self.cm.getPage(embed_url)
        if not sts:
            printDBG("IMDB: failed to load embed page")
            return []
        json_data = self.cm.ph.getSearchGroups(data, r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')[0]
        if not json_data:
            printDBG("IMDB: __NEXT_DATA__ not found")
            return []
        json_data = json.loads(json_data)
        try:
            videoData = json_data["props"]["pageProps"].get("videoEmbedPlaybackData")
            if not videoData:
                printDBG("IMDB: videoEmbedPlaybackData not found")
                return []
            qualities = []
            for item in videoData.get("playbackURLs", []):
                mime = item.get("videoMimeType", "").lower()
                url = item.get("url")
                if not url:
                    continue
                if mime != "mp4":
                    continue
                display = item.get("displayName", {})
                quality_txt = display.get("value", "")
                try:
                    quality = int(quality_txt.replace("p", "").strip())
                except:
                    continue
                qualities.append({"q": quality, "name": "IMDb %dp" % quality, "url": url, "need_resolve": 0})
            qualities.sort(key=lambda x: x["q"], reverse=True)
            for q in qualities:
                links.append({"name": q["name"], "url": q["url"], "need_resolve": 0})
        except Exception as e:
            printDBG("IMDB extraction error: %s" % e)
        return links

    def listEpisodes(self, cItem):
        printDBG("ArabSeed.listEpisodes >>> %s" % cItem)
        url = cItem.get("url")
        season_id = cItem.get("season_id", "")
        csrf_token = cItem.get("csrf_token", "")
        if not url or not season_id or not csrf_token:
            printDBG("[ArabSeed] Missing required params")
            return
        sts, page_data = self.getPage(url)
        if sts:
            selected_season = self.cm.ph.getSearchGroups(page_data, r'<li[^>]+class="selected"[^>]+data-term="(\d+)"')[0]
            if selected_season == season_id:
                printDBG("[ArabSeed] First season detected")
                episodes = self.cm.ph.getAllItemsBeetwenMarkers(page_data, "<li", "</li>")
                episodes.reverse()
                count = 0
                for ep in episodes:
                    ep_num = self.cm.ph.getSearchGroups(ep, r"الحلقة[^0-9]*<b>(\d+)</b>")[0]
                    if not ep_num:
                        continue
                    ep_url = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
                    if not ep_url:
                        continue
                    ep_url += "watch/"
                    title = "الحلقة %s" % ep_num
                    icon = self.cm.ph.getSearchGroups(ep, r'data-src="([^"]+)"')[0] or cItem.get("icon", "")
                    params = dict(cItem)
                    params.update({"category": "explore_episodes", "type": "video", "title": title, "url": ep_url, "icon": icon})
                    self.addDir(params)
                    count += 1
                printDBG("Found %d episodes (first season clean)" % count)
                printDBG("ArabSeed.listEpisodes <<< done (first season)")
                return
        post_url = self.getFullUrl("/season__episodes/")
        post_data = {"season_id": season_id, "csrf_token": csrf_token}
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest", "Referer": url}
        sts, response = self.cm.getPage(post_url, {"header": headers}, post_data)
        if not sts:
            return
        try:
            result = json_loads(response)
        except:
            return
        if result.get("type") != "success":
            return
        html = result.get("html", "")
        episodes = self.cm.ph.getAllItemsBeetwenMarkers(html, "<li", "</li>")
        episodes.reverse()
        count = 0
        for ep in episodes:
            ep_num = self.cm.ph.getSearchGroups(ep, r"الحلقة[^0-9]*<b>(\d+)</b>")[0]
            if not ep_num:
                continue
            ep_url = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
            if not ep_url:
                continue
            ep_url += "watch/"
            title = "الحلقة %s" % ep_num
            icon = self.cm.ph.getSearchGroups(ep, r'data-src="([^"]+)"')[0] or cItem.get("icon", "")
            params = dict(cItem)
            params.update({"category": "explore_episodes", "type": "video", "title": title, "url": ep_url, "icon": icon})
            self.addDir(params)
            count += 1
        printDBG("Found %d episodes (ajax clean)" % count)
        printDBG("ArabSeed.listEpisodes <<< done (ajax)")

    def colorizeTitle(self, title):
        """
        Detects movie title and year in different formats and colorizes both.
        Handles: 2025, (2025), ( 2025 ), - 2025, [2025]
        """
        if not title:
            return title
        match = re.search(r"(.+?)\s*(?:\(|\[|-)?\s*(\d{4})\s*(?:\)|\])?$", title)
        if match:
            movie_title = match.group(1).strip()
            movie_year = match.group(2).strip()
            return f"{E2ColoR('yellow')}{movie_title} " f"{E2ColoR('cyan')}{movie_year}{E2ColoR('white')}"
        else:
            return f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

    def colorizeQuality(self, quality):
        """
        Detect quality level and assign colors
        """
        q_color = "white"
        if re.search(r"4K|1080|BluRay", quality, re.I):
            q_color = "green"
        elif re.search(r"720|HDRip|WEB", quality, re.I):
            q_color = "yellow"
        elif re.search(r"CAM|TS|HDCAM", quality, re.I):
            q_color = "red"
        return f"{E2ColoR(q_color)}{quality if quality else 'N/A'}{E2ColoR('white')}"

    def colorizeServer(self, name, quality):
        """
        Combine server name + quality with colorized labels
        """
        q_colored = self.colorizeQuality(str(quality))
        return f"{E2ColoR('cyan')}{name}{E2ColoR('white')} [{q_colored}]"

    def clean_title_prefix(self, title, sub_mode=-1, url=""):
        """
        تنظيف العناوين من البادئات: فيلم، مسلسل، برنامج، أنمي، أغنية، مسرحية
        """
        if not title:
            return title
        title = title.strip()
        is_anime_content = False
        if sub_mode == 4:
            is_anime_content = True
        elif url and any(kw in url.lower() for kw in ["cartoon", "anime", "انمي", "كرتون"]):
            is_anime_content = True
        is_program_content = False
        if sub_mode == 5:
            is_program_content = True
        elif url and any(kw in url.lower() for kw in ["program", "برامج", "برنامج"]):
            is_program_content = True
        prefixes_to_remove = []
        prefixes_to_remove.extend(
            [
                (r"فيلم\s+", True),
                (r"افلام\s+", True),
                (r"أفلام\s+", True),
            ]
        )
        if not is_anime_content:
            prefixes_to_remove.append((r"مسلسل\s+", True))
        if is_program_content or sub_mode in [2, 3, 5]:
            prefixes_to_remove.extend(
                [
                    (r"برنامج\s+", True),
                    (r"برامج\s+", True),
                ]
            )
        if is_anime_content:
            prefixes_to_remove.extend(
                [
                    (r"انمي\s+", True),
                    (r"أنمي\s+", True),
                    (r"انمي\:\s+", True),
                    (r"أنمي\:\s+", True),
                ]
            )
        prefixes_to_remove.extend(
            [
                (r"أغنية\s+", True),
                (r"اغنية\s+", True),
                (r"اغاني\s+", True),
                (r"أغاني\s+", True),
                (r"مسرحية\s+", True),
                (r"مسرحيات\s+", True),
            ]
        )
        for pattern, condition in prefixes_to_remove:
            if condition and re.match(pattern, title, re.I | re.UNICODE):
                title = re.sub(pattern, "", title, flags=re.I | re.UNICODE)
                break
        return title.strip()

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("ArabSeed.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "series":
            self.listSeriesItems(self.currItem)
        elif category == "movies_folder":
            self.listMoviesFolder(self.currItem)
        elif category == "series_folder":
            self.listSeriesFolder(self.currItem)
        elif category == "series_packs_folder":
            self.listSeriesPacksFolder(self.currItem)
        elif category == "series_packs":
            self.listSeriesPacks(self.currItem)
        elif category == "series_seasons_list":
            self.listSeasons(self.currItem)
        elif category == "series_episodes_list":
            self.listEpisodes(self.currItem)
        elif category == "explore_episodes":
            self.exploreSeriesItems(self.currItem)
        elif category == "ramadan_folder":
            self.listRamadanFolder(self.currItem)
        elif category == "anime_folder":
            self.listAnimeFolder(self.currItem)
        elif category == "other_folder":
            self.listOtherFolder(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
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
        CHostBase.__init__(self, ArabSeed(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
