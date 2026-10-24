# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
#   - Burning Series (burningseries.ac, successor of bs.to): German series and anime, dub / sub
#   - latest episodes, latest and popular series, genres, A-Z and search over the site's series catalogue
#   - series -> seasons -> episodes, every language of an episode in one row; link names: hoster + language
#   - links: reCAPTCHA (invisible) per link - MyE2i opens the hoster page in the browser (NAV job, the user clicks
#     the player there) and sends back the hoster link; 9kw.eu / 2captcha.com tokens as an option - then urlparser
#   - watched flag, downloaded flag, favourites, name normalisation ("Show - SxxExx"), sidecar,
#     INFO via moviemeta + the site's fields
###################################################
import re
import time

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import b64Decode, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

###################################################
# Config options for HOST
# the 9kw.eu / 2captcha.com keys are the global ones of components/iptvconfig.py (api_key_9kweu / api_key_2captcha)
###################################################
config.plugins.iptvplayer.burningseries_alt_domain = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.burningseries_bypassrecaptcha = ConfigSelection(default="mye2i", choices=[("mye2i", _("MyE2i (solve on your phone/PC)")),
                                                                                                    ("9kw.eu", "https://9kw.eu/"),
                                                                                                    ("2captcha.com", "https://2captcha.com/")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Captcha solving service"), config.plugins.iptvplayer.burningseries_bypassrecaptcha))
    if config.plugins.iptvplayer.burningseries_bypassrecaptcha.value == "9kw.eu":
        optionList.append(getConfigListEntry("    " + _("API Key"), config.plugins.iptvplayer.api_key_9kweu))
    elif config.plugins.iptvplayer.burningseries_bypassrecaptcha.value == "2captcha.com":
        optionList.append(getConfigListEntry("    " + _("API Key"), config.plugins.iptvplayer.api_key_2captcha))
    optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.burningseries_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://burningseries.ac/"


# rows keep their urls on this address (watched / downloaded / favourite keys survive a domain change);
# getPage() sends them to the address in use
CANON_URL = gettytul()
SITE_PATH_RE = re.compile(r"^https?://(?:[^/]*burningseries\.[a-z]+|bs\.to|bs\.cine\.to)/(.*)$")
# serie/<show>[/<season>[/<n>-<slug>]][/<language>][/<hoster>]
EPISODE_PATH_RE = re.compile(r"^serie/([^/]+)/(\d+)/(\d+)(?:-([^/]*))?(?:/([a-z]{2,3}))?(?:/([^/]+))?$")
# MyE2i NAV job for a hoster page: the site binds the reCAPTCHA ticket to the browser that solved it (a token
# solved in the browser and posted from here is refused with 400), so the browser does the whole click; the page then
# puts the hoster link into the player box (<a href> or <iframe>). The pattern takes only "https://<host>/<id>"
# style links - the page also has links to bs.to / cine.to (cookie banner, board)
NAV_JOB = {"selector": "section.serie .hoster-player a, section.serie .hoster-player iframe", "attr": "href",
           "pattern": r"^https?://(?![^/]*(?:burningseries|cine\.to|bs\.to))[^/?#]+/(?:e/|d/|v/|embed-)?[A-Za-z0-9_-]{6,}(?:\.html)?(?:/[^/?#]*)?$"}
SERIES_LINK_RE = re.compile(r'<li><a href="(serie/[^"]+)"(?: title="([^"]*)")?>(.*?)</a></li>')
GROUP_RE = re.compile(r'(?s)<div class="genre">\s*<span><strong>(.*?)</strong></span>(.*?)</ul>')
OPTION_RE = re.compile(r'<option value="([a-z]+)"(\s+selected)?>([^<]+)</option>')
PAGE_SIZE = 100
VIDEO_CATEGORIES = ("bs_video",)
FOLDER_CATEGORIES = ("bs_series", "bs_season")


def _path(url):
    # "serie/..." part of a site url (any address), '' for anything else
    url = str(url or "")
    match = SITE_PATH_RE.match(url)
    return match.group(1).split("#")[0].rstrip("/") if match else ""


def _episodePath(match):
    # "serie/<show>/<season>/<n>-<slug>" of an EPISODE_PATH_RE match, without language and hoster
    show, season, number, slug = match.groups()[:4]
    return "serie/%s/%s/%s%s" % (show, season, number, "" if slug is None else "-" + slug)


def _showTitle(title):
    # "Deutscher Titel | Original Title" -> ("Deutscher Titel", "Original Title")
    parts = [x.strip() for x in title.split("|") if x.strip()]
    return (parts[0] if parts else title), (parts[1] if len(parts) > 1 else "")


class BurningSeries(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    # link id of a hoster page -> hoster url (the captcha is asked once per link and session)
    LINKS_CACHE = {}
    # the series catalogue (/serie-genre by genre, /serie-alphabet by letter): 1.3 MB each, loaded once per session;
    # not /andere-serien - that one follows the "seriesorder" cookie the last of the two pages set
    CATALOGUE = {}

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "s_langs",
                  "group", "kind", "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "burningseries", "cookie": "burningseries.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["User-Agent"] = self.USER_AGENT
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = CANON_URL + "opengraph.jpg"
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("burningseries")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        domain = config.plugins.iptvplayer.burningseries_alt_domain.value.strip()
        if domain and not domain.startswith("http"):
            domain = "https://" + domain
        if not self.setMainUrl(domain):
            self.MAIN_URL = gettytul()
        printDBG("BurningSeries.selectDomain [%s]" % self.MAIN_URL)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if self.MAIN_URL is None:
            self.selectDomain()
        if addParams is None:
            addParams = dict(self.defaultParams)
        path = SITE_PATH_RE.match(baseUrl or "")
        if path:
            baseUrl = self.getMainUrl() + path.group(1)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#")[0], addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("bs_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            path = _path(cItem.get("url", ""))
            if not path:
                return ""
            if category in VIDEO_CATEGORIES:
                # the episode number, not its title slug
                match = EPISODE_PATH_RE.match(path)
                return "video:serie/%s/%s/%s" % (match.group(1), match.group(2), match.group(3)) if match else ""
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    def _seriesUrl(self, slug):
        return CANON_URL + "serie/" + slug

    def _episodeTitle(self, show, season, episode, label=""):
        if IsMediaNamingNormalized():
            return "%s - %s" % (_showTitle(show)[0], formatSxxExx(season, episode))
        title = "%s - S%02d E%02d" % (show, season, episode)
        return "%s - %s" % (title, label) if label else title

    def _seasonTitle(self, show, season, label=""):
        if IsMediaNamingNormalized():
            return "%s - %s" % (_showTitle(show)[0], formatSxxExx(season))
        if season == 0:
            return "%s - %s" % (show, label or _("Specials"))
        return "%s - %s %d" % (show, _("Season"), season)

    def _languages(self, data):
        # [(code, label, selected)] of the page's language selector
        return [(code, self.cleanHtmlStr(label), bool(sel)) for code, sel, label in OPTION_RE.findall(self.cm.ph.getDataBeetwenMarkers(data, 'class="series-language"', "</select>")[1])]

    def _siteInfo(self, data):
        # (title, story, cover, {INFO fields}, year) from the show part of a series / season / episode page
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div id="sp_left">', '<div id="sp_right">')[1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, "<h2>", "</h2>", False)[1].split("<small>")[0])
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, "<p>", "</p>", False)[1])
        cover = self.cm.ph.getSearchGroups(data, r'<div id="sp_right">\s*<img src="([^"]+)"')[0]
        info, year = {}, ""
        names = {"Genres": "genres", "Hauptdarsteller": "actors", "Produzenten": "production", "Regisseure": "directors", "Autoren": "writers"}
        for item in self.cm.ph.getAllItemsBeetwenMarkers(self.cm.ph.getDataBeetwenMarkers(block, '<div class="infos">', '<div id="sp_right">')[1], "<div>", "</div>"):
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1])
            body = self.cm.ph.getDataBeetwenMarkers(item, "<p>", "</p>", False)[1]
            if label == "Produktionsjahre":
                year = self.cm.ph.getSearchGroups(body, r"((?:19|20)\d{2})")[0]
                continue
            values = [self.cleanHtmlStr(x) for x in re.findall(r"(?s)<span(?! class=\"no-entry\")[^>]*>(.*?)</span>", body)]
            values = [x for x in values if x]
            if label in names and values:
                info[names[label]] = ", ".join(values)
        if year:
            info["year"] = year
        return title, story, self.getFullIconUrl(cover) if cover else "", info, year

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"category": "bs_latest_episodes", "title": _("Latest episodes")},
                {"category": "bs_home_series", "title": _("Recently added"), "section": "newest_series"},
                {"category": "bs_home_series", "title": _("Popular series"), "section": "other-series-nav"},
                {"category": "bs_groups", "title": _("Genres"), "kind": "genre"},
                {"category": "bs_groups", "title": _("A-Z"), "kind": "alpha"}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def _catalogue(self, kind):
        # [(group, [(title, path)])] of the genre or letter page
        key = (self.getMainUrl(), kind)
        if BurningSeries.CATALOGUE.get(key):
            return BurningSeries.CATALOGUE[key]
        sts, data = self.getPage(self.getFullUrl("serie-genre" if kind == "genre" else "serie-alphabet"))
        if not sts:
            return []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="seriesContainer">', "<script")[1]
        groups = []
        for name, block in GROUP_RE.findall(data):
            items = []
            for path, title, text in SERIES_LINK_RE.findall(block):
                title = self.cleanHtmlStr(title or text)
                if title:
                    items.append((title, path))
            if items:
                groups.append((self.cleanHtmlStr(name), items))
        if groups:
            BurningSeries.CATALOGUE[key] = groups
        return groups

    def listGroups(self, cItem):
        kind = cItem.get("kind", "genre")
        for name, items in self._catalogue(kind):
            self.addDir({"name": "category", "category": "bs_list", "good_for_fav": True, "title": name, "kind": kind, "group": name,
                         "url": CANON_URL + ("serie-genre#%s" if kind == "genre" else "serie-alphabet#%s") % name,
                         "desc": "%s: %d" % (_("Series"), len(items))})

    def _addSeriesRows(self, cItem, items, pageTpl):
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
        for title, path in items[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
            self._addSeries(title, path)
        addPagingItems(self, cItem, page, page < lastPage, lastPage, pageTpl)

    def _addSeries(self, title, path, desc=""):
        slug = path.split("/")[1] if path.count("/") else ""
        if not slug:
            return
        self.addDir({"name": "category", "category": "bs_series", "good_for_fav": True, "title": title, "url": self._seriesUrl(slug),
                     "s_title": title, "meta_type": "tv", "meta_title": _showTitle(title)[0], "desc": desc})

    def listGroup(self, cItem):
        kind, group = cItem.get("kind", "genre"), cItem.get("group", "")
        for name, items in self._catalogue(kind):
            if name == group:
                base = stripPagerKeys(dict(cItem))
                self._addSeriesRows(cItem, items, base["url"].split("#")[0] + "#" + group + "/{page}")
                return

    def listHomeSeries(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        section = cItem.get("section", "")
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="%s"' % section, "</ul>")[1]
        for path, title, text in SERIES_LINK_RE.findall(block):
            title = self.cleanHtmlStr(title or text)
            if title and path.startswith("serie/"):
                self._addSeries(title, path)

    def listLatestEpisodes(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<section id="newest_episodes">', "</section>")[1]
        rows, order = {}, []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li>", "</li>"):
            path = self.cm.ph.getSearchGroups(item, r'href="(serie/[^"]+)"')[0]
            match = EPISODE_PATH_RE.match(path)
            if not match:
                continue
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="title">(.*?)</a>')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]*)"')[0])
            if show and label.startswith(show + ":"):
                label = label[len(show) + 1:].strip(" |")
            lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<i class="flag[^"]*" title="([^"]+)"')[0])
            key = _episodePath(match)
            if key not in rows:
                rows[key] = {"show": show, "label": label, "slug": match.group(1), "season": int(match.group(2)),
                             "episode": int(match.group(3)), "codes": [], "langs": []}
                order.append(key)
            if match.group(5) and match.group(5) not in rows[key]["codes"]:
                rows[key]["codes"].append(match.group(5))
                rows[key]["langs"].append(lang or match.group(5))
        for key in order:
            row = rows[key]
            self.addVideo({"name": "category", "category": "bs_video", "good_for_fav": True, "url": CANON_URL + key,
                           "title": self._episodeTitle(row["show"], row["season"], row["episode"], row["label"]),
                           "s_title": row["show"], "s_season": row["season"], "s_episode": row["episode"], "s_langs": ",".join(row["codes"]),
                           "meta_type": "tv", "meta_title": _showTitle(row["show"])[0],
                           "desc": " | ".join(x for x in ("S%02d E%02d" % (row["season"], row["episode"]), ", ".join(row["langs"]), row["label"]) if x)})

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = (cItem.get("s_pattern") or searchPattern or "").strip()
        words = pattern.lower().split()
        if not words:
            return
        found = []
        for _group, items in self._catalogue("alpha"):
            for title, path in items:
                low = title.lower()
                if all(word in low for word in words):
                    found.append((title, path))
        listItem = dict(cItem, category="search_next_page", s_pattern=pattern, url=CANON_URL + "serie-alphabet#search")
        self._addSeriesRows(listItem, found, CANON_URL + "serie-alphabet#search/{page}")

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        title, story, cover, info, year = self._siteInfo(data)
        show = cItem.get("s_title") or title or cItem.get("title", "")
        slug = _path(cItem["url"]).split("/")[1]
        langs = self._languages(data)
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="seasons"', "</ul>")[1]
        facts = " | ".join(x for x in (year, info.get("genres", ""), ", ".join(x[1] for x in langs)) if x)
        desc = "[/br]".join(x for x in (facts, story) if x)
        count = 0
        for season, label in re.findall(r'<li class="s(\d+)[^"]*"><a href="serie/[^"]+">([^<]*)</a></li>', block):
            season = int(season)
            label = self.cleanHtmlStr(label)
            self.addDir({"name": "category", "category": "bs_season", "good_for_fav": True, "url": self._seriesUrl(slug) + "/%d" % season,
                         "title": self._seasonTitle(show, season, label), "icon": cover or cItem.get("icon", ""),
                         "s_title": show, "s_season": season, "meta_type": "tv", "meta_title": _showTitle(show)[0],
                         "desc": desc})
            count += 1
        if not count:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def _episodeRows(self, data):
        # [(episode, path, label, [hoster names])] of a season page in one language
        rows = []
        table = self.cm.ph.getDataBeetwenMarkers(data, '<table class="episodes">', "</table>")[1]
        for row in self.cm.ph.getAllItemsBeetwenMarkers(table, "<tr", "</tr>"):
            cells = self.cm.ph.getAllItemsBeetwenMarkers(row, "<td", "</td>")
            if len(cells) < 3:
                continue
            path = self.cm.ph.getSearchGroups(cells[0], r'href="(serie/[^"]+)"')[0]
            match = EPISODE_PATH_RE.match(path)
            if not match:
                continue
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(cells[1], "<strong>", "</strong>", False)[1])
            original = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(cells[1], "<i>", "</i>", False)[1])
            if original and original != label:
                label = "%s (%s)" % (label, original) if label else original
            hosters = [self.cleanHtmlStr(x) for x in re.findall(r'<a href="serie/[^"]+" title="([^"]+)"', cells[2])]
            rows.append((int(match.group(3)), _episodePath(match), label, hosters))
        return rows

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        season = int(cItem.get("s_season", 0) or 0)
        show = cItem.get("s_title") or cItem.get("title", "")
        langs = self._languages(data)
        current = [x[0] for x in langs if x[2]][:1]
        episodes, order = {}, []

        def merge(rows, lang):
            for number, path, label, hosters in rows:
                if number not in episodes:
                    episodes[number] = {"path": path, "label": label, "codes": [], "langs": [], "hosters": []}
                    order.append(number)
                if hosters and lang[0] not in episodes[number]["codes"]:
                    episodes[number]["codes"].append(lang[0])
                    episodes[number]["langs"].append(lang[1])
                    episodes[number]["hosters"].extend(x for x in hosters if x not in episodes[number]["hosters"])

        for lang in langs:
            if lang[0] in current:
                merge(self._episodeRows(data), lang)
                continue
            sts, other = self.getPage(cItem["url"] + "/" + lang[0])
            if sts and [x[0] for x in self._languages(other) if x[2]][:1] == [lang[0]]:
                merge(self._episodeRows(other), lang)
        if not langs:
            merge(self._episodeRows(data), ("", ""))
        cover = self._siteInfo(data)[2] or cItem.get("icon", "")
        count = 0
        for number in sorted(order):
            row = episodes[number]
            if not row["codes"]:
                # "disabled" row: no hoster in any language yet
                continue
            count += 1
            self.addVideo({"name": "category", "category": "bs_video", "good_for_fav": True, "url": CANON_URL + row["path"],
                           "title": self._episodeTitle(show, season, number, row["label"]), "icon": cover,
                           "s_title": show, "s_season": season, "s_episode": number, "s_langs": ",".join(row["codes"]),
                           "meta_type": "tv", "meta_title": _showTitle(show)[0],
                           "desc": " | ".join(x for x in ("S%02d E%02d" % (season, number), ", ".join(row["langs"]), ", ".join(row["hosters"])) if x) +
                           ("[/br]" + row["label"] if row["label"] else "")})
        if not count:
            SetIPTVPlayerLastHostError(_("No stream available"))

    ###################################################
    # links
    ###################################################
    def _hosterTabs(self, data):
        # [(hoster name, path)] of the hoster tabs of an episode page
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="hoster-tabs top">', "</ul>")[1]
        tabs = []
        for path, body in re.findall(r'(?s)<a[^>]+href="(serie/[^"]+)"[^>]*>(.*?)</a>', block):
            name = self.cleanHtmlStr(body) or path.rsplit("/", 1)[-1]
            tabs.append((name, path))
        return tabs

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("BurningSeries.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        langs = self._languages(data)
        current = [x[0] for x in langs if x[2]][:1]
        wanted = [x for x in (cItem.get("s_langs", "") or "").split(",") if x]
        urltab = []
        for code, label, _sel in langs or [("", "", True)]:
            if wanted and code and code not in wanted:
                continue
            page = data
            if code and code not in current:
                sts, page = self.getPage(url + "/" + code)
                if not sts or [x[0] for x in self._languages(page) if x[2]][:1] != [code]:
                    continue
            for name, path in self._hosterTabs(page):
                urltab.append({"name": "%s (%s)" % (name, label) if label else name,
                               "url": strwithmeta(CANON_URL + path, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        title, story, _cover, info, year = self._siteInfo(data)
        main, alt = _showTitle(cItem.get("s_title") or title)
        metaQuery = sidecarMetaQuery("tv", main, year, altTitles=[alt] if alt else ())
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story, metaQuery))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("BurningSeries.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        pageUrl = CANON_URL + _path(videoUrl) if _path(videoUrl) else str(videoUrl)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        lid = self.cm.ph.getSearchGroups(data, r'class="hoster-player" data-lid="(\d+)"')[0]
        if not lid:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        hostUrl = BurningSeries.LINKS_CACHE.get(lid, "")
        if not hostUrl:
            # series.init(season, episode, '<reCAPTCHA site key>'): an empty key = no captcha for this link
            sitekey = self.cm.ph.getSearchGroups(data, r"""series\.init\s*\(\s*\d+\s*,\s*\d+\s*,\s*['"]([^'"]*)['"]""")[0]
            refUrl = self.getMainUrl() + _path(pageUrl)
            service = config.plugins.iptvplayer.burningseries_bypassrecaptcha.value or "mye2i"
            if sitekey and service == "mye2i":
                hostUrl = self._myE2iHosterUrl(refUrl)
            else:
                hostUrl = self._embedLink(lid, sitekey, refUrl, service)
                if hostUrl is None:
                    return []
            if not self.cm.isValidUrl(hostUrl):
                SetIPTVPlayerLastHostError(_("It looks like some kind of protection. Try again later."))
                return []
            BurningSeries.LINKS_CACHE[lid] = hostUrl
        printDBG("BurningSeries.getVideoLinks hoster [%s]" % hostUrl)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(hostUrl, {"Referer": self.getMainUrl()})), sidecar)

    def _embedLink(self, lid, sitekey, refUrl, service):
        # POST ajax/embed.php with a 9kw.eu / 2captcha.com token for the invisible reCAPTCHA v2 (none without a site
        # key): the hoster link, "" when the site refuses it, None when the captcha service gave no token
        token = ""
        if sitekey:
            token, errorMsgTab = self.processCaptcha(sitekey, refUrl, bypassCaptchaService=service, captchaType="INVISIBLE")
            if not token:
                if errorMsgTab:
                    SetIPTVPlayerLastHostError("\n".join(errorMsgTab))
                return None
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=refUrl, Accept="application/json, text/javascript, */*; q=0.01", **{"X-Requested-With": "XMLHttpRequest"})
        sts, ret = self.getPage(self.getFullUrl("ajax/embed.php"), params, {"LID": lid, "ticket": token})
        try:
            ret = json_loads(ret) if sts else {}
        except Exception:
            printExc()
            ret = {}
        hostUrl = ret.get("link", "") if isinstance(ret, dict) and ret.get("success") else ""
        if hostUrl.startswith("//"):
            hostUrl = "https:" + hostUrl
        if not hostUrl:
            printDBG("BurningSeries._embedLink answer [%s]" % ret)
        return hostUrl

    def _myE2iHosterUrl(self, pageUrl):
        # MyE2i NAV job: the hoster page opens in the user's browser, the user clicks the player (the page runs its own
        # invisible reCAPTCHA there) and the hoster link the page then shows comes back
        try:
            from Plugins.Extensions.IPTVPlayer.libs.recaptcha_mye2i import UnCaptchaReCaptcha
            answer = UnCaptchaReCaptcha().processCaptcha(time.time(), pageUrl, captchaType="NAV", captchaData=json_dumps(NAV_JOB),
                                                         hint=_("Open the page and click the video player there"))
            url = (json_loads(b64Decode(answer)) or {}).get("url", "") if answer else ""
        except Exception:
            printExc()
            url = ""
        if self.cm.isValidUrl(url):
            return url
        printDBG("BurningSeries._myE2iHosterUrl no link for [%s]" % pageUrl)
        return ""

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("BurningSeries.getArticleContent [%s]" % cItem.get("url", ""))
        title, story, cover, info = "", "", "", {}
        year = ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            title, story, cover, info, year = self._siteInfo(data)
            langs = ", ".join(x[1] for x in self._languages(data))
            if langs:
                info["language"] = langs
        main, alt = _showTitle(cItem.get("s_title") or title or cItem.get("title", ""))
        meta = {}
        try:
            meta = getMeta("tv", main, year)
            if not meta and alt:
                meta = getMeta("tv", alt, year)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        # the site's German fields stay, moviemeta adds what the page lacks
        info.update(siteInfo)
        if alt:
            info["original_title"] = alt
        plot = meta.get("plot", "")
        text = story or plot or self.cleanHtmlStr(cItem.get("desc", ""))
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        if cItem.get("category") in VIDEO_CATEGORIES:
            text = "%s[/br][/br]%s" % (self.cleanHtmlStr(cItem.get("desc", "").replace("[/br]", " | ")), text)
        icon = cover or meta.get("poster") or cItem.get("icon", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("BurningSeries.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "bs_latest_episodes":
            self.listLatestEpisodes(self.currItem)
        elif category == "bs_home_series":
            self.listHomeSeries(self.currItem)
        elif category == "bs_groups":
            self.listGroups(self.currItem)
        elif category == "bs_list":
            self.listGroup(self.currItem)
        elif category == "bs_series":
            self.listSeasons(self.currItem)
        elif category == "bs_season":
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
        CHostBase.__init__(self, BurningSeries(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("burningseries")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
