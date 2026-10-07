# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard
#   - moiflix.fans (French movies and series): movies, series, discovery, genres, search (up to 100 hits,
#     the site has no paging there)
#   - First page / Jump / Next page on every list (?filter=null&page=N)
#   - rows keyed on the site's id url (/movie/<id>, /show/<id>; the slug urls only redirect to the home page)
#   - series -> seasons (when more than one) -> episodes, all from the series page
#   - links: the page's embed id -> ajax/embed -> player iframe -> urlparser; the site's only hoster
#     emmmmbed.com sits behind a Cloudflare Turnstile page: solved with the configured captcha service
#     (MyE2i / DeathByCaptcha), a clear message otherwise
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
###################################################
import base64
import re
from hashlib import md5

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs import pyaes
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

from Components.config import config


def GetConfigList():
    return []


def gettytul():
    return "https://moiflix.fans/"


ITEM_URL_RE = re.compile(r'href="((?:https?://[^"/]+)?/(movie|show)/[A-Za-z0-9]{20,})"')
EPISODE_LINK_RE = re.compile(r'<a href="([^"]+)">')
EPISODE_NUM_RE = re.compile(r"/season-(\d+)-episode-(\d+)\Z")
GENRE_LINK_RE = re.compile(r'<a href="(https?://[^"]+)"[^>]*>')
FIELD_LABEL_RE = re.compile(r'<div class="attr">')
FIELD_VALUE_RE = re.compile(r'</div>\s*<div class="text">')
FIELD_END_RE = re.compile(r"</div>")
# every player of the site is on this hoster, behind a Cloudflare Turnstile page
EMBED_GATE = "emmmmbed."
VIDEO_CATEGORIES = ("mfx_video",)
FOLDER_CATEGORIES = ("mfx_series", "mfx_season")


def _linksWithText(data, tagRe, accept):
    # [(accept(match), inner html)] of every <a> tag matched by tagRe that accept() takes, up to its first "</a>";
    # the rows of re.findall(r'(?s)<a ...>(.*?)</a>') with the url test done in Python (no backtracking regex)
    rows, pos = [], 0
    while True:
        match = tagRe.search(data, pos)
        if not match:
            return rows
        end = data.find("</a>", match.end())
        if end < 0:
            return rows
        value = accept(match)
        if value:
            rows.append((value, data[match.end():end]))
            pos = end + 4
        else:
            pos = match.start() + 1


def _findPairs(data, headRe, midRe, tailRe):
    # re.findall(r'(?s)<head>(.*?)<mid>(.*?)<tail>') in steps: [(text between head and mid, text between mid and tail)]
    rows, pos = [], 0
    while True:
        head = headRe.search(data, pos)
        mid = head and midRe.search(data, head.end())
        tail = mid and tailRe.search(data, mid.end())
        if not tail:
            return rows
        rows.append((data[head.end():mid.start()], data[mid.end():tail.start()]))
        pos = tail.end()


def _episodeLink(match):
    # (url, season, episode) of an <a href=".../episode/.../season-N-episode-M">
    url = match.group(1)
    num = EPISODE_NUM_RE.search(url)
    pos = url.find("/episode/", 1)
    if num and 0 < pos and pos + 9 < num.start():
        return url, num.group(1), num.group(2)
    return None


def _genreLink(match):
    # an absolute ".../category/..." url
    url = match.group(1)
    path = url.split("://", 1)[1]
    pos = path.find("/category/", 1)
    return url if 0 < pos and pos + 10 < len(path) else None


class Moiflix(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "moiflix", "cookie": "moiflix.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.MENU = [
            {"category": "mfx_list", "title": _("Movies"), "url": self.getFullUrl("movies")},
            {"category": "mfx_list", "title": _("Series"), "url": self.getFullUrl("shows")},
            {"category": "mfx_list", "title": _("Discovery"), "url": self.getFullUrl("discovery")},
            {"category": "mfx_genres", "title": _("Genres"), "url": self.getFullUrl("categories")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("moiflix")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("mfx_list",):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category == "mfx_series":
                return "series:%s" % path
            if category == "mfx_season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url, inner in _linksWithText(data, GENRE_LINK_RE, _genreLink):
            label = self.cleanHtmlStr(inner)
            if not label or url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "mfx_list", "title": label, "url": url, "good_for_fav": True})

    def _addTiles(self, data):
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<div class="list-movie">')[1:]:
            match = ITEM_URL_RE.search(block)
            if not match or match.group(1) in seen:
                continue
            url, kind = self.getFullUrl(match.group(1)), match.group(2)
            caption = self.cm.ph.getDataBeetwenMarkers(block, 'class="list-caption"', '<div class="list-year"', False)[1] or \
                self.cm.ph.getDataBeetwenMarkers(block, 'class="list-caption"', "</a>", False)[1]
            title = self.cleanHtmlStr(re.sub(r"^[^>]*>", "", caption, count=1))
            if not title:
                continue
            seen.add(url)
            year = self.cm.ph.getSearchGroups(block, r'(?s)<div class="list-year"[^>]*>\s*(\d{4})')[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="quality">(.*?)</div>')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="imdb">\s*<span>(.*?)</span>')[0])
            icon = self.cm.ph.getSearchGroups(block, r"""(?:data-src="|background-image:\s*url\(['"]?)([^"')]+)""")[0]
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Quality"), quality), (_("Rating"), rating)) if value)
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc,
                      "meta_title": title, "meta_year": year}
            if kind == "movie":
                params.update({"category": "mfx_video", "meta_type": "movie", "title": "%s (%s)" % (title, year) if year and normalize else title})
                self.addVideo(params)
            else:
                params.update({"category": "mfx_series", "meta_type": "tv", "title": title, "s_title": title})
                self.addDir(params)
        return len(seen)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%s?filter=null&page=%d" % (baseUrl, page)
        printDBG("Moiflix.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = self._addTiles(data)
        nav = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        pages = [int(x) for x in re.findall(r"page=(\d+)'", nav)]
        hasNext = bool(count) and bool(pages) and max(pages) > page
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, hasNext, 0, baseUrl.replace("{", "{{").replace("}", "}}") + "?filter=null&page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        url = self.getFullUrl("search/%s" % urllib_quote(searchPattern.strip()))
        printDBG("Moiflix.listSearchResult [%s]" % url)
        sts, data = self.getPage(url)
        if sts:
            self._addTiles(data)

    def _episodes(self, data):
        # {season: [(episode, url, name)]} from the episode tabs of a series page
        seasons = {}
        block = self.cm.ph.getDataBeetwenMarkers(data, "episodes tab-content", "nav-social", False)[1] or data
        for (url, season, episode), inner in _linksWithText(block, EPISODE_LINK_RE, _episodeLink):
            season, episode, url = int(season), int(episode), self.getFullUrl(url)
            if url not in [e[1] for e in seasons.get(season, [])]:
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)<div class="name">(.*?)</div>')[0])
                seasons.setdefault(season, []).append((episode, url, name))
        return seasons

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._episodes(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            season = next(iter(seasons))
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "mfx_season", "good_for_fav": True, "s_season": season,
                           "title": "%s %d" % (_("Season"), season), "desc": "%s: %d" % (_("Episodes"), len(seasons[season]))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        season = cItem.get("s_season", 1)
        if episodes is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            episodes = self._episodes(data).get(season, [])
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        for episode, url, name in sorted(episodes):
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %d - %s" % (show, _("Season"), season, name or "%s %d" % (_("Episode"), episode))
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "mfx_video", "good_for_fav": True, "title": title, "url": url,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / series / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="text-content">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        alias = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)Also Known As:\s*<(?:h2|font)[^>]*>(.*?)</(?:h2|font)>")[0])
        if alias:
            info["original_title"] = alias
        fields = {self.cleanHtmlStr(label).lower(): self.cleanHtmlStr(value) for label, value in
                  _findPairs(data, FIELD_LABEL_RE, FIELD_VALUE_RE, FIELD_END_RE)}
        for key, label in (("rating", "note imdb"), ("country", "pays"), ("genres", "genre"), ("year", "date de sortie")):
            for name, value in fields.items():
                if name.startswith(label) and value:
                    info[key] = re.sub(r"\s{2,}", ", ", value)
        return story, poster, info

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Moiflix.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        for embedId in re.findall(r'data-embed="([^"]+)"', data):
            if embedId in seen:
                continue
            seen.add(embedId)
            params = dict(self.defaultParams, header=dict(self.HEADER, Referer=url, **{"X-Requested-With": "XMLHttpRequest"}))
            sts, frame = self.getPage(self.getFullUrl("ajax/embed"), params, {"id": embedId})
            playerUrl = self.cm.ph.getSearchGroups(frame, r'<iframe[^>]+src="([^"]+)"', ignoreCase=True)[0] if sts else ""
            playerUrl = self.getFullUrl(playerUrl)
            if self.cm.isValidUrl(playerUrl):
                urltab.append({"name": self.up.getHostName(playerUrl), "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def _getGatedEmbedLinks(self, url):
        # emmmmbed.com answers with a Cloudflare Turnstile page whose form posts the token back to the same url;
        # solved through the configured captcha service (MyE2i / DeathByCaptcha)
        hostName = self.up.getHostName(url)
        params = dict(self.defaultParams, header=dict(self.HEADER, Referer=self.getMainUrl()))
        sts, data = self.getPage(url, params)
        if not sts:
            return []
        sitekey = self.cm.ph.getSearchGroups(data, r"""sitekey\s*:\s*['"]([^'"]+)['"]""")[0]
        if sitekey:
            # no captcha service set ("Auto"): MyE2i, else the user only gets a wiki hint (box log 07.10.)
            bypass = config.plugins.iptvplayer.captcha_bypass.value or "mye2i"
            token = self.processCaptcha(sitekey, url, bypassCaptchaService=bypass, captchaType="cf_re")[0]
            if not token:
                SetIPTVPlayerLastHostError("%s: %s" % (hostName, _("Captcha was not entered.")))
                return []
            params["header"] = dict(self.HEADER, Referer=url)
            sts, data = self.getPage(url, params, {"cf-turnstile-response": token, "original_referer": self.getMainUrl()})
            if not sts or "cf-turnstile" in data:
                SetIPTVPlayerLastHostError("%s: %s" % (hostName, _("%s could not solve the captcha.") % "E2iPlayer"))
                return []
        # the player page after the captcha ("PlayerBx", VideoJS + crypto-js, box logs 07.10.): the MP4 url is
        # CryptoJS-encrypted in an inline script; the usual player patterns and one nested iframe are tried as well
        linksTab = self._extractGatedPlayer(data, url, hostName, 0)
        if not linksTab:
            # fix 071026: the page structure only goes to the log when nothing was found (Turnstile cannot be solved on the PC)
            self._debugPlayerPage(url, data)
            SetIPTVPlayerLastHostError(_("Hosting \"%s\" not supported.") % hostName)
        return linksTab

    def _debugPlayerPage(self, url, data):
        # page head without styles/whitespace + every url and script/data hint it holds, for the box log
        try:
            text = re.sub(r'(?is)<style[^>]*>.*?</style>', '', data)
            text = re.sub(r'\s+', ' ', text)
            printDBG("Moiflix.player page [%s] size[%d] head:\n%s" % (url, len(data), text[:1500]))
            hints = re.findall(r"""(?:src|href|data-[a-z-]+|file|link|url|action)\s*[=:]\s*['"]([^'"]{6,300})['"]""", data, re.I)
            hints += re.findall(r"""['"]((?:https?:)?//[^'"\s<>]{4,300})['"]""", data)
            hints += re.findall(r"""(?:fetch|\$\.(?:get|post|ajax)|axios\.(?:get|post))\s*\(\s*['"`]([^'"`]{2,200})""", data)
            seen = []
            for item in hints:
                if item not in seen and "challenges.cloudflare" not in item:
                    seen.append(item)
            printDBG("Moiflix.player page hints: %s" % seen[:60])
            printDBG("Moiflix.player page markers: packed[%s] jwplayer[%s] atob[%s] jwt[%s] cryptojs[%s] scripts[%d]" % (
                "eval(function(p,a,c,k,e," in data, "jwplayer" in data.lower(), "atob(" in data,
                bool(re.search(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', data)), "CryptoJS" in data, data.lower().count("<script")))
            # add 071026: the inline scripts in full (box log 07.10. #3: "PlayerBx" page, VideoJS + crypto-js, the source
            # sits in an inline script) - the next log shows how the encrypted source and its key are passed
            total = 0
            for script in re.findall(r'(?is)<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', data):
                script = re.sub(r'\s+', ' ', script).strip()
                if not script or total > 12000:
                    continue
                printDBG("Moiflix.player page inline script [%d]:\n%s" % (len(script), script[:4000]))
                total += min(len(script), 4000)
        except Exception:
            printExc()

    def _cryptoJsSources(self, data):
        # fix 071026: box log 07.10. #4 - the PlayerBx script is obfuscator.io code: CryptoJS[_0x..(0x2ba)]['decrypt'](a, b)
        # with the "U2FsdGVkX1..." (OpenSSL Salted__) cipher text in the string table and the passphrase as a literal
        # argument (wrapper(_0x..(0x2e7), '31d4...')). Rotating the table is not needed: every Salted blob is tried with
        # the short literals, call arguments first; only the right key gives valid padding and UTF-8 text
        blobs = []
        for blob in re.findall(r"""['"](U2FsdGVkX1[A-Za-z0-9+/=]{20,})['"]""", data):
            if blob not in blobs:
                blobs.append(blob)
        if not blobs:
            return []
        keys = re.findall(r""",\s*['"]([^'"\\\s]{8,64})['"]\s*\)""", data)
        keys += re.findall(r"""['"]([0-9A-Za-z_\-]{8,64})['"]""", data)
        plains = []
        for blob in blobs[:5]:
            try:
                raw = base64.b64decode(blob)
            except Exception:
                continue
            if raw[:8] != b"Salted__" or len(raw) < 32 or len(raw) % 16:
                continue
            tried = set()
            for key in keys:
                if key in tried:
                    continue
                tried.add(key)
                if len(tried) > 600:
                    break
                plain = self._decryptSalted(raw, key)
                if plain:
                    printDBG("Moiflix.CryptoJS (obfuscated) key[%s] plain text [%d]: %s" % (key, len(plain), plain[:300]))
                    plains.append(plain)
                    break
        # a bare url as plain text: quoted, so the candidate patterns see it
        return ['"%s"' % p.strip() if re.match(r'(?:https?:)?//\S+$', p.strip()) else p for p in plains]

    def _decryptSalted(self, raw, key):
        # OpenSSL EVP_BytesToKey (md5) + AES-256-CBC; None unless the padding and the UTF-8 text are valid
        salt, derived, prev = raw[8:16], b"", b""
        while len(derived) < 48:
            prev = md5(prev + ensure_binary(key) + salt).digest()
            derived += prev
        try:
            if len(raw) >= 48:
                # the last block alone shows a wrong key (bad padding) without decrypting the whole text
                last = bytearray(pyaes.AESModeOfOperationCBC(derived[:32], raw[-32:-16]).decrypt(raw[-16:]))
                pad = last[-1]
                if not 0 < pad <= 16 or any(b != pad for b in last[-pad:]):
                    return None
            decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(derived[:32], derived[32:48]))
            raw = decrypter.feed(raw[16:]) + decrypter.feed()
            raw.decode("utf-8")
        except Exception:
            return None
        plain = ensure_str(raw)
        if not plain.strip() or re.search(r"[\x00-\x08\x0e-\x1f]", plain):
            return None
        return plain

    def _playerCandidates(self, data, baseUrl):
        # add 071026: iframes (any quote, src/data-src), server lists (data-link/data-url/onclick), JWPlayer file/sources,
        # plain m3u8/mp4, the same again inside packed JS, urls in base64 strings and JWT payloads
        sources = [data]
        try:
            unpacked = get_packed_data(data)
            if unpacked:
                sources.append(unpacked)
        except Exception:
            printExc()
        sources.extend(self._cryptoJsSources(data))
        encoded = re.findall(r"""atob\(\s*['"]([A-Za-z0-9+/=_-]{16,})['"]""", data)
        encoded += re.findall(r'eyJ[A-Za-z0-9_-]{10,}\.([A-Za-z0-9_-]{10,})', data)
        for b64 in encoded:
            try:
                b64 = b64.replace("-", "+").replace("_", "/")
                sources.append(ensure_str(base64.b64decode(b64 + "=" * (-len(b64) % 4)), errors="ignore"))
            except Exception:
                pass
        patterns = (
            r"""<iframe[^>]+?(?:data-src|src)\s*=\s*['"]([^'"]+)['"]""",
            r"""data-(?:link|url|src|embed|player|video)\s*=\s*['"]((?:https?:)?//[^'"]+)['"]""",
            r"""(?:go_to_player|loadPlayer|playVideo|changeServer|setPlayer|window\.open|location\.href\s*=)\s*\(?\s*['"]((?:https?:)?//[^'"]+)['"]""",
            r"""["']?(?:file|src|link|url|embed_url|embedUrl)["']?\s*:\s*["']((?:https?:)?//[^"']+)["']""",
            r"""['"]((?:https?:)?//[^'"\s<>]+?\.(?:m3u8|mp4)(?:\?[^'"\s<>]*)?)['"]""",
        )
        candidates = []
        for source in sources:
            source = source.replace("\\/", "/")
            for pattern in patterns:
                for item in re.findall(pattern, source, re.I):
                    item = self.getFullUrl(item.strip().replace("&amp;", "&"), baseUrl)
                    if not self.cm.isValidUrl(item) or item in candidates:
                        continue
                    if re.search(r'(?i)challenges\.cloudflare|googletagmanager|google-analytics|jsdelivr|cdnjs|fonts\.|\.(?:js|css|png|jpe?g|gif|svg|webp|ico|woff2?)(?:\?|$)', item):
                        continue
                    candidates.append(item)
        return candidates

    def _extractGatedPlayer(self, data, url, hostName, depth):
        candidates = self._playerCandidates(data, url)
        printDBG("Moiflix._extractGatedPlayer depth[%d] candidates: %s" % (depth, candidates))
        nested = []
        for item in candidates:
            if re.search(r'(?i)\.(?:m3u8|mp4)(?:\?|$)', item):
                stream = strwithmeta(item, {"Referer": url, "User-Agent": self.HEADER["User-Agent"]})
                if ".m3u8" in item.lower():
                    linksTab = getDirectM3U8Playlist(stream, checkContent=True)
                    if linksTab:
                        return linksTab
                    continue
                return [{"name": hostName, "url": stream}]
            if EMBED_GATE in item and item.rstrip("/") == url.rstrip("/"):
                continue
            if EMBED_GATE not in item and 1 == self.up.checkHostSupport(item):
                linksTab = self.up.getVideoLinkExt(strwithmeta(item, {"Referer": url}))
                if linksTab:
                    return linksTab
                continue
            nested.append(item)
        # an unknown or same-site player page: follow it once and search again
        if depth == 0:
            for item in nested[:3]:
                params = dict(self.defaultParams, header=dict(self.HEADER, Referer=url))
                sts, page = self.getPage(item, params)
                if not sts or not page:
                    continue
                linksTab = self._extractGatedPlayer(page, item, self.up.getHostName(item), 1)
                if linksTab:
                    return linksTab
                self._debugPlayerPage(item, page)
        return []

    def getVideoLinks(self, videoUrl):
        printDBG("Moiflix.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if EMBED_GATE in videoUrl and 1 != self.up.checkHostSupport(videoUrl):
            return decorateResolvedLinkItems(self._getGatedEmbedLinks(videoUrl), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Moiflix.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        url = cItem.get("url", "")
        if "/episode/" in url:
            # the series page carries the story and the fields
            url = re.sub(r"/episode/([^/]+)/.*", r"/show/\1", url)
        sts, data = self.getPage(url)
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or ("tv" if "/show/" in url else "movie")
        metaTitle = info.get("original_title") or cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, metaTitle, cItem.get("meta_year") or info.get("year", ""))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Moiflix.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "mfx_genres":
            self.listGenres(self.currItem)
        elif category == "mfx_list":
            self.listItems(self.currItem)
        elif category == "mfx_series":
            self.listSeasons(self.currItem)
        elif category == "mfx_season":
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
        CHostBase.__init__(self, Moiflix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("moiflix")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in FOLDER_CATEGORIES
