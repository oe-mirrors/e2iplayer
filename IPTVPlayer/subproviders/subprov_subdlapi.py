# -*- coding: utf-8 -*-
import os
import zipfile
import requests
import re
import json

from Components.config import config, ConfigText, ConfigSubsection
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.isubprovider import (
    CSubProviderBase,
    CBaseSubProviderClass,
)
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    RemoveDisallowedFilenameChars,
    GetSubtitlesDir,
    E2ColoR,
)

Y = E2ColoR("yellow")
W = E2ColoR("white")
L = E2ColoR("lime")
C = E2ColoR("cyan")
OR = E2ColoR("orange")
if not hasattr(config.plugins, "iptvplayer"):
    config.plugins.iptvplayer = ConfigSubsection()
if not hasattr(config.plugins.iptvplayer, "subdlapi"):
    config.plugins.iptvplayer.subdlapi = ConfigText(default="", fixed_size=False)


def GetConfigList():
    from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import (
        TranslateTXT as _,
    )

    optionList = []
    optionList.append(("subdlapi", _("SubDL.com API Key"), "text"))
    return optionList


def get_subdl_api():
    try:
        return config.plugins.iptvplayer.subdlapi.value.strip()
    except Exception:
        printExc()
        return ""


BASE_URL = "https://api.subdl.com/api/v1"
DOWNLOAD_BASE = "https://dl.subdl.com/subtitle"


def build_headers():
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTVPlayer"}


def getBuildId(self):
    try:
        r = self.session.get("https://subdl.com", timeout=20)
        r.raise_for_status()
        match = re.search(r'"buildId":"(.*?)"', r.text)
        if match:
            return match.group(1)
    except Exception:
        printExc()
    return None


class SubDLAPIProvider(CBaseSubProviderClass):
    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.session = requests.Session()
        self.session.headers.update(build_headers())
        self.defaultParams = {"header": self.session.headers}
        self.currList = []

    def cleanTitle(self, title, for_search=True):
        if not for_search:
            return title
        text = re.sub(r"\\[cCpPbBuU][0-9A-Fa-f]{0,8}", "", title)
        text = re.sub(r"[cC][0-9A-Fa-f]{6}", "", text)
        text = re.sub(r"\s*[Ss](\d{1,2})\s*[Ee](\d{1,2})\s*", " ", text)
        text = re.sub(r"\s*[Ss]eason\s*\d+\s*[Ee]pisode\s*\d+\s*", " ", text)
        text = re.sub(r"\s*\d+x\d+\s*", " ", text)  # 1x01
        text = re.sub(r"\s*[Ss]eason\s*\d+\s*", " ", text)  # Season 1
        text = re.sub(r"\s*[Ee]pisode\s*\d+\s*", " ", text)  # Episode 1
        for sep in ["|", "-", ":", "(", "[", "]"]:
            if sep in text:
                text = text.split(sep)[0]
        text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
        words = text.split()
        clean = " ".join(words[:4]).strip()
        return clean if clean else " ".join(words[:2]).strip()

    def getMovieID(self, cItem):
        printDBG("\n=== [SubDL] Searching (HTML JSON mode) ===")
        raw_title = cItem.get("base_title", cItem.get("title", ""))
        clean_title = self.cleanTitle(raw_title)
        if not clean_title:
            printDBG("❌ No title provided")
            return
        search_url = "https://subdl.com/search/%s" % clean_title.replace(" ", "+")
        printDBG("URL: %s" % search_url)
        try:
            response = self.session.get(search_url, timeout=20)
            response.raise_for_status()
            html = response.text
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                html,
                re.DOTALL,
            )
            if not match:
                printDBG("❌ __NEXT_DATA__ not found")
                return
            json_data = match.group(1)

            data = json.loads(json_data)
            results = data.get("props", {}).get("pageProps", {}).get("list", [])
            results = sorted(
                results,
                key=lambda x: (
                    1 if x.get("type") == "tv" else 0,
                    -int(x.get("subtitles_count", 0) or 0),
                ),
            )
            printDBG("✅ Found %d results" % len(results))
            for item in results:
                sd_id = item.get("sd_id", "")
                if sd_id and not str(sd_id).startswith("sd"):
                    sd_id = "sd" + str(sd_id)
                title = item.get("name") or item.get("original_name") or "Unknown"
                year = item.get("year")
                year_str = str(year) if year else "N/A"
                subs_count = item.get("subtitles_count", 0)
                media_type = item.get("type", "movie")
                color_type = "orange" if media_type == "tv" else "cyan"
                type_display = "TV" if media_type == "tv" else "MOVIE"
                display_title = (
                    "%s (%s%s%s) - [ %s%s%s ] - [ %s%s%s subtitles ]"
                    % (
                        title,
                        Y, year_str, W,
                        E2ColoR(color_type), type_display, W,
                        L, subs_count, W
                    )
                )
                params_dir = dict(cItem)
                params_dir.update(
                    {
                        "title": display_title,
                        "sd_id": sd_id,
                        "slug": item.get("slug", ""),
                        "year": year_str if year_str != "N/A" else "",
                        "type": media_type,
                        "category": "get_languages",
                    }
                )
                self.addDir(params_dir)
                printDBG("✅ Found: %s" % display_title)
        except Exception as e:
            printDBG("❌ Error: %s" % str(e))
            printExc()
            self._searchViaOfficialAPI(cItem)

    def getLanguages(self, cItem):
        printDBG("\n=== [SubDL] Getting available languages ===")
        sd_id = cItem.get("sd_id")
        slug = cItem.get("slug")
        if not sd_id or not slug:
            printDBG("❌ Missing sd_id or slug")
            return
        season_slug = cItem.get("season_slug")
        if not season_slug:
            season_slug = "first-season"
        url = (
            "https://subdl.com/_next/data/Wne_av3hasQukc3wGybvM/en/subtitle/%s/%s/%s.json"
            % (sd_id, slug, season_slug)
        )
        printDBG("NextJS URL: %s" % url)
        lang_map = {}
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.cacheNextJS = {"sd_id": sd_id, "slug": slug, "data": data}
            page_props = data.get("pageProps", {})
            movie_info = page_props.get("movieInfo", {})
            seasons = movie_info.get("seasons", [])
            if seasons and not cItem.get("season_slug"):
                printDBG("Seasons detected: %d" % len(seasons))
                for s in seasons:
                    season_name = s.get("name", "")
                    season_number = s.get("number", "")
                    params_dir = dict(cItem)
                    params_dir.update(
                        {
                            "season_slug": season_number,
                            "title": season_name,
                            "category": "get_languages",
                        }
                    )
                    self.addDir(params_dir)
                printDBG("✅ Added %d seasons" % len(seasons))
                return
            lang_list = page_props.get("langList", [])
            if lang_list and isinstance(lang_list, list):
                for item in lang_list:
                    lang = item.get("lang")
                    count = item.get("count", 0)
                    if lang:
                        lang_map[lang.lower()] = {
                            "name": lang.capitalize(),
                            "count": count,
                        }
            else:
                grouped = page_props.get("groupedSubtitles", {})
                if isinstance(grouped, dict):
                    for lang, subs in grouped.items():
                        lang_map[lang.lower()] = {
                            "name": lang.capitalize(),
                            "count": len(subs) if isinstance(subs, list) else 0,
                        }
            printDBG("✅ NextJS languages: %s" % list(lang_map.keys()))
        except Exception as e:
            printDBG("❌ NextJS error: %s" % str(e))
            printExc()
            return
        added_count = 0
        for lang_code, info in lang_map.items():
            lang_name = info["name"]
            count = info["count"]
            title = "%s \c00FFFF00[ %d ]\c00FFFFFF" % (lang_name, count)
            params_dir = dict(cItem)
            params_dir.update(
                {
                    "language": lang_name,
                    "language_code": lang_code,
                    "category": "get_subtitles",
                    "title": title,
                }
            )
            self.addDir(params_dir)
            added_count += 1
        printDBG("✅ Added %d languages to menu" % added_count)

    def getSubtitles(self, cItem):
        printDBG("\n=== [SubDL] Fetching subtitles list ===")
        subtitles = self._searchSubtitle(cItem)
        for item in subtitles:
            params = dict(cItem)
            params.update(item)
            self.addSubtitle(params)

    def _searchSubtitle(self, cItem):
        printDBG("\n=== [SubDL] _searchSubtitle ===")
        API_KEY = get_subdl_api()
        lang_code = (cItem.get("language_code") or cItem.get("lang") or "").lower()
        selected_lang = (cItem.get("language") or lang_code).lower()
        sd_id = cItem.get("sd_id")
        imdb_id = cItem.get("imdb_id", "")
        outList = []
        # =========================================================
        # 1. NEXTJS (PRIMARY SOURCE)
        # =========================================================
        try:
            cache = getattr(self, "cacheNextJS", None)
            if cache and isinstance(cache, dict):
                data = cache.get("data", {})
                grouped = data.get("pageProps", {}).get("groupedSubtitles", {})
                subs_list = []
                if isinstance(grouped, dict):
                    subs_list = grouped.get(lang_code, [])
                # fallback matching
                if not subs_list:
                    for k, v in grouped.items():
                        if isinstance(k, str) and lang_code in k.lower():
                            subs_list = v
                            break
                if not isinstance(subs_list, list):
                    subs_list = []
                printDBG(
                    "NextJS subtitles for [%s]: %d items" % (lang_code, len(subs_list))
                )
                for item in subs_list:
                    if not isinstance(item, dict):
                        continue
                    title_raw = item.get("title", "")
                    author = item.get("author", "")
                    releases = item.get("releases", [])
                    clean = title_raw.replace(".", " ").replace("_", " ")
                    clean = " ".join(clean.split())
                    COLOR = Y
                    RESET = W

                    def color_season_episode(text):
                        if not text:
                            return text
                        # 1) S01E02 / s1e2
                        text = re.sub(
                            r"(?i)\bS\s*0*(\d+)\s*E\s*0*(\d+)\b",
                            lambda m: COLOR
                            + "S%02dE%02d" % (int(m.group(1)), int(m.group(2)))
                            + RESET,
                            text,
                        )
                        # 2) Season01 / Season 01
                        text = re.sub(
                            r"(?i)\bseason\s*0*(\d+)\b",
                            lambda m: COLOR + m.group(0) + RESET,
                            text,
                        )
                        # 3) Episode01 / Episode 01
                        text = re.sub(
                            r"(?i)\bepisode\s*0*(\d+)\b",
                            lambda m: COLOR + m.group(0) + RESET,
                            text,
                        )
                        # 4) S01
                        text = re.sub(
                            r"(?i)\bS0*(\d+)\b",
                            lambda m: COLOR + "S%02d" % int(m.group(1)) + RESET,
                            text,
                        )
                        # 5) E02
                        text = re.sub(
                            r"(?i)\bE0*(\d+)\b",
                            lambda m: COLOR + "E%02d" % int(m.group(1)) + RESET,
                            text,
                        )
                        return text

                    clean = color_season_episode(clean)
                    title = " | ".join(
                        [x for x in [lang_code.capitalize(), author, clean] if x]
                    )
                    desc = ""
                    if releases:
                        desc = "\c00FFFF00" + ("🎬 " + " | ".join(releases[:2]))
                    link = item.get("link", "")
                    url = "https://dl.subdl.com/subtitle/%s" % link if link else ""
                    params_sub = dict(cItem)
                    params_sub.update(
                        {
                            "title": title,
                            "description": desc,
                            "desc": desc,
                            "url": url,
                            "subtitle_id": str(item.get("id", "")),
                            "lang": lang_code,
                            "category": "get_download",
                        }
                    )
                    outList.append(params_sub)
                if outList:
                    printDBG("✅ Total (NextJS): %d subtitle items" % len(outList))
                    return outList
        except Exception as e:
            printDBG("⚠️ NextJS failed: %s" % str(e))
            printExc()
        # =========================================================
        # ❗ 2. FALLBACK API (ONLY IF NEXTJS FAILS)
        # =========================================================
        try:
            printDBG("🔁 Fallback API activated")
            params = {
                "api_key": API_KEY,
                "subs_per_page": "50",
                "releases": "1",
                "imdb_id": imdb_id if imdb_id else None,
                "sd_id": sd_id if sd_id else None,
            }
            url = "https://api.subdl.com/api/v1/subtitles"
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            json_data = response.json()
            subs = json_data.get("subtitles", [])
            for item in subs:
                if not isinstance(item, dict):
                    continue
                item_lang = (item.get("language") or item.get("lang") or "").lower()
                if selected_lang and item_lang and item_lang != selected_lang:
                    continue
                sub_id = item.get("id") or item.get("subtitle_id")
                if not sub_id:
                    continue
                title = item.get("release_name") or item.get("name") or item_lang
                params_sub = dict(cItem)
                params_sub.update(
                    {
                        "title": title,
                        "subtitle_id": str(sub_id),
                        "lang": item_lang,
                        "category": "get_download",
                    }
                )
                outList.append(params_sub)
            printDBG("✅ Total (API fallback): %d subtitle items" % len(outList))
            return outList
        except Exception as e:
            printDBG("❌ Error: %s" % str(e))
            printExc()
            return []

    def downloadSubtitleFile(self, cItem):
        printDBG("\n=== [SubDL] Downloading subtitle ===")
        sub_id = cItem.get("subtitle_id")
        bucket_link = cItem.get("bucketLink")
        direct_url = cItem.get("url") or cItem.get("link")
        lang = cItem.get("lang", "en")
        title = RemoveDisallowedFilenameChars(cItem.get("title", "subtitle"))
        download_url = None
        if direct_url:
            if direct_url.startswith("http"):
                download_url = direct_url
            else:
                download_url = "https://dl.subdl.com/subtitle/%s" % direct_url
        elif bucket_link:
            download_url = "https://dl.subdl.com/subtitle/%s" % bucket_link
        elif sub_id:
            sub_id = str(sub_id).replace(".zip", "")
            download_url = "https://dl.subdl.com/subtitle/%s.zip" % sub_id
        else:
            printDBG("❌ No valid download reference")
            return {}
        fileName = "%s-[SubDL].zip" % title
        filePath = os.path.join(GetSubtitlesDir(), fileName)
        printDBG("📥 Downloading: %s" % download_url)
        try:
            headers = build_headers()
            headers.update(
                {"Referer": "https://subdl.com/", "Origin": "https://subdl.com"}
            )
            response = requests.get(
                download_url,
                headers=headers,
                timeout=30,
                stream=True,
                allow_redirects=True,
            )
            if response.status_code != 200:
                printDBG("❌ HTTP ERROR: %s" % response.status_code)
                return {}
            with open(filePath, "wb") as f:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            printDBG("✅ Download complete: %s" % filePath)
            extracted_path = None
            subtitles_dir = GetSubtitlesDir()
            with zipfile.ZipFile(filePath, "r") as zip_ref:
                for fname in zip_ref.namelist():
                    if fname.lower().endswith((".srt", ".ass", ".ssa", ".sub", ".txt")):
                        zip_ref.extract(fname, subtitles_dir)
                        src_path = os.path.join(subtitles_dir, fname)
                        final_filename = RemoveDisallowedFilenameChars(
                            os.path.basename(fname)
                        )
                        extracted_path = os.path.join(subtitles_dir, final_filename)
                        if src_path != extracted_path:
                            if os.path.exists(extracted_path):
                                os.remove(extracted_path)
                            os.rename(src_path, extracted_path)
                        break
            if os.path.exists(filePath):
                os.remove(filePath)
            if extracted_path and os.path.exists(extracted_path):
                return {"title": title, "path": extracted_path, "lang": lang}
            return {"title": title, "path": filePath, "lang": lang}
        except Exception as e:
            printDBG("❌ Download error: %s" % str(e))
            printExc()
            if os.path.exists(filePath):
                os.remove(filePath)
            return {}

    def handleService(self, index, refresh=0):
        printDBG("SubDLAPIProvider.handleService start")
        CBaseSubProviderClass.handleService(self, index, refresh)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            API_KEY = get_subdl_api()
            if not API_KEY:
                printDBG("❌ ERROR: No SubDL API key configured")
                error_item = {
                    "title": _("⚠️ SubDL: API Key Required"),
                    "desc": _(
                        "Please configure your API Key in:\nSettings → IPTVPlayer → Subtitles → SubDL.com API Key"
                    ),
                    "category": "info_msg",
                }
                self.currList.append(error_item)
                CBaseSubProviderClass.endHandleService(self, index, refresh)
                return
            search_title = self.params.get("confirmed_title", "")
            search_year = self.params.get("year", "")
            search_imdb = self.params.get("imdbid", "")
            if search_title or search_imdb:
                fake_item = {
                    "name": "search_start",
                    "base_title": search_title,
                    "year": search_year,
                    "imdbid": search_imdb,
                    "category": "get_movieid",
                }
                self.getMovieID(fake_item)
            else:
                printDBG("⚠️ No title or imdb_id provided for search")
        elif category == "get_movieid":
            self.getMovieID(self.currItem)
        elif category == "get_languages":
            self.getLanguages(self.currItem)
        elif category == "get_subtitles":
            self.getSubtitles(self.currItem)
        elif category == "get_download":
            self.downloadSubtitleFile(self.currItem)
        elif category == "info_msg":
            try:
                if hasattr(self, "sessionEx") and self.sessionEx:
                    self.sessionEx.openMsgBox(
                        _(
                            'SubDL Setup:\n\n1. Visit: subdl.com/panel/api\n2. Copy your API Key\n3. Go to: Settings → IPTVPlayer → Subtitles\n4. Paste the key in "SubDL.com API Key" field'
                        ),
                        10000,
                    )
            except Exception as e:
                printDBG("Could not show info box: %s" % str(e))
            CBaseSubProviderClass.endHandleService(self, index, refresh)
        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):
    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubDLAPIProvider(params))
