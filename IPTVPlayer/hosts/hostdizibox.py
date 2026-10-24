# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   dizibox.live (WordPress, dizibox.com redirects there): foreign TV series with Turkish subtitles - latest and
#   popular episodes, series archive (sort, genres, countries), A-Z and search over the site's series index
#   streams: every episode page has one player per sub page (/, /2/, /3/): "Moly+" document.write(atob(..))
#   -> vidmoly, "Odnok" haydi.php?v=<base64> -> ok.ru, "DBX Pro" (king.php) is open to Turkish visitors only
import re
import time

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import b64Decode, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.dizibox_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.dizibox_domain)]


def gettytul():
    return "https://www.dizibox.live/"


ITEMS_PER_PAGE = 100
# "Lupin 4.Sezon 1.Bölüm", "Ted Lasso 4.Sezon 10.Bölüm Sezon Finali"
EPISODE_RE = re.compile(r"^(.*?)\s*(\d+)\.\s*Sezon\s+(\d+)\.\s*B\S*l\S*m\b\s*(.*)$", re.I)
# the series index is reloaded after 6 hours
INDEX_TTL = 6 * 3600
# lower case without the Turkish letters for the search
FOLD_CHARS = (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"), ("Ğ", "g"), ("ğ", "g"), ("Ü", "u"), ("ü", "u"),
              ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c"), ("Â", "a"), ("â", "a"), ("&#039;", "'"))


def _fold(text):
    text = str(text or "")
    for src, dst in FOLD_CHARS:
        text = text.replace(src, dst)
    return text.lower()


class DiziBox(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # the domain the site redirected to and its series index (A-Z / search), kept for the session
    DOMAIN = ""
    SERIES = []
    SERIES_TIME = 0

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "dizibox", "cookie": "dizibox.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.dizibox_domain.value.strip()
        self.MAIN_URL = DiziBox.DOMAIN or (domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul())
        self.MENU = [
            {"category": "list_episodes", "title": _("Latest episodes"), "url": self.MAIN_URL + "tum-bolumler/"},
            {"category": "list_episodes", "title": _("Popular episodes"), "url": self.MAIN_URL + "tum-bolumler/?tip=populer"},
            {"category": "list_series", "title": _("All series"), "url": self.MAIN_URL + "dizi-arsivi/"},
            {"category": "list_series", "title": _("Top rated"), "url": self.MAIN_URL + "dizi-arsivi/?orderby=imdb"},
            {"category": "list_series", "title": _("Most commented"), "url": self.MAIN_URL + "dizi-arsivi/?orderby=yorum"},
            {"category": "list_series", "title": "Efsane Diziler", "url": self.MAIN_URL + "efsane-diziler/"},
            {"category": "list_series", "title": "IMDb 7+", "url": self.MAIN_URL + "dizi-arsivi/?imdb=7"},
            {"category": "list_filter", "title": _("Genres"), "url": self.MAIN_URL + "dizi-arsivi/", "filter": "tur"},
            {"category": "list_filter", "title": _("Countries"), "url": self.MAIN_URL + "dizi-arsivi/", "filter": "ulke"},
            {"category": "list_az", "title": _("A-Z"), "url": self.MAIN_URL},
        ]
        for item in self.MENU:
            item.update({"name": "category", "good_for_fav": True})
        self.MENU += self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("dizibox")
        self.wfInitFolderCache()

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added - the site hops domains
        url = self.getFullUrl(url)
        if re.match(r"^https?://[^/]*dizibox\.[^/]+/", url):
            url = re.sub(r"^https?://[^/]+/", self.MAIN_URL, url)
        return url

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        url = self._siteUrl(baseUrl)
        sts, data = self.cm.getPageCFProtection(url, addParams, post_data)
        if sts and url.startswith(self.MAIN_URL):
            # dizibox.com -> dizibox.live: the next requests go to the domain the site redirected to
            finalUrl = str(getattr(data, "meta", {}).get("url", "") or self.cm.meta.get("url", "") or "")
            m = re.match(r"^(https?://[^/]*dizibox\.[^/]+/)", finalUrl)
            if m and m.group(1) != self.MAIN_URL:
                printDBG("DiziBox: domain %s -> %s" % (self.MAIN_URL, m.group(1)))
                self.MAIN_URL = DiziBox.DOMAIN = m.group(1)
        return sts, data

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", str(url or "").strip()).rstrip("/") + "/"

    def _pageUrl(self, url, page):
        # WordPress paging: <path>page/<n>/?<query>
        base, sep, query = self._siteUrl(url).partition("?")
        base = re.sub(r"page/\d+/?$", "", base.rstrip("/") + "/")
        if page > 1:
            base = "%spage/%d/" % (base, page)
        return base + ("?" + query if query else "")

    def _lastPage(self, data, page):
        # "<span class="pages">1 / 42</span>"
        last = self.cm.ph.getSearchGroups(data, r'class="pages">\s*\d+\s*/\s*(\d+)')[0]
        return max(int(last), page) if last else page

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            category = cItem.get("category", "")
            if category == "episode":
                return "video:%s" % self._path(url)
            if category == "dz_series":
                return "series:%s" % self._path(url)
            if category == "dz_season":
                return "season:%s" % self._path(url)
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _episodeTitle(self, sTitle, season, episode, raw=""):
        if IsMediaNamingNormalized() and season and episode:
            return "%s - %s" % (sTitle, formatSxxExx(season, episode))
        return " - ".join(x for x in (sTitle, raw or ("%s.Sezon %s.Bölüm" % (season, episode) if season and episode else "")) if x)

    def _addEpisode(self, cItem, url, sTitle, season, episode, raw="", icon="", desc="", extra=None):
        params = stripPagerKeys(dict(cItem), ("base_url",))
        params.update({"good_for_fav": True, "category": "episode", "url": self._siteUrl(url), "title": self._episodeTitle(sTitle, season, episode, raw),
                       "s_title": sTitle, "season": season, "ep_num": episode, "icon": icon or cItem.get("icon", ""), "desc": desc,
                       "meta_type": "tv", "meta_title": cItem.get("meta_title", sTitle)})
        params.update(extra or {})
        self.addVideo(params)

    def listEpisodeCards(self, cItem):
        # "Tüm Bölümler" / "Popüler Bölümler": 30 episode cards a page
        printDBG("DiziBox.listEpisodeCards |%s|" % cItem)
        page = self._page(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = 0
        for card in data.split('<article class="article-episode-card')[1:]:
            url, label = self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)" class="episode-card-title[^"]*" title="([^"]+)"', 2)
            if not url:
                continue
            label = self.cleanHtmlStr(label)
            icon = self.cm.ph.getSearchGroups(card, r"data-src='([^']+)'")[0]
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="publish-date[^"]*">([^<]+)<')[0])
            m = EPISODE_RE.match(label)
            if m:
                sTitle, season, episode, extra = m.group(1).strip(), m.group(2), m.group(3), m.group(4).strip()
                raw = "%s.Sezon %s.Bölüm%s" % (season, episode, " " + extra if extra else "")
            else:
                sTitle, season, episode = label, "", ""
                raw = ""
            desc = " | ".join(x for x in (label, date) if x)
            self._addEpisode(dict(cItem, meta_title=sTitle), url, sTitle, season, episode, raw, icon, desc)
            count += 1
        lastPage = self._lastPage(data, page) if count else 0
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        addPagingItems(self, nextItem, page, bool(count) and page < lastPage, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def _addSeries(self, url, title, icon="", year="", rating="", desc=""):
        title = self.cleanHtmlStr(title)
        if not url or not title:
            return False
        descLine = " | ".join(x for x in (year, "IMDb: %s" % rating if rating else "") if x)
        if descLine:
            desc = "%s[/br]%s" % (descLine, desc) if desc else descLine
        self.addDir({"name": "category", "good_for_fav": True, "category": "dz_series", "title": title, "s_title": title, "url": self._siteUrl(url),
                     "icon": icon, "desc": desc, "meta_type": "tv", "meta_title": title, "meta_year": year})
        return True

    def listSeries(self, cItem):
        # series archive (detailed rows) and "Efsane Diziler" (poster grid)
        printDBG("DiziBox.listSeries |%s|" % cItem)
        page = self._page(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = 0
        for card in re.split(r'<article class="(?=detailed-article|article-series-poster)', data)[1:]:
            card = card.split("</article>")[0]
            url = self.cm.ph.getSearchGroups(card, r'href="([^"]+/diziler/[^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(card, r'<h3[^>]*>\s*<a[^>]*>([^<]+)<')[0] or self.cm.ph.getSearchGroups(card, r'class="poster-title[^"]*" title="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(card, r"data-src='([^']+)'")[0] or self.cm.ph.getSearchGroups(card, r'<img src="([^"]+)"')[0]
            rating = self.cm.ph.getSearchGroups(card, r'icon-star"></i>\s*([\d.]+)')[0]
            year = self.cm.ph.getSearchGroups(card, r'icon-calendar-check-o"></i>\s*(\d{4})')[0] or self.cm.ph.getSearchGroups(card, r'icon-globe"></i>\s*(?:&nbsp;)?\s*(\d{4})')[0]
            fields = [self.cleanHtmlStr(x).strip(" |") for x in re.findall(r'(?s)<span class="custom-field">(.*?)</span>', card)]
            summary = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="post-summary">(.*?)</div>')[0])
            desc = "[/br]".join(x for x in (" | ".join(x for x in fields if x), summary) if x)
            if self._addSeries(url, title, icon, year, rating, desc):
                count += 1
        lastPage = self._lastPage(data, page) if count else 0
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        addPagingItems(self, nextItem, page, bool(count) and page < lastPage, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listFilter(self, cItem):
        # the genre / country check boxes of the archive's filter form
        printDBG("DiziBox.listFilter |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        name = cItem["filter"]
        base = self._siteUrl(cItem["url"]).split("?")[0]
        seen = set()
        for value, title in re.findall(r'name="%s\[\]" value="([^"]+)"\s*/?>\s*<label[^>]*>([^<]+)<' % re.escape(name), data):
            if value in seen:
                continue
            seen.add(value)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_series", "title": self.cleanHtmlStr(title),
                         "url": "%s?%s%%5B0%%5D=%s" % (base, name, urllib_quote_plus(value))})

    def _seriesIndex(self):
        # every page carries the whole series list A-Z in its header menu: [(letter, title, url)]
        if not DiziBox.SERIES or time.time() - DiziBox.SERIES_TIME > INDEX_TTL:
            sts, data = self.getPage(self.MAIN_URL + "efsane-diziler/")
            if not sts:
                return DiziBox.SERIES
            result = []
            for letter, block in re.findall(r"(?s)<ul class='alphabetical-category-list[^']*' data-index='#([^']+)'>(.*?)</ul>", data):
                letter = letter if len(letter) == 1 else "#"
                for url, title in re.findall(r'<a title="[^"]*" href="([^"]+)"><i class="icon icon-angle-right"></i>([^<]+)</a>', block):
                    title = self.cleanHtmlStr(title)
                    if title:
                        result.append((letter, title, self._path(url)))
            if result:
                DiziBox.SERIES = result
                DiziBox.SERIES_TIME = time.time()
        return DiziBox.SERIES

    def listAZ(self, cItem):
        printDBG("DiziBox.listAZ")
        letters = []
        counts = {}
        for letter, _title, _url in self._seriesIndex():
            if letter not in counts:
                letters.append(letter)
                counts[letter] = 0
            counts[letter] += 1
        for letter in letters:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_letter", "title": letter, "letter": letter, "url": self.MAIN_URL + "#" + letter,
                         "desc": "%s: %d" % (_("Series"), counts[letter])})

    def _listIndex(self, cItem, rows):
        # local paging over the series index rows
        page = self._page(cItem)
        lastPage = (len(rows) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        for _letter, title, path in rows[(page - 1) * ITEMS_PER_PAGE:page * ITEMS_PER_PAGE]:
            self._addSeries(self.MAIN_URL + path.lstrip("/"), title)
        if lastPage > 1:
            # the page lives in cItem["page"] - the template keeps the url unchanged
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, cItem.get("url", "").replace("{", "{{").replace("}", "}}"))

    def listLetter(self, cItem):
        printDBG("DiziBox.listLetter |%s|" % cItem)
        self._listIndex(cItem, [x for x in self._seriesIndex() if x[0] == cItem.get("letter")])

    def listSearchResult(self, cItem, searchPattern, searchType):
        # the site's own search (?s=) does not answer - the series index of the header menu is searched instead
        printDBG("DiziBox.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        words = _fold(searchPattern.strip()).split()
        if not words:
            return
        for _letter, title, path in self._seriesIndex():
            folded = _fold(title)
            if all(w in folded for w in words):
                self._addSeries(self.MAIN_URL + path.lstrip("/"), title)

    def _seriesInfo(self, data):
        # story, IMDb rating, year, countries and genres of a series page
        info = {}
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="tv-story">(.*?)</div>')[0])
        rating = self.cm.ph.getSearchGroups(data, r"label-imdb[^>]*>\s*imdb:\s*<b>([\d.]+)<")[0]
        if rating:
            info["rating"] = "%s/10" % rating
        year = self.cm.ph.getSearchGroups(data, r'href="[^"]*/yil/(\d{4})/"')[0]
        if year:
            info["year"] = year
        terms = self.cm.ph.getSearchGroups(data, r'(?s)<div class="terms[^"]*">(.*?)</div>')[0]
        countries = [self.cleanHtmlStr(x) for x in re.findall(r'href="[^"]*/ulke/[^"]*"[^>]*>([^<]+)<', terms)]
        if countries:
            info["country"] = ", ".join(countries)
        genres = [self.cleanHtmlStr(x) for x in re.findall(r'href="[^"]*/tur/[^"]*"[^>]*>([^<]+)<', terms)]
        if genres:
            info["genres"] = ", ".join(genres)
        return story, info

    def listSeasons(self, cItem):
        printDBG("DiziBox.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        sTitle = cItem.get("s_title") or cItem["title"]
        icon = cItem.get("icon") or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        year = cItem.get("meta_year") or self._seriesInfo(data)[1].get("year", "")
        block = self.cm.ph.getSearchGroups(data, r'(?s)<div id="seasons-list"[^>]*>(.*?)</div>')[0]
        seasons = re.findall(r"<a href='([^']+)'[^>]*>\s*(\d+)\.\s*Sezon\s*</a>", block)
        fields = {"s_title": sTitle, "s_url": self._siteUrl(cItem["url"]), "icon": icon, "meta_type": "tv", "meta_title": cItem.get("meta_title", sTitle), "meta_year": year}
        if len(seasons) <= 1:
            # one season (or none listed): its episodes are on the series page
            self.listEpisodes(dict(cItem, category="dz_season", **fields), data)
            return
        for url, num in seasons:
            title = "%s - %s" % (sTitle, formatSxxExx(num) if IsMediaNamingNormalized() else _("Season %s") % num)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "dz_season", "title": title, "url": self._siteUrl(url), "season": num})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("DiziBox.listEpisodes |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        sTitle = cItem.get("s_title") or cItem["title"]
        episodes = re.findall(r'<a href="([^"]+)" class="season-episode[^"]*">([^<]+)</a>(?:\s*<a[^>]*>\s*<small[^>]*>\s*<i[^>]*></i>([^<]*)<)?', data)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        page = self._page(cItem)
        lastPage = (len(episodes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        for url, label, date in episodes[(page - 1) * ITEMS_PER_PAGE:page * ITEMS_PER_PAGE]:
            label = self.cleanHtmlStr(label)
            m = EPISODE_RE.match(label)
            if m:
                season, episode = m.group(2), m.group(3)
            else:
                season, episode = self.cm.ph.getSearchGroups(url, r"-(\d+)-sezon-(\d+)-bolum", 2)
                season = season or cItem.get("season", "")
            finale = " (Sezon Finali)" if "sezon-finali" in url else ""
            self._addEpisode(cItem, url, sTitle, season, episode, label + finale, desc=" | ".join(x for x in (label + finale, self.cleanHtmlStr(date)) if x))
        if lastPage > 1:
            addPagingItems(self, dict(cItem, category="dz_season"), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _decodeWrites(self, data):
        # document.write(atob(unescape("%50%43..."))) blocks of a player page, decoded
        texts = []
        for enc in re.findall(r'atob\(\s*unescape\(\s*["\']([^"\']+)["\']', data):
            try:
                texts.append(b64Decode(urllib_unquote(enc)))
            except Exception:
                printExc()
        return "\n".join(texts) or data

    def _embedUrl(self, playerUrl, referer):
        # the hoster url behind one dizibox player iframe, "" when there is none (or it is geo-blocked)
        playerUrl = self.getFullUrl(playerUrl.replace("&amp;", "&"))
        if "haydi.php" in playerUrl:
            # haydi.php?v=<base64 of the ok.ru url>
            value = self.cm.ph.getSearchGroups(playerUrl, r"[?&]v=([^&]+)")[0]
            try:
                url = b64Decode(urllib_unquote(value)).strip()
            except Exception:
                url = ""
            return url if self.cm.isValidUrl(url) else ""
        if not re.match(r"^https?://[^/]*dizibox\.[^/]+/player/", playerUrl):
            return playerUrl
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer)
        sts, data = self.getPage(playerUrl, params)
        if not sts:
            return ""
        if "ziyaretçilerine açıktır" in data:
            printDBG("DiziBox: %s - open to visitors from Turkey only" % playerUrl)
            return ""
        data = self._decodeWrites(data)
        for url in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', data):
            url = self.getFullUrl(url.replace("&amp;", "&"))
            if self.cm.isValidUrl(url):
                return url
        return ""

    @staticmethod
    def _hosterLabel(host):
        # "vidmoly.biz" -> "vidmoly", "ok.ru" stays
        name = host.split(".")[0] if "." in host else host
        return host if len(name) < 3 else name

    def getLinksForVideo(self, cItem):
        printDBG("DiziBox.getLinksForVideo [%s]" % cItem)
        pageUrl = self._siteUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        current = self.cm.ph.getSearchGroups(data, r"<!--baslik:([^>]*?)-->")[0].strip()
        # the player selector: the current page as href, the other sub pages (/2/, /3/) as value
        block = self.cm.ph.getSearchGroups(data, r'(?s)<select class="woca-linkpages-dd[^>]*>(.*?)</select>')[0]
        players = []
        for url, name in re.findall(r"<option[^>]*?(?:value|href)='([^']+)'[^>]*>([^<]+)<", block):
            players.append((self.cleanHtmlStr(name), self._siteUrl(url)))
        if not players:
            players = [(current, pageUrl)]
        urltab = []
        seen = set()
        for name, url in players:
            if self._path(url) == self._path(pageUrl):
                page = data
            else:
                sts, page = self.getPage(url)
                if not sts:
                    continue
                name = self.cm.ph.getSearchGroups(page, r"<!--baslik:([^>]*?)-->")[0].strip() or name
            area = page.split('id="video-area"', 1)[-1]
            iframe = self.cm.ph.getSearchGroups(area, r'<iframe[^>]+src=["\']([^"\']+)["\']')[0]
            embed = self._embedUrl(iframe, url) if iframe else ""
            if not embed or embed in seen or self.up.checkHostSupport(embed) != 1:
                printDBG("DiziBox: player %s skipped [%s]" % (name, embed or iframe))
                continue
            seen.add(embed)
            label = "%s (%s)" % (name, self._hosterLabel(self.up.getHostName(embed, True))) if name else self.up.getHostName(embed, True)
            urltab.append({"name": label, "url": strwithmeta(embed, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        metaQuery = sidecarMetaQuery("tv", cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", ""), skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("DiziBox.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("DiziBox.getArticleContent [%s]" % cItem)
        category = cItem.get("category", "")
        seriesUrl = cItem.get("s_url", "") if category != "dz_series" else cItem.get("url", "")
        icon = cItem.get("icon", "")
        if not seriesUrl and category == "episode":
            # an episode of the latest list: its page links the series
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                seriesUrl = self.cm.ph.getSearchGroups(data, r'<a href="([^"]+/diziler/[^"]+)" class="link-unstyled"')[0] or \
                    self.cm.ph.getSearchGroups(data.split("itemprop=\"episode\"", 1)[-1], r'href="([^"]+/diziler/[^"]+)"')[0]
        story = ""
        info = {}
        if seriesUrl:
            sts, data = self.getPage(seriesUrl)
            if sts:
                story, info = self._seriesInfo(data)
                icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        title = cItem.get("meta_title", "") or cItem.get("s_title", "")
        year = cItem.get("meta_year", "") or info.get("year", "")
        meta = {}
        try:
            if title:
                meta = getMeta("tv", title, year) or {}
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        if "rating" in siteInfo:
            info["rating"] = siteInfo["rating"]  # the IMDb rating the site shows
        plot = meta.get("plot", "")
        text = story or cItem.get("desc", "")
        if plot and plot != text:
            text = "%s[/br][/br]%s" % (text, plot) if text else plot
        if category == "episode" and cItem.get("desc"):
            text = "%s[/br][/br]%s" % (cItem["desc"], text) if text else cItem["desc"]
        icon = icon or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_episodes":
            self.listEpisodeCards(self.currItem)
        elif category == "list_series":
            self.listSeries(self.currItem)
        elif category == "list_filter":
            self.listFilter(self.currItem)
        elif category == "list_az":
            self.listAZ(self.currItem)
        elif category == "list_letter":
            self.listLetter(self.currItem)
        elif category == "dz_series":
            self.listSeasons(self.currItem)
        elif category == "dz_season":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, DiziBox(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dizibox")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("episode", "dz_series", "dz_season")
