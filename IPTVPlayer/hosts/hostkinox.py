# -*- coding: utf-8 -*-
LAST_MODIFIED = "21.10.2026"
# 18.10.2026 - new host (rewrite of the old Backup host)
#   lists: Latest / Popular / Kino pages (static), All films / series / documentaries and genres through
#   POST /aGET/List/ (First / Jump / Next page), search; series: season folder -> episodes
#   streams: /aGET/Mirror/ -> /redirect/<id> is a verification page of the site (two picture steps: SVG
#   animals with the question as text, a SHA-256 proof of work, honeypot and browser fields) - solved here
#   once per mirror; the site blocks the IP for 30 minutes after about ten verification pages in a row,
#   so a solved mirror is kept for the session
import base64
import hashlib
import json
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import GetIPTVSleep, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def _jsonLoads(text):
    # stdlib json gives unicode on Python 2 - as UTF-8 str like the rest of the host's texts
    return ensure_str_deep(json.loads(text))


def GetConfigList():
    return []


def gettytul():
    return "https://kinox.to/"


LIST_PAGE_SIZE = 60
# /gr/sys/lng/<id>.png (from /Options.html)
LANGS = {"1": "Deutsch", "2": "Englisch", "4": "Chinesisch", "5": "Spanisch", "6": "Französisch", "7": "Türkisch", "8": "Japanisch",
         "9": "Arabisch", "11": "Italienisch", "12": "Kroatisch", "13": "Serbisch", "14": "Bosnisch", "15": "Deutsch / Englisch",
         "16": "Niederländisch", "17": "Koreanisch", "24": "Griechisch", "25": "Russisch", "26": "Indisch"}

###################################################
# verification page of /redirect/<id>
###################################################
# picture templates: the tag names of the elements that carry the drawing transform (the noise has none);
# digits are an SVG <text> ("text:7")
GATE_SHAPES = {
    "ellipse,line,line,circle,circle,rect,rect,rect,rect": "turtle",
    "circle,rect,rect,rect,rect,circle,circle,circle": "rabbit",
    "path,circle,circle,line,line,line": "snake",
    "ellipse,ellipse,ellipse,ellipse,circle,circle,rect,line,line,circle,circle": "butterfly",
    "ellipse,circle,ellipse,polygon,polygon,circle,rect,rect,rect,rect,path": "cat",
    "ellipse,circle,ellipse,polygon,circle,ellipse,polygon,rect,rect": "bird",
    "ellipse,polygon,circle": "fish",
    "ellipse,ellipse,ellipse,ellipse,circle,circle,ellipse,rect": "dog",
    "rect,line,circle,circle,circle,rect,rect": "robot",
    "line,line,line,line,line,line,line,line,circle": "sun",
    "rect,rect,circle,circle": "car",
    "polygon,rect,rect": "house",
    "polygon,rect": "tree",
    "path,line,path": "umbrella",
    "circle,circle,circle": "cloud",
    "ellipse,polygon,polygon,polygon,polygon": "plane",
    "circle,circle": "moon",
    # one element shapes (see _gateShape)
    "path:MCCCCZ": "heart",
    "path:MLLLLLLLLLLLZ": "cross",
    "path:MLLLLLLZ": "arrow",
    "path:MLAZ": "quarter",
    "polygon:3": "triangle",
    "polygon:5": "pentagon",
    "polygon:10": "star",
    "rect": "rectangle",
    "circle": "circle",
    "circle:ring": "ring",
}
# the thing in the question (German, any case ending: the start of the word) -> template name
GATE_WORDS = (("schildkr", "turtle"), ("hase", "rabbit"), ("schlange", "snake"), ("vogel", "bird"), (u"vögel", "bird"),
              ("schmetterling", "butterfly"), ("fisch", "fish"), ("katze", "cat"), ("hund", "dog"), ("roboter", "robot"), ("sonne", "sun"),
              ("auto", "car"), ("haus", "house"), (u"häuser", "house"), ("baum", "tree"), (u"bäume", "tree"),
              ("regenschirm", "umbrella"), ("wolke", "cloud"), ("flugzeug", "plane"), ("herz", "heart"), ("mond", "moon"), ("kreuz", "cross"), ("pfeil", "arrow"),
              ("viertelkreis", "quarter"), ("dreieck", "triangle"), (u"fünfeck", "pentagon"), ("stern", "star"),
              ("rechteck", "rectangle"), ("quadrat", "rectangle"), ("kreis", "circle"), ("ring", "ring"))


def _gateWanted(question):
    """the template names the question asks for and whether it is negated; None when it names a thing this
    host does not know - an answer without it would be wrong, and every wrong answer makes the site add steps"""
    # "bitte klicke auf einen hasen, schmetterling und katze, um fortzufahren:"
    # "bitte wähle alles aus, was keine schildkröte ist:" / "... was kein herz ist:"
    match = re.search(r"klicke auf (.+?),? um fortzufahren", question)
    negated = False
    if not match:
        match = re.search(r"was keine?[nms]? (.+?) ist", question)
        negated = True
    if not match:
        return None, False
    wanted = set()
    for thing in re.split(r",\s*|\s+und\s+", match.group(1)):
        thing = re.sub(r"^(?:eine?[nms]?)\s+", "", thing.strip())
        if not thing:
            continue
        if thing.isdigit():
            wanted.add("text:" + thing)
            continue
        label = [lab for word, lab in GATE_WORDS if thing.startswith(word)]
        if not label:
            printDBG("Kinox.gateForm unknown word [%s]" % thing)
            return None, negated
        wanted.add(label[0])
    return (wanted or None), negated


def _gateScripts(data):
    # the page scripts are XOR-hex strings run through new Function()
    out = []
    for key, hexStr in re.findall(r'var _\w+="((?:[^"\\]|\\.)*)",_\w+="([0-9a-f]+)"', data):
        key = re.sub(r"\\(.)", r"\1", key)
        if not key:
            continue
        try:
            out.append("".join(chr(int(hexStr[i:i + 2], 16) ^ ord(key[(i // 2) % len(key)])) for i in range(0, len(hexStr) - 1, 2)))
        except ValueError:
            printExc()
    return "\n".join(out)


def _gateShape(b64):
    try:
        svg = base64.b64decode(b64)
        if not isinstance(svg, str):
            svg = svg.decode("utf-8", "replace")
    except Exception:
        return ""
    text = "".join(re.findall(r"<text[^>]*>([^<]+)</text>", svg)).strip()
    if text:
        return "text:" + text
    parts = [(tag, attrs) for tag, attrs in re.findall(r"<(\w+)([^>]*)>", svg) if "transform=" in attrs]
    if len(parts) == 1:
        # the geometric shapes are one element: polygon by its corners, path by its commands
        tag, attrs = parts[0]
        if tag == "polygon":
            points = re.search(r'\bpoints="([^"]*)"', attrs)
            return "polygon:%d" % len(re.findall(r"[\d.]+,[\d.]+", points.group(1) if points else ""))
        if tag == "path":
            return "path:" + "".join(re.findall(r"[A-Za-z]", re.search(r'\bd="([^"]*)"', attrs).group(1) if ' d="' in attrs else "")).upper()
        if tag == "circle" and ('fill="none"' in attrs or "stroke-width" in attrs or 'r="30"' in attrs):
            return "circle:ring"
    return ",".join(tag for tag, attrs in parts)


def _gatePow(challenge, zeros, nibble):
    # the first nonce whose sha256(challenge + nonce) starts with <zeros> "0" (and the next hex digit <= nibble)
    prefix = "0" * zeros
    nonce = 0
    while nonce < 20000000:
        digest = hashlib.sha256((challenge + str(nonce)).encode("utf-8")).hexdigest()
        if digest.startswith(prefix) and (nibble <= 0 or int(digest[zeros], 16) <= nibble):
            return str(nonce)
        nonce += 1
    return ""


def gateForm(data):
    """(action, post data) for one step of the verification page, (action, None) when the pictures are unknown,
    ("", None) when the page holds no verification form"""
    form = re.search(r'(?s)<form[^>]+action="([^"]+)"[^>]*>(.*?)</form>', data)
    if not form:
        return "", None
    action, body = form.group(1), form.group(2)
    scripts = _gateScripts(data)
    question = re.sub(r"<[^>]+>", "", re.search(r"(?s)<h3>(.*?)</h3>", body).group(1)) if "<h3>" in body else ""
    try:
        question = question.decode("utf-8")
    except (AttributeError, UnicodeError):
        pass
    question = question.lower()
    post = {}
    for name, value in re.findall(r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"', body):
        post[name] = value
    for name in re.findall(r'<input type="text" name="([^"]+)"', body):
        post[name] = ""  # honeypots
    for name in re.findall(r'<button type="submit" name="([^"]+)"', body):
        post[name] = ""
    pics = re.findall(r'data-id="([^"]+)"[^>]*>\s*<img src="data:image/svg\+xml;base64,([^"]+)"', body)
    choice = [name for name in post if name.startswith("ch_")]
    if pics and choice:
        wanted, negated = _gateWanted(question)
        multi = re.search(r"\b_m=!0\b", scripts) is not None or "_m=true" in scripts
        printDBG("Kinox.gateForm question[%s] wanted%s negated[%s] multi[%s]" % (question, sorted(wanted or ()), negated, multi))
        if not wanted:
            return action, None
        picked = []
        for picId, b64 in pics:
            shape = _gateShape(b64)
            label = shape if shape.startswith("text:") else GATE_SHAPES.get(shape, "")
            if not label:
                printDBG("Kinox.gateForm unknown picture [%s]" % shape)
            if (label in wanted) != negated:
                picked.append(picId)
        if not picked:
            return action, None
        if not multi and not negated:
            picked = picked[:1]
        post[choice[0]] = ",".join(picked)
    pow_ = re.search(r'_ch="([0-9a-f]+)",_df=(\d+),_nl=(\d+)', scripts)
    nonceField = [name for name in post if name.startswith("pn_")]
    if pow_ and nonceField:
        post[nonceField[0]] = _gatePow(pow_.group(1), int(pow_.group(2)), int(pow_.group(3)))
    now = int(time.time() * 1000)
    for name in post:
        if name.startswith("ix_"):
            post[name] = json.dumps({"m": 37, "c": 2, "t": [now - 2600 + i * 85 for i in range(20)], "d": 764, "f": 610}, separators=(",", ":"))
        elif name.startswith("ev_"):
            post[name] = json.dumps({"wd": 0, "pl": 5, "hl": 2, "hb": 0}, separators=(",", ":"))
        elif name.startswith("fp_"):
            post[name] = hashlib.sha256(b"1920x1080|24|-120|8|de-DE|1|Win32|0|kinox|ANGLE (Intel)").hexdigest()
    return action, post


class Kinox(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kinox", "cookie": "kinox.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_menu", "title": _("Movies"), "f_type": "movie", "pages": (("Kino-filme.html", _("Cinema movies")), ("Latest-Filme.html", _("Latest")), ("Popular-Filme.html", _("Popular")), ("All-Filme.html", _("All")))},
                     {"category": "list_menu", "title": _("Series"), "f_type": "series", "pages": (("Latest-TVSerien.html", _("Latest")), ("Popular-TVSerien.html", _("Popular")), ("Fernseh-TVSerien.html", _("All")))},
                     {"category": "list_menu", "title": _("Documentaries"), "f_type": "documentation", "pages": (("Latest-Dokumentationen.html", _("Latest")), ("Popular-Dokumentationen.html", _("Popular")), ("Alle-Dokumentationen.html", _("All")))},
                     {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("Genre.html")}] + self.searchItems()
        self.solvedLinks = {}
        self.watchedHelper = IPTVWatchedHelper("kinox")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"video": "video", "list_seasons": "series", "explore_item": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMenu(self, cItem):
        for page, title in cItem.get("pages", ()):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(page), "f_type": cItem.get("f_type", "")})

    def listGenres(self, cItem):
        printDBG("Kinox.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'href="(/Genre/[^"]+)"[^>]*>([^<]+)<', data):
            title = self.cleanHtmlStr(title)
            if url in seen or not title:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})

    def _addRows(self, data, fType):
        count = 0
        for item in data.split("<div onclick=\"location.href='")[1:]:
            path = item.split("'", 1)[0]
            if not path.startswith("/Stream/") or path == "/Stream/.html":
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a title="([^"]*)"')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<h1>(.*?)</h1>")[0])
            if not title:
                continue
            count += 1
            url = self.getFullUrl(path)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+\.(?:jpe?g|png|webp))"')[0])
            lang = LANGS.get(self.cm.ph.getSearchGroups(item, r"/lng/(\d+)\.png")[0], "")
            genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'href="/Genre/[^"]+"[^>]*>([^<]+)<', item))
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"IMDb:</b>\s*([0-9.]+)\s*/")[0])
            descLine = " | ".join(x for x in (lang, genres, "IMDb %s" % rating if rating else "") if x)
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="Descriptor">(.*?)</div>')[0])
            if descLine:
                desc = "%s[/br]%s" % (descLine, desc) if desc else descLine
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "title": title, "meta_title": title}
            if fType == "series":
                params.update({"category": "list_seasons", "meta_type": "tv"})
                self.addDir(params)
            elif fType in ("movie", "documentation"):
                params.update({"category": "video", "meta_type": "movie"})
                self.addVideo(params)
            else:
                # search / genres: the row does not say whether it is a film or a series
                params.update({"category": "explore_item"})
                self.addDir(params)
        return count

    def listItems(self, cItem):
        printDBG("Kinox.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        fType = cItem.get("f_type", "")
        listParams = cItem.get("list_params", "")
        if not listParams:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            listParams = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'id="ListParams" value="([^"]+)"')[0])
            if not listParams:
                # a page without paging (Latest / Popular / Kino / search)
                self._addRows(data, fType)
                return
        try:
            params = _jsonLoads(listParams)
        except Exception:
            printExc()
            return
        fType = fType or params.get("fType", "")
        params["Length"] = LIST_PAGE_SIZE
        post = {"Page": page, "Per_Page": LIST_PAGE_SIZE, "ListMode": "cover", "additional": json.dumps(params, separators=(",", ":"))}
        addParams = dict(self.defaultParams)
        addParams["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": cItem["url"]})
        sts, data = self.getPage(self.getFullUrl("/aGET/List/"), addParams, post)
        if not sts:
            return
        try:
            data = _jsonLoads(data)
            total = int(data.get("Total", 0) or 0)
            content = data.get("Content") or ""
        except Exception:
            printExc()
            return
        count = self._addRows(content, fType)
        lastPage = (total + LIST_PAGE_SIZE - 1) // LIST_PAGE_SIZE
        nextItem = dict(cItem)
        nextItem["list_params"] = listParams
        addPagingItems(self, nextItem, page, bool(count) and page < lastPage, lastPage)

    def _seasons(self, data):
        # [(season, [episodes])], the base of the episode request ("?Addr=..&SeriesID=..")
        select = self.cm.ph.getDataBeetwenMarkers(data, 'id="SeasonSelection"', "</select>", False)[1]
        base = self.cm.ph.getSearchGroups(select, r'rel="([^"]+)"')[0].replace("&amp;", "&")
        seasons = []
        for num, eps in re.findall(r'<option value="(\d+)" rel="([^"]*)"', select):
            seasons.append((num, [e for e in eps.split(",") if e.strip().isdigit()]))
        return base, seasons

    def _year(self, data):
        return self.cm.ph.getSearchGroups(data, r'<span class="Year">\((\d{4})\)</span>')[0]

    def listSeasons(self, cItem):
        printDBG("Kinox.listSeasons")
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        base, seasons = self._seasons(data)
        year = self._year(data)
        if not seasons:
            # a film or documentary (search / genre rows)
            params = dict(cItem)
            params.update({"category": "video", "url": url, "meta_type": "movie", "meta_year": year})
            if IsMediaNamingNormalized() and year and year not in params["title"]:
                params["title"] = "%s (%s)" % (params["title"], year)
            self.addVideo(params)
            return
        for num, eps in seasons:
            if not eps:
                continue
            params = dict(cItem)
            params.update({"category": "list_episodes", "good_for_fav": True, "title": "%s %s" % (_("Season"), num), "url": "%s#s%s" % (url, num),
                           "s_title": cItem.get("title", ""), "s_season": num, "s_episodes": ",".join(eps), "ep_base": base,
                           "meta_type": "tv", "meta_year": year})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Kinox.listEpisodes")
        url = cItem["url"].split("#", 1)[0]
        season = cItem.get("s_season") or self.cm.ph.getSearchGroups(cItem["url"], r"#s(\d+)")[0]
        eps = [e for e in cItem.get("s_episodes", "").split(",") if e]
        if not eps:
            # opened from favourites without the season data
            sts, data = self.getPage(url)
            if not sts:
                return
            eps = dict(self._seasons(data)[1]).get(season, [])
        show = cItem.get("s_title", "") or cItem.get("meta_title", "")
        normalize = IsMediaNamingNormalized()
        for ep in eps:
            title = "%s - %s" % (show, formatSxxExx(season, ep)) if normalize else "%s - %s %s, %s %s" % (show, _("Season"), season, _("Episode"), ep)
            params = dict(cItem)
            params.update({"category": "video", "good_for_fav": True, "title": title, "url": "%s#s%se%s" % (url, season, ep), "s_episode": ep})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Kinox.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        sts, data = self.getPage(self.getFullUrl("/Search.html?q=" + urllib_quote_plus(searchPattern.strip())))
        if sts:
            self._addRows(data, "")

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Kinox.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        pageUrl = url.split("#", 1)[0]
        se = re.search(r"#s(\d+)e(\d+)$", url)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="Descriptore">(.*?)</div>')[0]) or cItem.get("desc", "")
        year = cItem.get("meta_year", "") or self._year(data)
        if se:
            base = cItem.get("ep_base", "") or self._seasons(data)[0]
            if not base:
                return []
            addParams = dict(self.defaultParams)
            addParams["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": pageUrl})
            sts, data = self.getPage(self.getFullUrl("/aGET/MirrorByEpisode/%s&Season=%s&Episode=%s" % (base, se.group(1), se.group(2))), addParams)
            if not sts:
                return []
        urltab = []
        for item in re.findall(r'(?s)<li id="Hoster_\d+"(.*?)</li>', data):
            rel = self.cm.ph.getSearchGroups(item, r'rel="([^"]+)"')[0].replace("&amp;", "&")
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="Named">(.*?)</div>')[0])
            if not rel or not name:
                continue
            mirrors = self.cm.ph.getSearchGroups(item, r"Mirror</b>:\s*\d+/(\d+)")[0]
            mirrors = int(mirrors) if mirrors.isdigit() else 1
            for num in range(1, mirrors + 1):
                mRel = re.sub(r"&Mirror=\d+", "", rel) + ("&Mirror=%d" % num if mirrors > 1 else "")
                label = "%s (%d/%d)" % (name, num, mirrors) if mirrors > 1 else name
                urltab.append({"name": label, "url": strwithmeta(self.getFullUrl("/aGET/Mirror/" + mRel), {"Referer": pageUrl}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), year, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def _passGate(self, gateUrl, referer):
        # the hoster url behind /redirect/<id>, "" when the verification fails
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"Referer": referer})
        params["no_redirection"] = True
        reloads = 0
        sts, data = self.cm.getPage(gateUrl, params)
        for _step in range(12):
            if not sts:
                if self.cm.meta.get("status_code") == 403:
                    SetIPTVPlayerLastHostError("kinox.to: too many requests - the site blocks for about 30 minutes.")
                return ""
            location = self.cm.meta.get("location", "")
            if location and "/redirect/" not in location:
                return self.getFullUrl(location)
            action, post = gateForm(data)
            if not action:
                found = self.cm.ph.getSearchGroups(data, r'''(?:<iframe[^>]+src|location\.(?:href|replace)\s*[=(]\s*)["']([^"']+)''')[0]
                if self.cm.isValidUrl(found) and "kinox" not in found:
                    return found
                if reloads > 2:
                    return ""
                # the first visit only answers with a page that reloads itself
                reloads += 1
                sts, data = self.cm.getPage(gateUrl, params)
                continue
            if post is None:
                # one new page at most: each one counts towards the site's 30 minute block
                if reloads > 1:
                    SetIPTVPlayerLastHostError("kinox.to: unknown verification picture.")
                    return ""
                reloads += 1
                sts, data = self.cm.getPage(gateUrl, params)
                continue
            GetIPTVSleep().Sleep(2)
            postParams = dict(params)
            postParams["header"] = dict(params["header"], **{"Referer": gateUrl, "Origin": self.MAIN_URL.rstrip("/")})
            sts, data = self.cm.getPage(self.getFullUrl(action), postParams, post)
        return ""

    def getVideoLinks(self, videoUrl):
        printDBG("Kinox.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        mirrorUrl = str(videoUrl)
        hosterUrl = self.solvedLinks.get(mirrorUrl, "")
        if not hosterUrl:
            referer = strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL)
            addParams = dict(self.defaultParams)
            addParams["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": referer})
            sts, data = self.getPage(mirrorUrl, addParams)
            if not sts:
                return []
            try:
                stream = _jsonLoads(data).get("Stream", "")
            except Exception:
                printExc()
                return []
            gate = self.cm.ph.getSearchGroups(stream, r'src="([^"]+)"')[0].replace("\\/", "/")
            if not gate:
                return []
            gate = self.getFullUrl(gate)
            hosterUrl = self._passGate(gate, referer) if "/redirect/" in gate else gate
            if not hosterUrl:
                return []
            self.solvedLinks[mirrorUrl] = hosterUrl
        printDBG("Kinox.getVideoLinks hoster[%s]" % hosterUrl)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(hosterUrl, {"Referer": self.MAIN_URL})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Kinox.getArticleContent [%s]" % cItem)
        info = {}
        desc = ""
        year = cItem.get("meta_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="Descriptore">(.*?)</div>')[0])
            year = year or self._year(data)
            if year:
                info["year"] = year
            table = self.cm.ph.getDataBeetwenMarkers(data, 'class="CommonModuleTable"', "</table>", False)[1]
            fields = {"imdb wertung:": "imdb_rating", "genre:": "genres", "schauspieler:": "actors", "regie:": "director", "fsk:": "age_limit", "laufzeit:": "duration"}
            for label, value in re.findall(r'(?s)<td class="Label"[^>]*>(.*?)</td>\s*<td class="Value"[^>]*>(.*?)</td>', table):
                key = fields.get(self.cleanHtmlStr(label).lower(), "")
                value = self.cleanHtmlStr(re.sub(r"<div class=\"IMDBRatingLinks\".*", "", value))
                if key and value:
                    info[key] = value
        meta = {}
        mediaType = cItem.get("meta_type", "")
        if mediaType:
            try:
                meta = getMeta(mediaType, cItem.get("meta_title", ""), year)
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        plot = meta.get("plot", "")
        text = desc or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = cItem.get("icon", "") or meta.get("poster", "")
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
        elif category == "list_menu":
            self.listMenu(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ("list_seasons", "explore_item"):
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, Kinox(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kinox")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ["video", "list_seasons", "explore_item", "list_episodes"]
