# -*- coding: utf-8 -*-
# Last modified: 14/1/2026
# footyroom Host (Created By Dr HYTHAM MAHMOUD)
import re
import json

from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return "FootyRoom"


class FootyRoom(CBaseHostClass):
    MATCHES_PER_PAGE = 34  # عدد الملخصات في كل صفحة من البلجن
    MAX_PAGES_TO_FETCH = 12  # أقصى عدد صفحات نجلبها من الموقع (12 صفحة = ~240 مباراة)

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "footyroom.co", "cookie": "footyroom.co.cookie"})
        self.MAIN_URL = "https://footyroom.co/"
        self.DEFAULT_ICON_URL = "https://cdn.footyroom.co/pics/iphone/1024x1024.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update({"Referer": self.MAIN_URL})
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self._countriesCache = None
        self._matchesCache = {}  # key: base_url → value: list of all matches

    def _t(self, s):
        """Clean HTML text"""
        if not s:
            return ""
        try:
            s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
            s = re.sub(r"(?is)<[^>]+>", " ", s)
            s = " ".join(s.split()).strip()
            try:
                from six.moves.html_parser import HTMLParser

                s = HTMLParser().unescape(s)
            except:
                try:
                    import html

                    s = html.unescape(s)
                except:
                    pass
            return s.strip()
        except:
            return ""

    def _getPage(self, url, addParams=None, post_data=None):
        try:
            params = dict(self.defaultParams)
            if addParams:
                params.update(addParams)
                if "header" in addParams and "header" in params:
                    hdr = dict(self.defaultParams.get("header", {}))
                    hdr.update(addParams.get("header", {}))
                    params["header"] = hdr
            return self.cm.getPage(url, params, post_data)
        except:
            printExc()
        return False, ""

    def _absoluteUrl(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("javascript:"):
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("https://"):
            return url
        return self.getFullUrl(url)

    def _addPageParam(self, url, page):
        """Add ?page=X to URL"""
        if page <= 1:
            return url
        sep = "&" if "?" in url else "?"
        return url + sep + "page=%d" % page

    def _parseAllLeaguesMenu(self, data):
        """Parse leagues dropdown from main page"""
        out = []
        try:
            nav = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="dropdown-nav all-leagues', "</nav>", withMarkers=True)[1]
            if not nav:
                nav = data
            uls = self.cm.ph.getAllItemsBeetwenMarkers(nav, '<ul class="all-leagues-section', "</ul>", withMarkers=True)
            for ul in uls:
                header = self.cm.ph.getDataBeetwenMarkers(ul, '<li class="all-leagues-header', "</li>", withMarkers=True)[1]
                country = self._t(header)
                if not country:
                    continue
                comps = []
                links = self.cm.ph.getAllItemsBeetwenMarkers(ul, "<a ", "</a>", withMarkers=True)
                for a in links:
                    href = self.cm.ph.getSearchGroups(a, r"""href=['"]([^'"]+)['"]""")[0]
                    title = self._t(a)
                    href = self._absoluteUrl(href)
                    if not href or not title:
                        continue
                    if "/competitions/" in href:
                        comps.append({"title": title, "url": href})
                if comps:
                    out.append({"title": country, "comps": comps})
        except:
            printExc()
        return out

    def _getCountries(self, force=False):
        """Get or retrieve cached countries list"""
        if (not force) and self._countriesCache is not None:
            return self._countriesCache
        sts, data = self._getPage(self.MAIN_URL, {"header": {"Referer": self.MAIN_URL}})
        if not sts:
            self._countriesCache = []
            return self._countriesCache
        self._countriesCache = self._parseAllLeaguesMenu(data) or []
        printDBG("FootyRoom._getCountries: countries=%d" % len(self._countriesCache))
        return self._countriesCache

    # ---------------------------------------------------------
    # استخراج المباريات من صفحة واحدة
    # ---------------------------------------------------------
    def _extractMatchesFromPage(self, data):
        """
        Extract matches from single page HTML
        Returns: list of {'title':..., 'url':..., 'icon':...}
        """
        matches = []
        added = set()
        # 1) Card grid (الأفضل: thumbnails من YouTube)
        card_blocks = re.findall(r'(?is)<div[^>]+class=["\'][^"\']*\bcard\b[^"\']*["\'][^>]*>(.*?)</div>\s*</div>\s*</div>', data)
        if not card_blocks:
            card_blocks = re.findall(r'(?is)<div[^>]+class=["\'][^"\']*\bcard-image\b[^"\']*["\'][^>]*>(.*?)</div>', data)
        for blk in card_blocks:
            href = re.search(r'(?is)href=["\'](https?://[^"\']+/matches/[^"\']+/review[^"\']*)["\']', blk)
            if not href:
                href = re.search(r'(?is)href=["\']([^"\']+/matches/[^"\']+/review[^"\']*)["\']', blk)
            if not href:
                continue
            url = self._absoluteUrl(href.group(1))
            url_norm = url.split("?")[0].split("#")[0].strip()
            if not url_norm or url_norm in added:
                continue
            img = re.search(r'(?is)<img[^>]+src=["\']([^"\']+)["\']', blk)
            icon = self._absoluteUrl(img.group(1)) if img else self.DEFAULT_ICON_URL
            title = ""
            t = re.search(r'(?is)class=["\'][^"\']*\bnot-spoiler\b[^"\']*["\'][^>]*>(.*?)</a>', blk)
            if t:
                title = self._t(t.group(1))
            if not title:
                t = re.search(r'(?is)class=["\'][^"\']*\bspoiler\b[^"\']*["\'][^>]*>(.*?)</a>', blk)
                if t:
                    title = self._t(t.group(1))
            if not title:
                try:
                    slug = url_norm.split("/matches/")[-1].replace("/review", "")
                    slug = re.sub(r"^\d+/", "", slug)
                    title = slug.replace("-", " ").strip()
                except:
                    title = "Match"
            added.add(url_norm)
            matches.append({"title": title or "Match", "url": url_norm, "icon": icon})
        if matches:
            return matches
        # 2) Fallback: tournament-guide-match (قد لا يحتوي صور)
        match_blocks = re.findall(r'(?is)<div[^>]*class=["\']tournament-guide-match[^"\']*["\'][^>]*>(.*?)</div>\s*</div>', data)
        for block in match_blocks:
            href_match = re.search(r'(?is)href=[\'"]([^\'"]*?/matches[^\'"]*?/review[^\'"]*?)[\'"]', block)
            if not href_match:
                continue
            href = self._absoluteUrl(href_match.group(1))
            if not href:
                continue
            href_norm = href.split("?")[0].split("#")[0].strip()
            if href_norm in added:
                continue
            added.add(href_norm)
            teams = re.findall(r'(?is)<div[^>]*class=["\']tournament-guide-team[^"\']*["\'][^>]*>(.*?)</div>', block)
            if len(teams) >= 2:
                team1 = self._t(teams[0]).strip()
                team2 = self._t(teams[1]).strip()
                title = (team1 + " vs " + team2).strip() if team1 and team2 else ""
            else:
                title = ""
            if not title:
                try:
                    slug = href_norm.split("/matches/")[-1].replace("/review", "")
                    slug = re.sub(r"^\d+/", "", slug)
                    title = slug.replace("-", " ").strip()
                except:
                    title = "Match"
            matches.append({"title": title or "Match", "url": href_norm, "icon": self.DEFAULT_ICON_URL})
        return matches

    # ---------------------------------------------------------
    # جلب جميع المباريات من البطولة (صفحات متعددة)
    # ---------------------------------------------------------
    def _loadAllMatchesForCompetition(self, base_url):
        """
        جلب جميع المباريات لبطولة معينة عن طريق:
        1. جلب ?page=1, ?page=2, ?page=3... حتى MAX_PAGES_TO_FETCH
        2. التوقف إذا لم تعد تأتي مباريات جديدة
        Returns: list of all matches
        """
        all_matches = []
        added_urls = set()
        for page_num in range(1, self.MAX_PAGES_TO_FETCH + 1):
            url = self._addPageParam(base_url, page_num)
            printDBG("FootyRoom: Fetching page %d: %s" % (page_num, url))
            sts, data = self._getPage(url, {"header": {"Referer": self.MAIN_URL}})
            if not sts or not data:
                printDBG("FootyRoom: Failed to fetch page %d" % page_num)
                break
            page_matches = self._extractMatchesFromPage(data)
            if not page_matches:
                printDBG("FootyRoom: No matches found on page %d, stopping" % page_num)
                break
            # نضيف المباريات الجديدة فقط
            new_count = 0
            for match in page_matches:
                url_key = match["url"]
                if url_key not in added_urls:
                    added_urls.add(url_key)
                    all_matches.append(match)
                    new_count += 1
            printDBG("FootyRoom: Page %d → got %d matches, %d new, total now: %d" % (page_num, len(page_matches), new_count, len(all_matches)))
            # إذا لم نحصل على مباريات جديدة → توقف
            if new_count == 0:
                printDBG("FootyRoom: No new matches on page %d, stopping" % page_num)
                break
            # إذا جمعنا عدد كافي للـ pagination (مثلاً 100+)، يمكن التوقف
            # لكن نترك الخيار لجلب كل شيء حتى MAX_PAGES
            # إذا تريد توقف بدري: uncomment السطر التالي
            # if len(all_matches) >= 100:
            #     break
        printDBG("FootyRoom: Total matches collected: %d" % len(all_matches))
        return all_matches

    # ----------------- MENUS -----------------
    def listMainMenu(self, cItem):
        """عرض الدول مباشرة"""
        self.currList = []
        countries = self._getCountries(force=True)
        for idx, item in enumerate(countries):
            self.addDir({"name": "category", "title": item.get("title", ""), "category": "list_competitions", "country_idx": str(idx), "icon": self.DEFAULT_ICON_URL})

    def listCompetitions(self, cItem):
        """عرض البطولات لدولة معينة"""
        self.currList = []
        countries = self._getCountries(force=True)
        try:
            idx = int(str(cItem.get("country_idx", "-1")).strip())
        except:
            idx = -1
        comps = []
        if 0 <= idx < len(countries):
            comps = countries[idx].get("comps", []) or []
        printDBG("FootyRoom.listCompetitions: country=%s comps=%d" % (cItem.get("title", ""), len(comps)))
        for comp in comps:
            title = (comp.get("title") or "").strip() or "Competition"
            url = (comp.get("url") or "").strip()
            if not url:
                continue
            self.addDir({"name": "category", "title": title, "category": "list_matches", "url": url, "page": 1, "icon": self.DEFAULT_ICON_URL})

    def listMatches(self, cItem):
        """
        عرض المباريات (34 في كل صفحة) + Next page
        يجلب جميع المباريات من الموقع ويخزنها في الكاش
        """
        self.currList = []
        page = int(cItem.get("page", 1))
        base_url = cItem["url"]
        # نفحص هل المباريات موجودة في الكاش
        cache_key = base_url
        if cache_key not in self._matchesCache:
            printDBG("FootyRoom: Loading ALL matches for: %s" % base_url)
            all_matches = self._loadAllMatchesForCompetition(base_url)
            self._matchesCache[cache_key] = all_matches
            printDBG("FootyRoom: Cached %d matches for %s" % (len(all_matches), cache_key))
        else:
            all_matches = self._matchesCache[cache_key]
            printDBG("FootyRoom: Using cached %d matches for %s" % (len(all_matches), cache_key))
        # حساب النطاق للصفحة الحالية
        total_matches = len(all_matches)
        start_idx = (page - 1) * self.MATCHES_PER_PAGE
        end_idx = start_idx + self.MATCHES_PER_PAGE
        page_matches = all_matches[start_idx:end_idx]
        printDBG("FootyRoom: Showing page %d: matches %d-%d of %d total" % (page, start_idx + 1, min(end_idx, total_matches), total_matches))
        # عرض المباريات
        for match in page_matches:
            self.addVideo({"name": "video", "title": match.get("title", ""), "url": match.get("url", ""), "icon": match.get("icon", self.DEFAULT_ICON_URL)})
        # عرض Next page إذا يوجد مباريات أكثر
        if end_idx < total_matches:
            params = dict(cItem)
            params.update({"title": "Next page", "category": "list_matches", "page": page + 1})
            self.addDir(params)

    # ----------------- VIDEO LINKS -----------------
    def getLinksForVideo(self, cItem):
        """Extract video links from DataStore.media"""
        urlTab = []
        sts, data = self._getPage(cItem["url"], {"header": {"Referer": self.MAIN_URL}})
        if not sts:
            return urlTab
        # 1) Parse DataStore.media JSON
        m = re.search(r"DataStore\.media\s*=\s*(\[.*?\]);", data, re.DOTALL)
        if m:
            try:
                media_json = json.loads(m.group(1))
                for item in media_json:
                    src = (item.get("source") or "").strip()
                    title = (item.get("title") or "Video").strip()
                    provider = (item.get("provider") or "Unknown").strip()
                    if not src or "photo-resources" in src or ".jpg" in src or ".png" in src:
                        continue
                    if "youtube.com" in src or "youtu.be" in src:
                        vid = re.search(r"(?:youtu\.be/|youtube\.com/(?:embed/|watch\?v=))([A-Za-z0-9_-]{11})", src)
                        if vid:
                            src = "https://www.youtube.com/watch?v=" + vid.group(1)
                    if src:
                        urlTab.append({"name": provider + ": " + title[:50], "url": src, "need_resolve": 1})
            except:
                printExc()
        # 2) Fallback: JSON-LD
        if not urlTab:
            ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', data, re.DOTALL | re.IGNORECASE)
            if ld:
                try:
                    ld_data = json.loads(ld.group(1))
                    embed = ld_data.get("embedUrl", "")
                    if embed and "youtube" in embed:
                        urlTab.append({"name": "YouTube", "url": embed.replace("/embed/", "/watch?v="), "need_resolve": 1})
                except:
                    printExc()
        return urlTab

    def getVideoLinks(self, url):
        """Resolve video URL via urlparser"""
        try:
            return self.up.getVideoLinkExt(url)
        except:
            printExc()
        return []

    # ----------------- DISPATCHER -----------------
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        self.currList = []
        try:
            name = (self.currItem.get("name", "") or "").strip()
            category = (self.currItem.get("category", "") or "").strip()
            printDBG("FootyRoom.handleService: name[%s] category[%s]" % (name, category))
            if name == "":
                self.listMainMenu(self.currItem)
            elif category == "list_competitions":
                self.listCompetitions(self.currItem)
            elif category == "list_matches":
                self.listMatches(self.currItem)
            else:
                self.listMainMenu(self.currItem)
        except:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, FootyRoom(), True, [])
