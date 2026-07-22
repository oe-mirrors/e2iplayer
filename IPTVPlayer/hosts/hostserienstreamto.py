# -*- coding: utf-8 -*-
# Last Modified: 20.07.2026 - Jump/Next icons added, JumpToPage updated, OMDb/IMDb refactored,
# IMDb rating, Year and Genre added for descriptions/sidecar files, HLS sidecar files (.txt + .jpg) extended,
# episode titles normalized to SxxExx format and language suffix separated by " - ",
# IMDb/OMDb enabled for listNewEpisodes via imdb_lookup_url fallback in article/sidecar flow,
# Optional MKV output meta added via host config,
# s.to broken, serienstream.cx added as alternative,
# URL meta helper for sidecar and MKV postprocess handling - Kamikaze24
import re
import json

from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Components.config import ConfigSelection, config, getConfigListEntry, ConfigYesNo, ConfigText
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecar, sidecarFromUrlMeta, decorateUrl, decorateResolvedLinkItems


config.plugins.iptvplayer.serienstreamto_hosts = ConfigSelection(default="http://186.2.175.5/", choices=[("http://186.2.175.5/", "186.2.175.5"), ("https://serienstream.to/", "serienstream.to"), ("https://serienstream.cx/", "serienstream.cx")])  # NOSONAR
config.plugins.iptvplayer.serienstreamto_uselogin = ConfigYesNo(default=False)
config.plugins.iptvplayer.serienstreamto_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.serienstreamto_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.serienstreamto_omdb_apikey = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.serienstreamto_sidecar = ConfigYesNo(default=True)
config.plugins.iptvplayer.serienstreamto_mkv = ConfigYesNo(default=True)


def GetConfigList():
    return [getConfigListEntry(_("Use login") + ":", config.plugins.iptvplayer.serienstreamto_uselogin),
            getConfigListEntry(_("e-mail") + ":", config.plugins.iptvplayer.serienstreamto_login),
            getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.serienstreamto_password),
            getConfigListEntry(_("OMDb API Key") + ":", config.plugins.iptvplayer.serienstreamto_omdb_apikey),
            getConfigListEntry(_("Create sidecar files (.txt/.jpg)") + ":", config.plugins.iptvplayer.serienstreamto_sidecar),
            getConfigListEntry(_("Create MKV") + ":", config.plugins.iptvplayer.serienstreamto_mkv),
            getConfigListEntry(_("host") + ":", config.plugins.iptvplayer.serienstreamto_hosts)]


def gettytul():
    return "https://serienstream.to/"


def language(item):
    lang_map = {"german": "(DE)", "english": "(EN)", "english-german": "(EN/DE-UT)"}
    flags = re.findall(r'<use href="#icon-flag-([^"]+)', item)
    return "" if not flags else " ".join(lang_map.get(f, f) for f in flags)


class SerienStreamTo(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "SerienStreamTo", "cookie": "SerienStreamTo.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = config.plugins.iptvplayer.serienstreamto_hosts.value
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/serienstream.to.png"
        self.imdb_cache = {}
        self.sessionEx = MainSessionWrapper()
        self.MENU = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("suche")},
                     {"category": "list_newepisodes", "title": "Neueste Episoden"},
                     {"category": "list_items", "title": _("Collections"), "url": self.getFullUrl("sammlungen")},
                     {"category": "list_value", "title": _("Genres"), "s": ">Genres</h2>"},
                     {"category": "list_AZ", "title": "A-Z"},
                     {"category": "list_value", "title": _("Country"), "s": ">Länder</h2>"},
                     {"category": "list_value", "title": _("Persons"), "s": ">Personen</h2>"},
                     {"category": "list_items", "title": _("All"), "url": self.getFullUrl("serien")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getJumpItem(self, max_page, page, url, name):
        name = (name or "category").split('-')[0] + "-JUMP"
        if max_page:
            return {"good_for_fav": False, "title": "%s %s/%s" % (_("Jump"), page, max_page),
                    "desc": _("Jump to a selected page, max: {}").format(max_page),
                    "category": "jump_to_page", "type": "category", "url": url, "name": name,
                    "icon": "", "max_page": max_page, "current_page": page, "image_type": "JUMP"}
        else:
            return {"good_for_fav": False, "title": _("Jump"),
                    "desc": _("Jump to a selected page"),
                    "category": "jump_to_page", "type": "category", "url": url, "name": name,
                    "icon": "", "max_page": max_page, "current_page": page, "image_type": "JUMP"}

    def jumpToPage(self, cItem):
        printDBG("SerienStreamTo.jumpToPage begin")
        root_url = cItem["url"]
        root_url = re.sub(r"/\d+/?$", "/", root_url)
        root_url = re.sub(r"\?page=\d+|&page=\d+", "", root_url).rstrip("?&")
        printDBG("ROOT JUMP: [%s]" % root_url)
        max_page = int(cItem.get("max_page", 99))
        if max_page < 1:
            max_page = 99
        current_page = int(cItem.get("current_page", 1))
        if current_page > max_page:
            current_page = max_page
        title = _("Jump to a selected page, max: {}").format(max_page) if max_page else _("Jump to a selected page")
        ret = self.sessionEx.waitForFinishOpen(GetVirtualKeyboard(), title=title, text=str(current_page))
        if isinstance(ret, tuple) and len(ret):
            ret = ret[0]
        if not ret or not ret.strip():
            page = current_page
        elif ret.isdigit():
            page = int(ret)
        else:
            page = current_page
        if page < 1:
            page = 1
        if page > max_page:
            page = max_page
        sep = "?" if "?" not in root_url else "&"
        jump_url = root_url + sep + "page=%s" % page
        printDBG("JUMP von %d → %d: [%s]" % (current_page, page, jump_url))
        jump_cItem = dict(cItem)
        jump_cItem.pop("image_type", None)
        jump_cItem.pop("imageType", None)
        jump_cItem.update({"url": jump_url, "category": "list_items", "page": page, "max_page": max_page, "current_page": page})
        self.currItem["url"] = jump_cItem["url"]
        self.currItem["page"] = jump_cItem["page"]
        self.currItem["max_page"] = jump_cItem["max_page"]
        self.currItem["current_page"] = jump_cItem["current_page"]
        self.currItem.pop("image_type", None)
        self.currItem.pop("imageType", None)
        self.listItems(jump_cItem)

    def getMaxPageFromPagination(self, html):
        pages = []
        for m in re.finditer(r'href="[^"]*page=(\d+)[^"]*"', html, re.IGNORECASE):
            try:
                pages.append(int(m.group(1)))
            except Exception:
                pass
        return max(pages) if pages else None

    def extractImdbId(self, data):
        if not data:
            return ""
        imdb_match = re.search(r"\b(tt\d{7,10})\b", data, re.IGNORECASE)
        return imdb_match.group(1) if imdb_match else ""

    def getOMDbData(self, imdb_id):
        if not imdb_id:
            return {}
        if not re.match(r"^tt\d{7,10}$", imdb_id):
            return {}
        cache_key = "omdb_%s" % imdb_id
        if cache_key in self.imdb_cache:
            return self.imdb_cache[cache_key]
        api_key = config.plugins.iptvplayer.serienstreamto_omdb_apikey.value.strip()
        if not api_key:
            return {}
        api_url = "http://www.omdbapi.com/?i=%s&apikey=%s" % (imdb_id, api_key)
        printDBG("||OMDb: %s" % api_url)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        params["timeout"] = 8
        try:
            sts, data = self.cm.getPage(api_url, params)
            if not sts or not data:
                return {}
            j = json.loads(data)
            if j.get("Response") != "True":
                return {}
            self.imdb_cache[cache_key] = j
            return j
        except Exception:
            printExc("||OMDb EXCEPTION")
            return {}

    def getIMDBRating(self, imdb_id):
        omdb = self.getOMDbData(imdb_id)
        rating = omdb.get("imdbRating", "") if omdb else ""
        if rating in ("", "N/A", None):
            return "-"
        return str(rating)

    def listItems(self, cItem):
        printDBG("SerienStreamTo.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return

        max_page = self.getMaxPageFromPagination(htm)
        page = cItem.get("page", 1)

        baseItem = dict(cItem)
        baseItem.pop("image_type", None)
        baseItem.pop("imageType", None)
        if (baseItem.get("name", "") or "").endswith("-JUMP"):
            baseItem["name"] = "category"
        baseItem.pop("desc", None)

        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-6', "</div>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="series-item"', "</li>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="collection-item-cover', "</small>")
        if data is None:
            data = []

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title1 = self.cm.ph.getSearchGroups(item, 'data-search="([^"]+)"')[0]
            title2 = self.cm.ph.getSearchGroups(item, 'title="([^"]+)"')[0]
            title = title1 or title2
            params = dict(baseItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": ""})
            if "sammlung" in url:
                params.update({"category": "list_items"})
            self.addDir(params)

        if max_page and max_page > 1:
            self.addDir({"title": "************************", "category": "empty"})
            self.addDir(self.getJumpItem(max_page, page, cItem["url"], baseItem.get("name", "category")))
            nextPage = self.cm.ph.getSearchGroups(htm, r'class="page-link"\s*href="([^"]+?)"\s*rel="next"')[0]
            if nextPage:
                next_params = dict(baseItem)
                next_params.update({"page": page + 1, "title": _("Next page"), "max_page": max_page, "current_page": page + 1, "category": "list_items", "url": self.getFullUrl(nextPage)})
                self.addDir(next_params)

    def AZ(self, cItem):
        az = [chr(t) for t in range(ord("A"), ord("Z") + 1)] + ["0-9"]
        for title in az:
            url = "katalog/" + title
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("SerienStreamTo.listSeasons")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return

        trailer = self.cm.ph.getSearchGroups(data, 'data-trailer-url="([^"]+)')[0]
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description-text">([^<]+)')[0])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, 'data-src="([^"]+)')[0])

        imdb_id = self.extractImdbId(data)
        printDBG("IMDb DEBUG listSeasons id=[%s]" % imdb_id)
        imdb_rating = self.getIMDBRating(imdb_id) if imdb_id else "-"
        printDBG("IMDb DEBUG listSeasons rating=[%s]" % imdb_rating)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-nav">', "</nav>")
        if not data:
            return

        data = re.compile(r'href="([^"]+).*?data-season-pill="(\d+)', re.DOTALL).findall(data[0])
        for url, se in data:
            imdb_text = (" | IMDb: %s" % imdb_rating) if imdb_rating != "-" else ""
            title = "%s - %s" % (cItem["title"], _("Movies") if se == "0" else _("Season") + " " + str(se))
            desc_show = desc + imdb_text
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title,
                           "url": self.getFullUrl(url), "icon": icon, "desc": desc_show,
                           "imdb_rating": imdb_rating, "imdb_id": imdb_id, "imdb_lookup_url": self.getFullUrl(url)})
            if trailer:
                params.update({"trailer": trailer})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("SerienStreamTo.listEpisodes")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        season_num = self.cm.ph.getSearchGroups(cItem.get("title", ""), r'Staffel\s+(\d+)')[0]
        if not season_num:
            season_num = self.cm.ph.getSearchGroups(cItem.get("url", ""), r'/staffel-(\d+)')[0]
        season_num = int(season_num) if season_num.isdigit() else 0
        series_title = cItem.get("title", "").split(" - Staffel")[0].strip()
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="episode-row', "</tr>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, "location='([^']+)")[0])
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)">')[0])
            ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'cell">(\d+)')[0])
            if "Releases soon" in name:
                continue
            ep_num = int(ep) if ep.isdigit() else 0
            se_tag = "S%02dE%02d" % (season_num, ep_num) if season_num > 0 and ep_num > 0 else ""
            lang = language(item)
            lang_suffix = " - %s" % lang if lang else ""
            title = "%s - %s - %s%s" % (series_title, se_tag, name, lang_suffix) if se_tag else "%s - %s%s" % (series_title, name, lang_suffix)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "imdb_lookup_url": cItem.get("imdb_lookup_url", "") or cItem.get("url", "")})
            self.addVideo(params)

    def listNewEpisodes(self, cItem):
        printDBG("SerienStreamTo.listNewEpisodes")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="latest-episode', "</a>")
        if data:
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'ep-title"\stitle="([^"]+)')[0])
                se = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'ep-season">([^<]+)')[0])
                ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'ep-episode">([^<]+)')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
                season_num = self.cm.ph.getSearchGroups(se, r'(\d+)')[0]
                episode_num = self.cm.ph.getSearchGroups(ep, r'(\d+)')[0]
                season_ep = "S%sE%s" % (season_num.zfill(2), episode_num.zfill(2)) if season_num and episode_num else "%s %s" % (se, ep)
                lang = language(item)
                title = "%s - %s%s" % (name, season_ep, (" - %s" % lang) if lang else "")
                imdb_lookup_url = re.sub(r'/staffel-\d+/episode-\d+/?$', '/', url)
                params = dict(cItem)
                params.update({"good_for_fav": False, "title": title, "url": url, "icon": icon, "imdb_id": "", "imdb_rating": "-", "imdb_lookup_url": imdb_lookup_url})
                self.addVideo(params)

    def listValue(self, cItem):
        printDBG("SerienStreamTo.listValue")
        sts, data = self.getPage(self.getFullUrl("suche"))
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")
        if not data:
            return

        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data[0])
        dub = set()
        for url, title in data:
            if url not in dub:
                dub.add(url)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SerienStreamTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("suche?term=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("SerienStreamTo.getLinksForVideo [%s]" % cItem)
        urltab = []
        sidecarTxt = ""
        sidecarImg = ""
        sidecarEnabled = config.plugins.iptvplayer.serienstreamto_sidecar.value
        imdb_rating = cItem.get("imdb_rating", "")
        sidecarYear = ""
        sidecarGenre = ""

        try:
            article = self.getArticleContent(cItem)
            if article and isinstance(article, list):
                articleItem = article[0]
                sidecarTxt = articleItem.get("text", "")
                images = articleItem.get("images", [])
                if images and images[0].get("url"):
                    sidecarImg = images[0].get("url")

                otherInfo = articleItem.get("other_info", {})
                if not imdb_rating or imdb_rating == "-":
                    imdb_rating = otherInfo.get("imdb_rating", "")
                sidecarGenre = otherInfo.get("genres", "") or otherInfo.get("genre", "")
        except Exception:
            printExc("getArticleContent for sidecar failed")

        if not sidecarTxt:
            sidecarTxt = cItem.get("desc", "")
        if not sidecarImg:
            sidecarImg = cItem.get("icon", "")

        imdb_id = cItem.get("imdb_id", "")
        imdb_lookup_url = cItem.get("imdb_lookup_url", "") or cItem.get("url", "")

        try:
            if not imdb_id and imdb_lookup_url:
                printDBG("||SIDECAR imdb lookup url: [%s]" % imdb_lookup_url)
                sts, lookupData = self.getPage(imdb_lookup_url)
                if sts:
                    imdb_id = self.extractImdbId(lookupData)
                    printDBG("||SIDECAR imdb id from lookup url: [%s]" % imdb_id)

            if not imdb_id and cItem.get("url", "") != imdb_lookup_url:
                sts, pageData = self.getPage(cItem["url"])
                if sts:
                    imdb_id = self.extractImdbId(pageData)
                    printDBG("||SIDECAR imdb id from item url: [%s]" % imdb_id)

            if imdb_id:
                omdb = self.getOMDbData(imdb_id)
                printDBG("||SIDECAR OMDb: [%s]" % omdb)
                if omdb:
                    if not imdb_rating or imdb_rating in ("-", "", "N/A"):
                        imdb_rating = omdb.get("imdbRating", "")
                    sidecarYear = omdb.get("Year", "")
                    if not sidecarGenre:
                        sidecarGenre = omdb.get("Genre", "")
        except Exception:
            printExc("OMDb sidecar lookup failed")

        if sidecarTxt.startswith("IMDb:"):
            sidecarTxt = sidecarTxt.split("\n", 1)[1] if "\n" in sidecarTxt else ""

        sidecarLines = []

        if imdb_rating and imdb_rating not in ("-", "N/A", ""):
            sidecarLines.append(u"IMDb: %s/10" % imdb_rating)

        infoLine = []
        if sidecarYear and sidecarYear not in ("N/A", ""):
            infoLine.append(u"Jahr: %s" % sidecarYear)
        if infoLine:
            sidecarLines.append(u" / ".join(infoLine))

        if sidecarGenre and sidecarGenre not in ("N/A", ""):
            sidecarLines.append(sidecarGenre)

        if sidecarLines:
            prefix = u"\n".join(sidecarLines)
            if sidecarTxt:
                sidecarTxt = prefix + u"\n\n" + sidecarTxt
            else:
                sidecarTxt = prefix

        sidecar = buildSidecar(sidecarEnabled, sidecarTxt, sidecarImg)

        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="episode-links"', "</article>")
        if not data:
            return []

        data = re.compile(r'data-play-url="([^"]+).*?data-provider-name="([^"]+).*?data-language-label="([^"]+)', re.DOTALL).findall(data[0])
        for url, title, lang in data:
            fullUrl = decorateUrl(self.getFullUrl(url), referer=config.plugins.iptvplayer.serienstreamto_hosts.value, sidecar=sidecar)
            urltab.append({"name": "%s (%s)" % (title, lang), "url": fullUrl, "need_resolve": 1})

        if cItem.get("trailer"):
            trailerUrl = decorateUrl(cItem.get("trailer"), sidecar=sidecar)
            urltab.append({"name": "Trailer", "url": trailerUrl, "need_resolve": 1})

        return urltab

    def getVideoLinks(self, url):
        printDBG("SerienStreamTo.getVideoLinks [%s]" % url)

        cfgSidecarEnabled = config.plugins.iptvplayer.serienstreamto_sidecar.value
        cfgMkvEnabled = config.plugins.iptvplayer.serienstreamto_mkv.value
        sidecar = sidecarFromUrlMeta(url, cfgSidecarEnabled)

        def _addFinalMeta(videoLinks):
            return decorateResolvedLinkItems(videoLinks, sidecar=sidecar, mkvEnabled=cfgMkvEnabled)

        if "youtube" in url:
            return _addFinalMeta(self.up.getVideoLinkExt(url))

        params = dict(self.defaultParams)
        params["no_redirection"] = True
        sts, data = self.cm.getPage(url, params)
        if self.cm.meta["status_code"] == 302:
            if self.cm.meta.get("location"):
                url = self.cm.meta.get("location")
                if self.cm.isValidUrl(url):
                    return _addFinalMeta(self.up.getVideoLinkExt(url))
        elif sts:
            if "frameBridge" in data:
                SetIPTVPlayerLastHostError("Der Link ist geschützt ein s.to Login ist nötig. \nGeben Sie Login und Passwort in der Host Konfiguration (blau) ein und versuchen Sie es erneut.")
                return []

            url = self.cm.ph.getSearchGroups(data, 'href="([^"]+)"')[0]
            if self.cm.isValidUrl(url):
                return _addFinalMeta(self.up.getVideoLinkExt(url))
        return []

    def getArticleContent(self, cItem):
        printDBG("SerienStreamTo.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="small text-body lh-lg mb-3">', "</div>", withMarkers=False)[1]
        if not desc:
            desc = self.cm.ph.getSearchGroups(data, 'description-text">([^<]+)')[0]
        desc = self.cleanHtmlStr(desc)
        icon = strwithmeta(self.getFullIconUrl(self.cm.ph.getSearchGroups(data, 'data-src="([^"]+)')[0]) or cItem.get("icon", ""))
        imdb_id = cItem.get("imdb_id", "") or self.extractImdbId(data)
        if not imdb_id:
            lookup_url = cItem.get("imdb_lookup_url", "")
            if lookup_url and lookup_url != cItem.get("url", ""):
                sts2, data2 = self.getPage(lookup_url)
                if sts2:
                    imdb_id = self.extractImdbId(data2)
        printDBG("IMDb DEBUG article id=[%s]" % imdb_id)
        imdb_rating = self.getIMDBRating(imdb_id) if imdb_id else "-"
        printDBG("IMDb DEBUG article rating=[%s]" % imdb_rating)
        if imdb_rating != "-":
            otherInfo["imdb_rating"] = imdb_rating
        bc = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="flex-grow-1">', "</span>")
        if bc:
            bc = self.cm.ph.getSearchGroups(bc[0], 'title="([^"]+)')[0]
            if bc:
                otherInfo["broadcast"] = bc
        fields = {"country": '<strong class="me-1">Land:</strong>', "director": '<strong class="me-1">Regisseur:</strong>', "actors": '<strong class="me-1">Besetzung:</strong>', "genres": '<strong class="me-1">Genre:</strong>', "production": '<strong class="me-1">Produzent:</strong>'}
        for key, pattern in fields.items():
            value = self.cm.ph.getAllItemsBeetwenMarkers(data, pattern, "</li>")
            if value:
                val = re.findall('light">([^<]+)', value[0])
                if val:
                    otherInfo[key] = ", ".join(val)
        episode = {"country": '<strong class="me-1">Land:</strong>', "director": ">Regisseure</div>", "actors": ">Besetzung</div>", "production": ">Produzenten</div>"}
        for key, pattern in episode.items():
            value = self.cm.ph.getAllItemsBeetwenMarkers(data, pattern, "</div>")
            if value:
                val = re.findall('title="([^"]+)', value[0])
                if val:
                    otherInfo[key] = ", ".join(val)
        return [{"title": cItem["title"], "text": desc, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def login(self):
        login = config.plugins.iptvplayer.serienstreamto_login.value.strip()
        passw = config.plugins.iptvplayer.serienstreamto_password.value.strip()
        if login == "" and passw == "":
            return

        lurl = self.getFullUrl("/login")
        sts, data = self.getPage(lurl)
        if sts:
            token = self.cm.ph.getSearchGroups(data, r'csrf-token" content="([^"]+)')
            post = {"_token": token[0], "email": login, "password": passw}
            params = dict(self.defaultParams)
            params["no_redirection"] = True
            self.cm.getPage(lurl, params, post_data=post)
            if self.cm.meta["status_code"] == 302 and self.cm.meta.get("location") != lurl:
                printDBG("Login OK")
            else:
                printDBG("Login fehlgeschlagen")

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []

        if category == "jump_to_page" or ((name or "").endswith("-JUMP")):
            self.jumpToPage(self.currItem)
        elif name is None:
            self.listsTab(self.MENU, {"name": "category"})
            if config.plugins.iptvplayer.serienstreamto_uselogin.value:
                self.login()
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
        elif category == "list_AZ":
            self.AZ(self.currItem)
        elif category == "list_newepisodes":
            self.listNewEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        elif category == "empty":
            pass
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, SerienStreamTo(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes", "list_newepisodes"]
