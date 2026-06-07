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
BASE_URL = "https://api.subdl.com/api/v1"
DOWNLOAD_BASE = "https://dl.subdl.com/subtitle"
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


def build_headers():
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTVPlayer"}


class SubDLAPIProvider(CBaseSubProviderClass):
    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.session = requests.Session()
        self.session.headers.update(build_headers())
        self.defaultParams = {"header": self.session.headers}
        self.currList = []
        self._build_id_cache = None

    def convert_to_utf8(self, filePath):
        try:
            with open(filePath, "rb") as f:
                raw_data = f.read()
            try:
                raw_data.decode("utf-8")
                printDBG("✅ File is already UTF-8: %s" % filePath)
                return
            except UnicodeDecodeError:
                printDBG("⚠️ File is not UTF-8, attempting conversion from ANSI...")
            encodings_to_try = [
                "cp1256",
                "windows-1256",
                "iso-8859-6",
                "cp1252",
                "latin-1",
            ]
            decoded_content = None
            for enc in encodings_to_try:
                try:
                    decoded_content = raw_data.decode(enc)
                    printDBG("🔧 Successfully decoded using encoding: %s" % enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if decoded_content:
                with open(filePath, "w", encoding="utf-8") as f:
                    f.write(decoded_content)
                printDBG("✅ Successfully converted %s to UTF-8" % filePath)
            else:
                printDBG(
                    "❌ Could not decode file %s with common encodings." % filePath
                )
        except Exception as e:
            printDBG("❌ Error converting file encoding: %s" % str(e))
            printExc()

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
                display_title = "%s (%s%s%s) - [ %s%s%s ] - [ %s%s%s subtitles ]" % (
                    title,
                    Y,
                    year_str,
                    W,
                    E2ColoR(color_type),
                    type_display,
                    W,
                    L,
                    subs_count,
                    W,
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

    def getBuildId(self):
        if self._build_id_cache:
            return self._build_id_cache
        try:
            r = self.session.get("https://subdl.com", timeout=20)
            r.raise_for_status()
            match = re.search(r'"buildId":"(.*?)"', r.text)
            if match:
                self._build_id_cache = match.group(1)
                return self._build_id_cache
        except Exception:
            printExc()
        return None

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
        build_id = self.getBuildId()
        if not build_id:
            printDBG("❌ Cannot get buildId")
            return
        url = "https://subdl.com/_next/data/%s/en/subtitle/%s/%s/%s.json" % (
            build_id,
            sd_id,
            slug,
            season_slug,
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
            title = r"%s \c00FFFF00[ %d ]\c00FFFFFF" % (lang_name, count)
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
                    releases = item.get("releases", "")
                    quality_api = item.get("quality", "").strip()
                    display_type = ""
                    if quality_api:
                        q = quality_api.lower()
                        if q == "web-dl":
                            display_type = "WEB-DL"
                        elif q == "bluray":
                            display_type = "Bluray"
                        elif q == "hdtv":
                            display_type = "HDTV"
                        elif q == "hdrip":
                            display_type = "HDRip"
                        elif q == "dvdrip":
                            display_type = "DVDRip"
                        elif q == "bdrip":
                            display_type = "BDRip"
                        elif q == "webrip":
                            display_type = "WEBRip"
                        elif q == "tvrip":
                            display_type = "TVRip"
                        elif q == "cam":
                            display_type = "CAM"
                        else:
                            display_type = q.capitalize()
                    else:
                        type_patterns = r"(BluRay|WEB-DL|WEBDL|HDTV|HDRip|DVDRip|BDRip|TVRip|CAM|TS|TC|HDTC|PPV|DVDScr|WEBRip|WEB)"
                        match = re.search(type_patterns, title_raw, re.IGNORECASE)
                        if match:
                            display_type = match.group(1)
                        else:
                            display_type = "Other"
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
                        [
                            x
                            for x in [
                                lang_code.capitalize(),
                                display_type,
                                author,
                                clean,
                            ]
                            if x
                        ]
                    )
                    desc = ""
                    if releases:
                        desc = r"\c00FFFF00" + ("🎬 " + " | ".join(releases[:2]))
                    link = item.get("link", "")
                    url = "https://dl.subdl.com/subtitle/%s" % link if link else ""
                    downloads_count = item.get("downloads", 0)
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
                            "quality": quality_api,
                            "downloads": downloads_count,
                        }
                    )
                    outList.append(params_sub)

                def get_quality_weight(q_str):
                    if not q_str:
                        return 99
                    q = q_str.lower()
                    if "bluray" in q or "bdrip" in q:
                        return 1
                    if "web-dl" in q or "webdl" in q:
                        return 2
                    if "webrip" in q:
                        return 3
                    if "hdtv" in q:
                        return 4
                    if "hdrip" in q:
                        return 5
                    if "dvdrip" in q:
                        return 6
                    if "tvrip" in q:
                        return 7
                    if "cam" in q or "ts" in q or "tc" in q:
                        return 8
                    return 99  # Other

                outList.sort(
                    key=lambda x: (
                        get_quality_weight(x.get("quality", "other")),
                        -int(x.get("downloads", 0)),
                    )
                )
                if outList:
                    printDBG(
                        "✅ Total (NextJS): %d subtitle items (Sorted)" % len(outList)
                    )
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
            # Extract current episode number from video title
            video_title = self.params.get("confirmed_title", "") or cItem.get(
                "title", ""
            )
            printDBG("🎬 video_title = %s" % video_title)
            wanted_episode = ""
            # S01E07
            match = re.search(r"(?i)S(\d+)\s*E(\d+)", video_title)
            if match:
                wanted_episode = "S%02dE%02d" % (
                    int(match.group(1)),
                    int(match.group(2)),
                )
            # Season 1 Episode 7
            if not wanted_episode:
                match = re.search(r"(?i)season\s*(\d+)\s*episode\s*(\d+)", video_title)
                if match:
                    wanted_episode = "S%02dE%02d" % (
                        int(match.group(1)),
                        int(match.group(2)),
                    )
            # German formats:
            # Staffel 1 Episode 7
            # Staffel 1 Episoden 7
            # Staffel 1 Folge 7
            if not wanted_episode:
                match = re.search(
                    r"(?i)staffel\s*(\d+).*?(?:episode|episoden|folge)\s*(\d+)",
                    video_title,
                )
                if match:
                    wanted_episode = "S%02dE%02d" % (
                        int(match.group(1)),
                        int(match.group(2)),
                    )
            # 1x07
            if not wanted_episode:
                match = re.search(r"(?i)\b(\d+)x(\d+)\b", video_title)
                if match:
                    wanted_episode = "S%02dE%02d" % (
                        int(match.group(1)),
                        int(match.group(2)),
                    )
            printDBG("🎯 Wanted episode: %s" % wanted_episode)
            with zipfile.ZipFile(filePath, "r") as zip_ref:
                zip_list = [
                    x
                    for x in zip_ref.namelist()
                    if x.lower().endswith((".srt", ".ass", ".ssa", ".sub", ".txt"))
                ]
                selected_file = None
                # Search for matching episode subtitle
                if wanted_episode:
                    for item in zip_list:
                        if wanted_episode in item.upper():
                            selected_file = item
                            printDBG("✅ Matched episode subtitle: %s" % item)
                            break
                # Fallback to first subtitle file
                if not selected_file and zip_list:
                    selected_file = zip_list[0]
                    printDBG(
                        "⚠️ No exact episode match, using first subtitle: %s"
                        % selected_file
                    )
                if selected_file:
                    zip_ref.extract(selected_file, subtitles_dir)
                    src_path = os.path.join(subtitles_dir, selected_file)
                    final_filename = RemoveDisallowedFilenameChars(
                        os.path.basename(selected_file)
                    )
                    extracted_path = os.path.join(subtitles_dir, final_filename)
                    if src_path != extracted_path:
                        if os.path.exists(extracted_path):
                            os.remove(extracted_path)
                        os.rename(src_path, extracted_path)
                    self.convert_to_utf8(extracted_path)
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
                printDBG("ERROR: No SubDL API key configured")
                error_item = {
                    "title": _("SubDL: API Key Required"),
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
