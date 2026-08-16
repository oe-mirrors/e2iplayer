# -*- coding: utf-8 -*-
# Last modified: 3/1/2026
# Aradrama Host (Created By Dr HYTHAM MAHMOUD)
import re
from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry

# from Plugins.Extensions.IPTVPlayer.compat import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import MergeDicts, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvtools import ParseColor
except Exception:

    def ParseColor(color, text):
        return text


TRAILER_LABEL = "Trailer"
ALT_TITLE_REGEX = r'alt=[\'"]([^"^\']+?)[\'"]'
# -------------------- config --------------------
config.plugins.iptvplayer.aradramtv_proxy = ConfigSelection(default="None", choices=[("None", _("None")), ("proxy_1", _("Alternative proxy server (1)")), ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.aradramtv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    tab = []
    tab.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.aradramtv_proxy))
    if config.plugins.iptvplayer.aradramtv_proxy.value == "None":
        tab.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.aradramtv_alt_domain))
    return tab


def gettytul():
    return "ARADrama"


class ARADrama(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "aradramtv", "cookie": "aradramtv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "https://aradramatv.cc/wp-content/uploads/logo-v3.1.png"
        self.HEADER = self.cm.getDefaultHeader("chrome")
        self.HEADER.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})
        self.defaultParams = {"header": self.HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    # -------------------- net --------------------
    def getProxy(self):
        proxy = config.plugins.iptvplayer.aradramtv_proxy.value
        if proxy != "None":
            if proxy == "proxy_1":
                return config.plugins.iptvplayer.alternative_proxy1.value
            return config.plugins.iptvplayer.alternative_proxy2.value
        return None

    def _withProxy(self, params):
        proxy = self.getProxy()
        if proxy:
            params = MergeDicts(params, {"http_proxy": proxy})
        return params

    def _ensureReferer(self, params, url):
        try:
            hdr = params.get("header", {})
            if "Referer" not in hdr:
                hdr = dict(hdr)
                hdr["Referer"] = self.getMainUrl() or self.getFullUrl("/")
                params["header"] = hdr
        except Exception:
            pass
        return params

    def getPage(self, baseUrl, addParams=None, post_data=None):
        params = dict(self.defaultParams)
        if addParams:
            try:
                params.update(addParams)
            except Exception:
                pass
        params = self._withProxy(params)
        params = self._ensureReferer(params, baseUrl)
        try:
            if hasattr(self.cm, "getPageCFFProtection"):
                return self.cm.getPageCFProtection(baseUrl, params, post_data)
        except Exception:
            pass
        try:
            if hasattr(self.cm, "getPageCFProtection"):
                return self.cm.getPageCFProtection(baseUrl, params, post_data)
        except Exception:
            pass
        return self.cm.getPage(baseUrl, params, post_data)

    def selectDomain(self):
        domains = [
            "https://aradramatv.cc/",
            "https://aradramatv.co/",
            "https://aradramtv.com/",
            "https://aradramatv.com/",
        ]
        alt = config.plugins.iptvplayer.aradramtv_alt_domain.value.strip()
        if self.cm.isValidUrl(alt):
            if not alt.endswith("/"):
                alt += "/"
            domains.insert(0, alt)
        for d in domains:
            sts, data = self.getPage(d)
            if sts and data and ("Aradrama" in data or "wp-content" in data or "page-content" in data):
                try:
                    self.setMainUrl(self.cm.meta.get("url", d))
                except Exception:
                    self.setMainUrl(d)
                self.MAIN_URL = self.getMainUrl()
                return
        if self.MAIN_URL is None:
            self.setMainUrl(domains[0])
            self.MAIN_URL = self.getMainUrl()

    # -------------------- text helpers --------------------
    def _cleanTitle(self, s):
        if not s:
            return ""
        s = s.strip()
        if (">" in s) and (s.startswith("class=") or s.startswith("id=") or s.startswith("style=") or s.startswith("data-")):
            s = s.split(">", 1)[-1]
        s = self.cleanHtmlStr(s).strip()
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _normalizeTitle(self, s):
        s = self._cleanTitle(s)
        if not s:
            return ""
        s = s.replace("<", "").replace(">", "").replace("‹", "").replace("›", "").replace("«", "").replace("»", "")
        s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", s)
        s = re.sub(r"\b[0-9٠-٩]{5,}\b", "", s)  # remove long numeric ids
        s = re.sub(r"\s*-\s*", " - ", s)
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"^\s*-\s*", "", s).strip()
        s = re.sub(r"\s*-\s*$", "", s).strip()
        return s

    # ---------- RTL fix (Isolates + manual wrap) ----------
    def _stripBidi(self, s):
        if not s:
            return ""
        return re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", s)

    def _wrapTextBlock(self, text, width=74):
        if not text:
            return ""
        out = []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                out.append("")
                continue
            words = ln.split()
            cur = ""
            for w in words:
                if not cur:
                    cur = w
                elif len(cur) + 1 + len(w) <= width:
                    cur += " " + w
                else:
                    out.append(cur)
                    cur = w
            if cur:
                out.append(cur)
        return "\n".join(out)

    def _stripLeadingDashesPerLine(self, text):
        """
        ✅ إزالة أي شرطة/داش في بداية كل سطر بعد اللفّ.
        يشمل: -  –  —  ـ
        """
        if not text:
            return ""
        fixed = []
        for ln in text.splitlines():
            # remove leading dashes/em-dashes/tatweel and spaces
            ln = re.sub(r"^\s*([\-–—ـ]+)\s*", "", ln)
            fixed.append(ln)
        return "\n".join(fixed)

    def _isolateLTRRuns(self, s):
        if not s:
            return ""
        LRI = "\u2066"
        RLI = "\u2067"
        PDI = "\u2069"

        def repl(m):
            t = m.group(0)
            return LRI + t + PDI

        s = re.sub(r"[A-Za-z0-9][A-Za-z0-9\-\._:/ ]*", repl, s)
        s = RLI + s + PDI
        return s

    def _forceRTLText(self, text):
        if not text:
            return ""
        text = self._stripBidi(text)
        lines = []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                lines.append("")
                continue
            ln = "\u200f" + self._isolateLTRRuns(ln)
            lines.append(ln)
        return "\n".join(lines)

    # -------------------- extract helpers --------------------
    def _extractTrailerUrl(self, data):
        block = ""
        for marker in ("tab-trailer-1", "tab-trailer", "trailer"):
            tmp = self.cm.ph.getDataBeetwenMarkers(data, marker, "</iframe", False)[1]
            if tmp:
                block = tmp + "</iframe>"
                break
        if not block:
            return ""
        src = self.cm.ph.getSearchGroups(block, r'<iframe[^>]+src=[\'"]([^\'"]+)[\'"]')[0].strip()
        if not src:
            return ""
        if not self.cm.isValidUrl(src):
            src = self.getFullUrl(src)
        low = src.lower()
        if any(low.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return ""
        return src

    def _hasServersOnPage(self, data):
        if "data-url=" in data:
            return True
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "Servrs", "</div", False)[1]
        return "data-url=" in tmp

    def _getPlayableIframe(self, data):
        srcs = re.findall(r'<iframe[^>]+src=[\'"]([^\'"]+)[\'"]', data, flags=re.I)
        for s in srcs:
            s = (s or "").strip()
            if not s:
                continue
            low = s.lower()
            if ("youtube.com" in low) or ("youtu.be" in low) or ("vimeo.com" in low):
                continue
            if any(low.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                continue
            if not self.cm.isValidUrl(s):
                s = self.getFullUrl(s)
            if self.cm.isValidUrl(s):
                return s
        return ""

    def _extractPoster(self, data):
        img = self.cm.ph.getSearchGroups(data, r'<meta[^>]+property=[\'"]og:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]')[0]
        if not img:
            img = self.cm.ph.getSearchGroups(data, r'<meta[^>]+name=[\'"]twitter:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]')[0]
        if img and (not self.cm.isValidUrl(img)):
            img = self.getFullUrl(img)
        return img

    def _getStory(self, data):
        descBlock = self.cm.ph.getDataBeetwenMarkers(data, "b_block s-desc", "</div", False)[1]
        if descBlock:
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descBlock, "القصة", "<br", False)[1]).strip()
            if story:
                return story
        metaDesc = self.cm.ph.getSearchGroups(data, r'<meta[^>]+name=[\'"]description[\'"][^>]+content=[\'"]([^\'"]+)[\'"]')[0]
        metaDesc = self._cleanTitle(metaDesc)
        if metaDesc:
            if ("البرنامج" in metaDesc and "+" in metaDesc) or ("جميع الحلقات" in metaDesc):
                return ""
            return metaDesc
        p = self.cm.ph.getDataBeetwenMarkers(data, "<p", "</p>", False)[1]
        return self._cleanTitle(p)

    def getFullIconUrl(self, url):
        iconUrl = CBaseHostClass.getFullIconUrl(self, (url or "").strip())
        if not iconUrl:
            return ""
        proxy = self.getProxy()
        if proxy:
            iconUrl = strwithmeta(iconUrl, {"iptv_http_proxy": proxy})
        return iconUrl

    # -------------------- INFO parse + format --------------------
    def _getDescHtml(self, data):
        for a, b in [
            ("b_block s-desc", "</div"),
            ('class="b_block s-desc"', "</div"),
            ('class="s-desc"', "</div"),
            ('class="entry-content"', "</div"),
            ('class="post-content"', "</div"),
            ('class="post_content"', "</div"),
        ]:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, a, b, False)[1]
            if tmp:
                return tmp
        return ""

    def _parsePairsArabic(self, html):
        info = {}
        if not html:
            return info
        t = html.replace("<br", "\n<br")
        t = self.cleanHtmlStr(t)
        t = t.replace("\r", "\n")
        t = re.sub(r"\n+", "\n", t)
        t = t.replace("القصة", "\nالقصة")
        t = t.replace("أبطال الدراما", "\nأبطال الدراما")
        wanted = set(["اسم المسلسل", "الاسم", "الاسم العربي", "يعرف أيضا بـ", "يعرف أيضًا بـ", "النوع", "عدد الحلقات", "الحلقات", "البلد المنتج", "المنتج", "شبكة العرض", "موعد البث", "موعد", "أيام العرض"])
        for line in t.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = self._cleanTitle(k)
            v = self._cleanTitle(v)
            if not k or not v:
                continue
            if k in wanted:
                info[k] = v
        if "الاسم" in info and "اسم المسلسل" not in info:
            info["اسم المسلسل"] = info.pop("الاسم")
        if "يعرف أيضًا بـ" in info and "يعرف أيضا بـ" not in info:
            info["يعرف أيضا بـ"] = info.pop("يعرف أيضًا بـ")
        if "الحلقات" in info and "عدد الحلقات" not in info:
            info["عدد الحلقات"] = info.pop("الحلقات")
        if "المنتج" in info and "البلد المنتج" not in info:
            info["البلد المنتج"] = info.pop("المنتج")
        if "موعد" in info and "موعد البث" not in info:
            info["موعد البث"] = info.pop("موعد")
        return info

    def _extractStoryAndCast(self, html):
        story = ""
        cast = ""
        if not html:
            return story, cast
        t = html.replace("<br", "\n<br")
        t = self.cleanHtmlStr(t)
        t = t.replace("\r", "\n")
        t = re.sub(r"\n+", "\n", t)
        t = t.replace("القصة", "\nالقصة")
        t = t.replace("أبطال الدراما", "\nأبطال الدراما")
        m = re.search(r"القصة\s*:?\s*(.+)", t)
        if m:
            story = m.group(1).strip()
            if "أبطال الدراما" in story:
                story = story.split("أبطال الدراما", 1)[0].strip()
        story = self._cleanTitle(story)
        if "أبطال الدراما" in t:
            after = t.split("أبطال الدراما", 1)[1]
            after = after.replace(":", "").strip()
            after = re.sub(r"\n+", "\n", after).strip()
            lines = []
            for a, r1 in re.findall(r"([A-Za-z0-9\-\_\.]+)\s*:\s*في\s*دور\s*(.+)", after):
                a = a.strip()
                r1 = r1.strip()
                if a and r1:
                    lines.append("%s : في دور %s" % (a, r1))
            cast = "\n".join(lines) if lines else after
        return story, cast

    def _buildPrettyInfoText(self, info, story, cast):
        order = [
            "اسم المسلسل",
            "الاسم العربي",
            "يعرف أيضا بـ",
            "النوع",
            "عدد الحلقات",
            "البلد المنتج",
            "شبكة العرض",
            "موعد البث",
            "أيام العرض",
        ]
        lines = []
        for k in order:
            if k in info and info[k]:
                lines.append("%s : %s" % (k, info[k]))
        # ✅ لون أزرق داكن لكلمة "القصة"
        storyLabel = ParseColor("#1b3f8b", "القصة")
        if story:
            lines.append("%s : %s" % (storyLabel, story))
        if cast:
            if "\n" in cast:
                lines.append("أبطال الدراما :\n%s" % cast)
            else:
                lines.append("أبطال الدراما : %s" % cast)
        return "\n".join(lines).strip()

    # -------------------- menus --------------------
    def listMainMenu(self, cItem):
        printDBG("ARADrama.listMainMenu")
        tab = [{"category": "movies", "title": "الأفـــلام", "icon": self.DEFAULT_ICON_URL}, {"category": "series", "title": "مســلـســلات", "icon": self.DEFAULT_ICON_URL}, {"category": "tvshow", "title": "بــرامــج", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/k-shows/")}] + self.searchItems()
        self.listsTab(tab, cItem)

    def listCatItems(self, cItem, nextCategory):
        printDBG("ARADrama.listCatItems cItem[%s]" % cItem)
        cat = self.currItem.get("category", "")
        if cat == "movies":
            tab = [
                {"category": nextCategory, "title": "أفلام أسيوية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/%d8%a7%d9%84%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%84%d8%a2%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/")},
                {"category": nextCategory, "title": "أفلام كورية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/type/k-movies/")},
                {"category": nextCategory, "title": "أفلام صينية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/type/c-movies/")},
                {"category": nextCategory, "title": "أفلام يابانية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/type/j-movie/")},
                {"category": nextCategory, "title": "أفلام تايوانية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/type/فيلم-تايواني/")},
                {"category": nextCategory, "title": "أفلام فيتنامية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/type/فيلم-فيتنامي/")},
            ]
        elif cat == "series":
            tab = [
                {"category": nextCategory, "title": "الدراما الكورية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/serie/korea/")},
                {"category": nextCategory, "title": "الدراما اليابانية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/serie/japanese/")},
                {"category": nextCategory, "title": "الدراما الصينيةوالتايوانية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/serie/chinese-taiwan/")},
                {"category": nextCategory, "title": "الدراما التايلاندية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/serie/tailand/")},
                {"category": nextCategory, "title": "الدراما الفلبينية", "icon": self.DEFAULT_ICON_URL, "url": self.getFullUrl("/category/serie/f-drama/")},
            ]
        else:
            tab = []
        self.listsTab(tab, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("ARADrama.listItems cItem[%s]" % cItem)
        pageKey = "page"
        page = cItem.get(pageKey, 1)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("ARADrama.listItems: getPage failed.")
            return
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="wp-pagenavi">', "</div>", False)[1]
        nextUrl = ""
        if pagination:
            items = self.cm.ph.getAllItemsBeetwenMarkers(pagination, "<a", "</a>", withMarkers=True)
            for a in items:
                href = self.cm.ph.getSearchGroups(a, r'href=[\'"]([^\'"]+?)[\'"]')[0]
                num = self.cleanHtmlStr(a)
                if (num.isdigit() and int(num) == page + 1) or ("»" in num and page == 1):
                    nextUrl = self.getFullUrl(href)
                    break
        main = self.cm.ph.getDataBeetwenMarkers(data, '<div id="T20_container" class="page-content">', "<footer", False)[1]
        if not main:
            main = data
        posts = self.cm.ph.getAllItemsBeetwenMarkers(main, "<article", "</article>", withMarkers=True)
        for item in posts:
            img = self.cm.ph.getSearchGroups(item, r'<img[^>]+src=[\'"]([^\'"]+?)[\'"]')[0]
            icon = self.getFullIconUrl(img)
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+class=[\'"]first_A[\'"][^>]+href=[\'"]([^\'"]+?)[\'"]')[0]
            if not href:
                href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href=[\'"]([^\'"]+?)[\'"]')[0]
            url = self.getFullUrl(href)
            title = self.cm.ph.getSearchGroups(item, r"<h[23][^>]*>\s*<a[^>]*>(.*?)</a>\s*</h[23]>")[0]
            if not title:
                title = self.cm.ph.getDataBeetwenMarkers(item, "<h3", "</h3>", False)[1]
            title = self._normalizeTitle(title)
            if not title:
                title = self._normalizeTitle(self.cm.ph.getSearchGroups(item, ALT_TITLE_REGEX)[0])
            if not url or not title:
                continue
            params = dict(cItem)
            params.update({"category": nextCategory, "good_for_fav": True, "EPG": True, "title": title, "url": url, "icon": icon or self.DEFAULT_ICON_URL, "desc": ""})
            self.addDir(params)
        if nextUrl:
            params = dict(cItem)
            params.update({"title": _("Next page"), "url": nextUrl, pageKey: page + 1})
            self.addDir(params)

    # -------------------- explore --------------------
    def exploreItems(self, cItem):
        printDBG("ARADrama.exploreItems cItem[%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        cItem["prev_url"] = cItem["url"]
        trailerUrl = self._extractTrailerUrl(data)
        if self.cm.isValidUrl(trailerUrl):
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": "[%s]" % (ParseColor("#6082b6", TRAILER_LABEL)), "url": trailerUrl, "desc": ""})
            self.addVideo(params)
        story = self._getStory(data)
        baseTitle = self._normalizeTitle(cItem.get("title", ""))
        if self._hasServersOnPage(data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "EPG": True, "title": baseTitle, "url": cItem["url"], "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": story})
            self.addVideo(params)
        else:
            playIframe = self._getPlayableIframe(data)
            if self.cm.isValidUrl(playIframe):
                params = dict(cItem)
                params.update({"good_for_fav": True, "EPG": True, "title": "%s - %s" % (baseTitle, "مشاهدة"), "url": playIframe, "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": story})
                self.addVideo(params)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "vc_btn3-inline", "</div>", False)[1]
        href = self.cm.ph.getSearchGroups(tmp, r'href=[\'"]([^\'"]+?)[\'"]')[0]
        if not href:
            return
        if "?" in href:
            url = self.getFullUrl("?" + href.split("?", 1)[1])
        else:
            url = self.getFullUrl(href)
        sts, data2 = self.getPage(url)
        if not sts or not data2:
            return
        main = self.cm.ph.getDataBeetwenMarkers(data2, '<div id="T20_container" class="page-content">', "<footer", False)[1]
        if not main:
            main = data2
        posts = self.cm.ph.getAllItemsBeetwenMarkers(main, "<article", "</article>", withMarkers=True)
        for item in posts:
            epUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'<a[^>]+href=[\'"]([^\'"]+?)[\'"]')[0])
            epTitle = self.cm.ph.getSearchGroups(item, r"<h[23][^>]*>\s*<a[^>]*>(.*?)</a>\s*</h[23]>")[0]
            if not epTitle:
                epTitle = self.cm.ph.getDataBeetwenMarkers(item, "<h3", "</h3>", False)[1]
            epTitle = self._normalizeTitle(epTitle)
            if not epUrl or not epTitle:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "EPG": True, "title": epTitle, "url": epUrl, "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": story})
            self.addVideo(params)

    # -------------------- search --------------------
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ARADrama.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern))
        params = {"name": "category", "good_for_fav": False, "url": url}
        self.listItems(params, "explore_item")

    # -------------------- links --------------------
    def getLinksForVideo(self, cItem):
        printDBG("ARADrama.getLinksForVideo [%s]" % cItem)
        if TRAILER_LABEL in cItem.get("title", ""):
            return self.up.getVideoLinkExt(cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            if self.cm.isValidUrl(cItem.get("url", "")):
                return self.up.getVideoLinkExt(cItem["url"])
            return []
        meta = {}
        try:
            meta = getattr(data, "meta", {}) or {}
        except Exception:
            meta = {}
        referer = meta.get("url", cItem["url"])
        found = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "Servrs", "</div>", False)[1]
        servers = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<li", "</li>", withMarkers=True)
        for s in servers:
            u = self.cm.ph.getSearchGroups(s, r'data-url=[\\\'"]([^"^\\\']+?)[\\\'"]')[0]
            if u:
                found.append(u)
        if not found:
            found = re.findall(r'data-url=[\'"]([^\'"]+)[\'"]', data, flags=re.I)
        if not found:
            iframe = self._getPlayableIframe(data)
            if self.cm.isValidUrl(iframe):
                return self.up.getVideoLinkExt(iframe)
        linksTab = []
        baseTitle = self._normalizeTitle(cItem.get("title", ""))
        for u in found:
            host = self.up.getHostName(u, True)
            label = "%s - %s" % (host, baseTitle)
            linksTab.append({"name": label, "url": strwithmeta(u, {"Referer": referer}), "need_resolve": 1})
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("ARADrama.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    # -------------------- info (RTL fixed) --------------------
    def getArticleContent(self, cItem):
        printDBG("ARADrama.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        if "prev_url" in cItem:
            url = cItem["prev_url"]
        sts, data = self.getPage(url)
        if not sts or not data:
            return []
        poster = self._extractPoster(data) or cItem.get("icon", "")
        descHtml = self._getDescHtml(data)
        info = self._parsePairsArabic(descHtml)
        storyFromBlock, cast = self._extractStoryAndCast(descHtml)
        story = storyFromBlock or self._getStory(data) or cItem.get("desc", "")
        story = self._cleanTitle(story)
        title = self._normalizeTitle(cItem.get("title", "") or info.get("اسم المسلسل", ""))
        if not title:
            title = self._normalizeTitle(self.cm.ph.getSearchGroups(data, r"<title>([^<]+)</title>")[0])
        text = self._buildPrettyInfoText(info, story, cast)
        # ✅ لفّ يدوي ثم إزالة الداش من بداية السطر ثم RTL isolates
        title = self._forceRTLText(title).replace("\n", " ")
        text = self._wrapTextBlock(text, width=74)
        text = self._stripLeadingDashesPerLine(text)
        text = self._forceRTLText(text)
        return [{"title": title, "text": text, "images": [{"title": "", "url": poster}], "other_info": {}}]

    # -------------------- service --------------------
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        try:
            CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        except TypeError:
            try:
                CBaseHostClass.handleService(self, index, refresh, searchPattern)
            except TypeError:
                CBaseHostClass.handleService(self, index, refresh)
        if self.MAIN_URL is None:
            self.selectDomain()
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        try:
            if not name and not category:
                self.listMainMenu({"name": "category", "type": "category"})
            elif category in ("series", "movies"):
                self.listCatItems(self.currItem, "listItems")
            elif category in ("listItems", "tvshow"):
                self.listItems(self.currItem, "explore_item")
            elif category == "explore_item":
                self.exploreItems(self.currItem)
            elif category in ("search", "search_next_page"):
                cItem = dict(self.currItem)
                cItem.update({"search_item": False, "name": "category"})
                self.listSearchResult(cItem, searchPattern, searchType)
            elif category == "search_history":
                self.listsHistory({"name": "history", "category": "search"}, "desc")
            else:
                printExc()
        except Exception:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, ARADrama(), True, [])

    def withArticleContent(self, cItem):
        if "EPG" in cItem or "prev_url" in cItem or cItem.get("category", "") == "explore_item":
            return True
        return False
