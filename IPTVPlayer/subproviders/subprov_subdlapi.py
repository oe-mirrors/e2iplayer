# -*- coding: utf-8 -*-
import os
import zipfile
import requests
import re
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
                printDBG("File is already UTF-8: %s" % filePath)
                return
            except UnicodeDecodeError:
                printDBG("File is not UTF-8, attempting conversion from ANSI...")
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
                    printDBG(" Successfully decoded using encoding: %s" % enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if decoded_content:
                with open(filePath, "w", encoding="utf-8") as f:
                    f.write(decoded_content)
                printDBG("Successfully converted %s to UTF-8" % filePath)
            else:
                printDBG("Could not decode file %s with common encodings." % filePath)
        except Exception as e:
            printDBG("Error converting file encoding: %s" % str(e))
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
        printDBG("\n=== [SubDL] Searching ===")
        raw_title = cItem.get("base_title", cItem.get("title", ""))
        clean_title = self.cleanTitle(raw_title)
        if not clean_title:
            printDBG("No title provided")
            return
        search_url = "https://subdl.com/search/%s" % clean_title.replace(" ", "+")
        printDBG("URL: %s" % search_url)
        results_found = False
        try:
            response = self.session.get(search_url, timeout=20)
            response.raise_for_status()
            html = response.text
            items_list = []
            pattern = r'<a\s+href="/subtitle/(sd\d+)/([^"]+)".*?<h3[^>]*>(.*?)</h3>.*?bg-(tvColor|movieColor)[^>]*>(tv|movie)</div>.*?(\d+)\s+subtitles'
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                sd_id, slug, title_raw, color_class, media_type, subs_count = match
                year_match = re.search(r"\((\d{4})\)", title_raw)
                year = year_match.group(1) if year_match else ""
                display_name = re.sub(r"\s*\(\d{4}\)\s*", "", title_raw).strip()
                items_list.append(
                    {
                        "sd_id": sd_id,
                        "slug": slug,
                        "name": display_name,
                        "year": year,
                        "type": media_type.lower(),
                        "subtitles_count": int(subs_count),
                    }
                )
            if items_list:
                results_found = True
                items_list = sorted(
                    items_list,
                    key=lambda x: (
                        0 if x.get("type") == "tv" else 1,
                        -int(x.get("subtitles_count", 0)),
                    ),
                )
                printDBG("Found %d results via HTML Parsing" % len(items_list))
                for item in items_list:
                    sd_id = item.get("sd_id", "")
                    title = item.get("name", "Unknown")
                    year_str = str(item.get("year", "")) or "N/A"
                    subs_count = item.get("subtitles_count", 0)
                    media_type = item.get("type", "movie")
                    color_type = "orange" if media_type == "tv" else "cyan"
                    type_display = "TV" if media_type == "tv" else "MOVIE"
                    display_title = (
                        "%s (%s%s%s) - [ %s%s%s ] - [ %s%s%s subtitles ]"
                        % (
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
            else:
                printDBG("No results found in new HTML structure")
        except Exception as e:
            printDBG("Scraping Error: %s" % str(e))
            printExc()
        if not results_found:
            printDBG("Falling back to Official SubDL API...")
            self._searchViaOfficialAPI(cItem)

    def _searchViaOfficialAPI(self, cItem):
        API_KEY = get_subdl_api()
        if not API_KEY:
            printDBG("Cannot fallback: No API Key configured")
            return
        raw_title = cItem.get("base_title", cItem.get("title", ""))
        clean_title = self.cleanTitle(raw_title)
        url = "https://api.subdl.com/api/v1/subtitles"
        params = {"api_key": API_KEY, "query": clean_title, "subs_per_page": "30"}
        try:
            resp = self.session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            grouped = {}
            for sub in data.get("subtitles", []):
                sid = sub.get("sd_id") or sub.get("id")
                if not sid:
                    continue
                if sid not in grouped:
                    grouped[sid] = {
                        "sd_id": sid,
                        "slug": sub.get("slug", ""),
                        "name": sub.get("release_name") or sub.get("name"),
                        "year": sub.get("year", ""),
                        "type": sub.get("type", "movie"),
                        "subtitles_count": 0,
                    }
                grouped[sid]["subtitles_count"] += 1
            for item in grouped.values():
                sd_id = item["sd_id"]
                if not str(sd_id).startswith("sd"):
                    sd_id = "sd" + str(sd_id)
                title = item.get("name", "Unknown")
                year_str = str(item.get("year", "")) or "N/A"
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
        except Exception as e:
            printDBG("API Fallback failed: %s" % str(e))
            printExc()

    def getLanguages(self, cItem):
        printDBG("\n=== [SubDL] Getting available languages ===")
        sd_id = cItem.get("sd_id")
        slug = cItem.get("slug")
        if not sd_id or not slug:
            printDBG("Missing sd_id or slug")
            return
        if cItem.get("season_slug"):
            self._fetchLanguagesFromPage(cItem)
            return
        url = "https://subdl.com/subtitle/%s/%s" % (sd_id, slug)
        printDBG("Checking page: %s" % url)
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            html = response.text
            has_languages = bool(re.search(r'data-language="[^"]+"', html))
            if has_languages:
                printDBG(
                    "Subtitle page detected (has data-language), extracting languages..."
                )
                self._cached_html = html
                self._cached_url = url
                self._extractLanguagesFromHTML(html, cItem)
                return
            season_pattern = (
                r'<a\s+href="/subtitle/%s/%s/([^"]*(?:season|specials)[^"]*)"[^>]*>.*?<h3[^>]*>(.*?)</h3>'
                % (re.escape(sd_id), re.escape(slug))
            )
            season_matches = re.findall(season_pattern, html, re.DOTALL | re.IGNORECASE)
            if season_matches:
                printDBG(
                    "TV Show seasons page detected, extracting %d seasons..."
                    % len(season_matches)
                )
                added_count = 0
                for season_slug, season_name in season_matches:
                    clean_name = season_name.strip()
                    params_dir = dict(cItem)
                    params_dir.update(
                        {
                            "season_slug": season_slug,
                            "title": clean_name,
                            "category": "get_languages",
                        }
                    )
                    self.addDir(params_dir)
                    added_count += 1
                printDBG("Added %d seasons" % added_count)
                return
            printDBG("No languages or seasons found in HTML")
            self._getLanguagesViaAPI(cItem)
        except Exception as e:
            printDBG("Page check error: %s" % str(e))
            printExc()
            self._getLanguagesViaAPI(cItem)

    def _fetchLanguagesFromPage(self, cItem):
        sd_id = cItem.get("sd_id")
        slug = cItem.get("slug")
        season_slug = cItem.get("season_slug")
        url = "https://subdl.com/subtitle/%s/%s/%s" % (sd_id, slug, season_slug)
        printDBG("Season Page URL: %s" % url)
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            html = response.text
            self._cached_html = html
            self._cached_url = url
            self._extractLanguagesFromHTML(html, cItem)
        except Exception as e:
            printDBG("Season page error: %s" % str(e))
            printExc()
            self._getLanguagesViaAPI(cItem)

    def _extractLanguagesFromHTML(self, html, cItem):
        desc_parts = []
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        movie_title = ""
        if h1_match:
            movie_title = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip()
        released = ""
        released_match = re.search(r"Released:\s*([\d\-]+)", html)
        if released_match:
            released = released_match.group(1)
        imdb = ""
        imdb_match = re.search(r"IMDb:\s*([\d\.]+)", html)
        if imdb_match:
            imdb = imdb_match.group(1)
        rated = ""
        rated_match = re.search(r"Rated:\s*([^<\n]+)", html)
        if rated_match:
            rated = rated_match.group(1).strip()
        network = ""
        network_match = re.search(r"Network:\s*([^<\n]+)", html)
        if network_match:
            network = network_match.group(1).strip()
        storyline = ""
        story_match = re.search(
            r"Storyline.*?</h2>\s*(?:<div[^>]*>.*?</div>\s*)?<p[^>]*>(.*?)</p>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if story_match:
            storyline = re.sub(r"<[^>]+>", "", story_match.group(1)).strip()
        if movie_title:
            desc_parts.append("%s%s%s" % (Y, movie_title, W))
        info_line_parts = []
        if released:
            info_line_parts.append("%sReleased:%s %s" % (Y, W, released))
        if imdb:
            info_line_parts.append("%sIMDb:%s %s" % (Y, W, imdb))
        if rated:
            info_line_parts.append("%sRated:%s %s" % (Y, W, rated))
        if network:
            info_line_parts.append("%sNetwork:%s %s" % (Y, W, network))
        if info_line_parts:
            desc_parts.append(" | ".join(info_line_parts))
        if storyline:
            desc_parts.append("%sStory :%s %s" % (Y, W, storyline))
        full_desc = "\n".join(desc_parts) if desc_parts else ""
        printDBG("Description extracted: %d chars" % len(full_desc))
        if full_desc:
            printDBG("Desc preview: %s" % full_desc[:200])
        poster_url = ""
        poster_match = re.search(
            r'<img[^>]*src="(https://poster\.subdl\.com/poster/[^"]+)"', html
        )
        if poster_match:
            poster_url = poster_match.group(1)
        lang_pattern = r'data-language="([^"]+)"[^>]*data-language-name="([^"]+)"[^>]*style="[^"]*--rows:\s*(\d+)'
        matches = re.findall(lang_pattern, html, re.IGNORECASE)
        if not matches:
            lang_pattern_alt = (
                r'data-language="([^"]+)"[^>]*data-language-name="([^"]+)"'
            )
            matches = re.findall(lang_pattern_alt, html, re.IGNORECASE)
            matches = [(code, name, "0") for code, name in matches]
        if not matches:
            printDBG("No languages found in HTML")
            self._getLanguagesViaAPI(cItem)
            return
        added_count = 0
        seen_langs = set()
        for match in matches:
            lang_code = match[0].lower()
            lang_name = match[1].strip()
            rows_count = match[2] if len(match) > 2 else "0"
            if lang_code in seen_langs:
                continue
            seen_langs.add(lang_code)
            display_name = lang_name if lang_name else lang_code.capitalize()
            title = r"%s \c00FFFF00[ %s ]\c00FFFFFF" % (display_name, str(rows_count))
            params_dir = dict(cItem)
            params_dir.update(
                {
                    "language": display_name,
                    "language_code": lang_code,
                    "category": "get_subtitles",
                    "title": title,
                    "desc": full_desc,
                    "description": full_desc,
                    "icon": poster_url if poster_url else "",
                }
            )
            self.addDir(params_dir)
            added_count += 1
        printDBG("Added %d languages from HTML" % added_count)

    def _getLanguagesViaAPI(self, cItem):
        API_KEY = get_subdl_api()
        if not API_KEY:
            printDBG("Cannot fallback: No API Key")
            return
        sd_id = cItem.get("sd_id", "").replace("sd", "")
        url = "https://api.subdl.com/api/v1/subtitles"
        params = {"api_key": API_KEY, "sd_id": sd_id, "subs_per_page": "100"}
        try:
            resp = self.session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            langs = {}
            for sub in data.get("subtitles", []):
                lang = (sub.get("language") or sub.get("lang") or "").lower()
                if lang:
                    langs[lang] = langs.get(lang, 0) + 1
            for lang_code, count in langs.items():
                title = r"%s \c00FFFF00[ %d ]\c00FFFFFF" % (
                    lang_code.capitalize(),
                    count,
                )
                params_dir = dict(cItem)
                params_dir.update(
                    {
                        "language": lang_code.capitalize(),
                        "language_code": lang_code,
                        "category": "get_subtitles",
                        "title": title,
                    }
                )
                self.addDir(params_dir)
            printDBG("Added %d languages via API fallback" % len(langs))
        except Exception as e:
            printDBG("API Language Fallback failed: %s" % str(e))
            printExc()

    def getSubtitles(self, cItem):
        printDBG("\n=== [SubDL] Fetching subtitles list ===")
        subtitles = self._searchSubtitle(cItem)
        for item in subtitles:
            params = dict(cItem)
            params.update(item)
            self.addSubtitle(params)

    def _searchSubtitle(self, cItem):
        printDBG("\n=== [SubDL] _searchSubtitle ===")
        lang_code = (cItem.get("language_code") or "").lower()
        outList = []
        html = getattr(self, "_cached_html", None)

        def get_quality_weight(q_str):
            if not q_str:
                return 99
            q = q_str.lower()
            if "bluray" in q or "bdrip" in q or "remux" in q:
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
            return 99

        def color_season_episode(text):
            if not text:
                return text
            COLOR_SE = C
            RESET = W
            text = re.sub(
                r"(?i)\bS\s*0*(\d+)\s*E\s*0*(\d+)\b",
                lambda m: COLOR_SE
                + "S%02dE%02d" % (int(m.group(1)), int(m.group(2)))
                + RESET,
                text,
            )
            text = re.sub(
                r"(?i)\bseason\s*0*(\d+)\b",
                lambda m: COLOR_SE + m.group(0) + RESET,
                text,
            )
            text = re.sub(
                r"(?i)\bepisode\s*0*(\d+)\b",
                lambda m: COLOR_SE + m.group(0) + RESET,
                text,
            )
            text = re.sub(
                r"(?i)\bS0*(\d+)\b",
                lambda m: COLOR_SE + "S%02d" % int(m.group(1)) + RESET,
                text,
            )
            text = re.sub(
                r"(?i)\bE0*(\d+)\b",
                lambda m: COLOR_SE + "E%02d" % int(m.group(1)) + RESET,
                text,
            )
            return text

        video_title = self.params.get("confirmed_title", "") or ""
        wanted_ep = ""
        ep_match = re.search(r"(?i)\bS(\d{1,2})\s*E(\d{1,2})\b", video_title)
        if ep_match:
            wanted_ep = "S%02dE%02d" % (int(ep_match.group(1)), int(ep_match.group(2)))
            printDBG("Current episode: %s" % wanted_ep)

        def is_episode_match(item):
            if not wanted_ep:
                return False
            title_raw = item.get("title", "")
            clean_title = re.sub(r"\\c[0-9A-Fa-f]{6,8}", "", title_raw)
            clean_title = re.sub(r"\x1b\[[0-9;]*m", "", clean_title)  # ANSI codes
            clean_upper = clean_title.upper()
            if wanted_ep.upper() in clean_upper:
                return True
            season_only = wanted_ep[:3].upper()  # "S01"
            if season_only in clean_upper:
                other_eps = re.findall(r"S01E(\d+)", clean_upper)
                if not other_eps:
                    return True
                elif wanted_ep[4:].lstrip("E") in other_eps:
                    return True
            return False

        cached_url = getattr(self, "_cached_url", "")
        expected_slug = cItem.get("season_slug", "")
        if not html or (expected_slug and expected_slug not in cached_url):
            printDBG("Cache miss, fetching fresh HTML...")
            sd_id = cItem.get("sd_id")
            slug = cItem.get("slug")
            if expected_slug:
                fetch_url = "https://subdl.com/subtitle/%s/%s/%s" % (
                    sd_id,
                    slug,
                    expected_slug,
                )
            else:
                fetch_url = "https://subdl.com/subtitle/%s/%s" % (sd_id, slug)
            try:
                resp = self.session.get(fetch_url, timeout=30)
                resp.raise_for_status()
                html = resp.text
                self._cached_html = html
                self._cached_url = fetch_url
            except Exception as e:
                printDBG("Failed to fetch HTML: %s" % str(e))
                html = None
        if html:
            try:
                printDBG("Parsing subtitles from HTML for [%s]" % lang_code)
                lang_section_pattern = (
                    r'data-language="%s"[^>]*>(.*?)(?=data-language="|<div class="mt-4 flex select-none flex-col" data-ai-language|$)'
                    % re.escape(lang_code)
                )
                section_match = re.search(
                    lang_section_pattern, html, re.DOTALL | re.IGNORECASE
                )
                if section_match:
                    section_html = section_match.group(1)
                    row_blocks = re.findall(
                        r'<li[^>]*data-row[^>]*data-id="(\d+)"[^>]*>(.*?)</li>',
                        section_html,
                        re.DOTALL | re.IGNORECASE,
                    )
                    printDBG(
                        "Found %d raw row blocks for [%s]"
                        % (len(row_blocks), lang_code)
                    )
                    for sub_id, block_html in row_blocks:
                        title_match = re.search(
                            r"<h4>(.*?)</h4>", block_html, re.DOTALL
                        )
                        clean_title = (
                            title_match.group(1).strip() if title_match else "Unknown"
                        )
                        author = ""
                        author_match = re.search(r'href="/u/([^"]+)"', block_html)
                        if author_match:
                            author = author_match.group(1).strip()
                        download_url = ""
                        dl_match = re.search(
                            r'href="(https://dl\.subdl\.com/subtitle/[^"]+)"',
                            block_html,
                        )
                        if dl_match:
                            download_url = dl_match.group(1)
                        if not download_url:
                            continue
                        quality = "Other"
                        q_patterns = r"(BluRay|WEB-DL|WEBDL|HDTV|HDRip|DVDRip|BDRip|TVRip|CAM|WEBRip|REMUX)"
                        q_match = re.search(q_patterns, clean_title, re.IGNORECASE)
                        if q_match:
                            quality = q_match.group(1)
                            q_lower = quality.lower()
                            if q_lower == "webdl":
                                quality = "WEB-DL"
                            elif q_lower == "bluray":
                                quality = "BluRay"
                            elif q_lower == "remux":
                                quality = "REMUX"
                        colored_quality = Y + quality + W if quality != "Other" else ""
                        colored_author = Y + "(%s)" % author + W if author else ""
                        colored_title = color_season_episode(clean_title)
                        display_parts = [lang_code.upper()]
                        if colored_quality:
                            display_parts.append(colored_quality)
                        display_parts.append(colored_title)
                        if colored_author:
                            display_parts.append(colored_author)
                        title = " | ".join([x for x in display_parts if x])
                        params_sub = dict(cItem)
                        params_sub.update(
                            {
                                "title": title,
                                "url": download_url,
                                "subtitle_id": sub_id,
                                "lang": lang_code,
                                "category": "get_download",
                                "quality": quality,
                            }
                        )
                        outList.append(params_sub)
                    printDBG(
                        "Found %d subtitles via HTML for [%s]"
                        % (len(outList), lang_code)
                    )
                else:
                    printDBG("Language section not found in HTML for [%s]" % lang_code)
            except Exception as e:
                printDBG("HTML subtitle parsing failed: %s" % str(e))
                printExc()
                outList = []
        if not outList:
            printDBG("Falling back to API for subtitles")
            API_KEY = get_subdl_api()
            if not API_KEY:
                return []
            sd_id = cItem.get("sd_id", "").replace("sd", "")
            url = "https://api.subdl.com/api/v1/subtitles"
            params = {
                "api_key": API_KEY,
                "sd_id": sd_id,
                "lang": lang_code,
                "subs_per_page": "50",
            }
            season_slug = cItem.get("season_slug", "")
            if season_slug and season_slug != "first-season":
                s_match = re.search(r"(\d+)", season_slug)
                if s_match:
                    params["season"] = s_match.group(1)
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("subtitles", []):
                    item_lang = (item.get("language") or "").lower()
                    if item_lang != lang_code:
                        continue
                    sub_id = str(item.get("id", ""))
                    raw_title = (
                        item.get("release_name") or item.get("name") or lang_code
                    )
                    link = item.get("link", "")
                    download_url = (
                        "https://dl.subdl.com/subtitle/%s" % link if link else ""
                    )
                    quality = "Other"
                    q_match = re.search(
                        r"(BluRay|WEB-DL|WEBDL|HDTV|HDRip|DVDRip|BDRip|TVRip|CAM|WEBRip|REMUX)",
                        raw_title,
                        re.IGNORECASE,
                    )
                    if q_match:
                        quality = q_match.group(1)
                    colored_quality = Y + quality + W if quality != "Other" else ""
                    display_parts = [lang_code.upper()]
                    if colored_quality:
                        display_parts.append(colored_quality)
                    display_parts.append(raw_title)
                    title = " | ".join([x for x in display_parts if x])
                    params_sub = dict(cItem)
                    params_sub.update(
                        {
                            "title": title,
                            "subtitle_id": sub_id,
                            "url": download_url,
                            "lang": lang_code,
                            "category": "get_download",
                            "quality": quality,
                        }
                    )
                    outList.append(params_sub)
                printDBG("Found %d subtitles via API fallback" % len(outList))
            except Exception as e:
                printDBG("API subtitle fallback failed: %s" % str(e))
                printExc()
        if wanted_ep:
            printDBG("Prioritizing subtitles for episode: %s" % wanted_ep)
            outList.sort(
                key=lambda x: (
                    0 if is_episode_match(x) else 1,
                    get_quality_weight(x.get("quality", "other")),
                    -int(x.get("downloads", 0)),
                )
            )
            match_count = 0
            for item in outList:
                if is_episode_match(item):
                    item["title"] = r"\c0030FF30✅ \c00FFFFFF" + item["title"]
                    match_count += 1
            printDBG("  Found %d matching subtitles for %s" % (match_count, wanted_ep))
        else:
            outList.sort(key=lambda x: get_quality_weight(x.get("quality", "other")))
        return outList

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
            printDBG("No valid download reference")
            return {}
        fileName = "%s-[SubDL].zip" % title
        filePath = os.path.join(GetSubtitlesDir(), fileName)
        printDBG("Downloading: %s" % download_url)
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
                printDBG("HTTP ERROR: %s" % response.status_code)
                return {}
            with open(filePath, "wb") as f:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            printDBG("Download complete: %s" % filePath)
            extracted_path = None
            subtitles_dir = GetSubtitlesDir()
            video_title = self.params.get("confirmed_title", "") or cItem.get(
                "title", ""
            )
            printDBG("Raw video title: %s" % video_title)
            wanted_episode = ""
            patterns = [
                # الأنماط القياسية
                r"(?i)\bS(\d{1,2})\s*E(\d{1,2})\b",
                r"(?i)\bS(\d{1,2})\s*-\s*E(\d{1,2})\b",
                r"(?i)\bS(\d{1,2})\s+E(\d{1,2})\b",
                r"(?i)\bS(\d{1,2})\s*EP(\d{1,2})\b",
                r"(?i)\b(\d{1,2})x(\d{1,2})\b",
                # الفرنسية: Saison 3 - Episode 4
                r"(?i)saison\s*(\d{1,2})\s*[-–]?\s*episode\s*(\d{1,2})",
                r"(?i)saison\s*(\d{1,2})\s+ep(?:isode)?\.?\s*(\d{1,2})",
                # الألمانية: Staffel 3 - Folge 4
                r"(?i)staffel\s*(\d{1,2})\s*[-–]?\s*(?:folge|episode)\s*(\d{1,2})",
                # الإسبانية: Temporada 3 - Episodio 4
                r"(?i)temporada\s*(\d{1,2})\s*[-–]?\s*episodio\s*(\d{1,2})",
                # الإيطالية: Stagione 3 - Episodio 4
                r"(?i)stagione\s*(\d{1,2})\s*[-–]?\s*episodio\s*(\d{1,2})",
                # البرتغالية: Temporada 3 - Episódio 4
                r"(?i)temporada\s*(\d{1,2})\s*[-–]?\s*epis[oó]dio\s*(\d{1,2})",
                # التركية: Sezon 3 - Bölüm 4
                r"(?i)sezon\s*(\d{1,2})\s*[-–]?\s*b[oö]l[uü]m\s*(\d{1,2})",
                # أنماط عامة إضافية
                r"(?i)season\s*(\d{1,2}).*?episode\s*(\d{1,2})",
                r"(?i)series\s*(\d{1,2}).*?episode\s*(\d{1,2})",
            ]
            for pattern in patterns:
                match = re.search(pattern, video_title)
                if match:
                    season_num = int(match.group(1))
                    episode_num = int(match.group(2))
                    wanted_episode = "S%02dE%02d" % (season_num, episode_num)
                    printDBG(
                        "Extracted season/episode: %s using pattern: %s"
                        % (wanted_episode, pattern)
                    )
                    break
            printDBG("Wanted episode: %s" % wanted_episode)
            with open(filePath, "rb") as f:
                header = f.read(8)
            is_zip = header.startswith(b"PK")
            is_rar = header.startswith(b"Rar!")
            archive_list = []
            if is_zip:
                printDBG("ZIP archive detected")
                with zipfile.ZipFile(filePath, "r") as zip_ref:
                    archive_list = [
                        x
                        for x in zip_ref.namelist()
                        if x.lower().endswith((".srt", ".ass", ".ssa", ".sub", ".txt"))
                    ]
                    selected_file = None
                    if wanted_episode:
                        for item in archive_list:
                            upper_name = item.upper()
                            if wanted_episode in upper_name:
                                selected_file = item
                                printDBG("Matched subtitle: %s" % item)
                                break
                    if not selected_file and archive_list:
                        selected_file = archive_list[0]
                        printDBG("Using first subtitle: %s" % selected_file)
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
            elif is_rar:
                printDBG("RAR archive detected")
                rar_extract_dir = os.path.join(subtitles_dir, "rar_extract_tmp")
                if not os.path.exists(rar_extract_dir):
                    os.mkdir(rar_extract_dir)
                cmd = 'unrar e -o+ "%s" "%s/"' % (filePath, rar_extract_dir)
                printDBG("Running: %s" % cmd)
                os.system(cmd)
                archive_list = []
                for fname in os.listdir(rar_extract_dir):
                    lower = fname.lower()
                    if lower.endswith((".srt", ".ass", ".ssa", ".sub", ".txt")):
                        archive_list.append(fname)
                selected_file = None
                if wanted_episode:
                    for item in archive_list:
                        upper_name = item.upper()
                        if wanted_episode in upper_name:
                            selected_file = item
                            printDBG("Matched subtitle: %s" % item)
                            break
                if not selected_file and archive_list:
                    selected_file = archive_list[0]
                    printDBG("Using first subtitle: %s" % selected_file)
                if selected_file:
                    src_path = os.path.join(rar_extract_dir, selected_file)
                    final_filename = RemoveDisallowedFilenameChars(
                        os.path.basename(selected_file)
                    )
                    extracted_path = os.path.join(subtitles_dir, final_filename)
                    if os.path.exists(extracted_path):
                        os.remove(extracted_path)
                    os.rename(src_path, extracted_path)
                try:
                    for f in os.listdir(rar_extract_dir):
                        os.remove(os.path.join(rar_extract_dir, f))
                    os.rmdir(rar_extract_dir)
                except Exception:
                    pass
            else:
                printDBG("Unknown archive type")
                printDBG("Invalid header sample: %s" % repr(header))
            if extracted_path and os.path.exists(extracted_path):
                self.convert_to_utf8(extracted_path)
            if os.path.exists(filePath):
                os.remove(filePath)
            if extracted_path and os.path.exists(extracted_path):
                return {"title": title, "path": extracted_path, "lang": lang}
            return {"title": title, "path": filePath, "lang": lang}
        except Exception as e:
            printDBG("Download error: %s" % str(e))
            printExc()
            if os.path.exists(filePath):
                os.remove(filePath)
            return {}

    def extractSeasonEpisode(self, video_title):
        if not video_title:
            return ""
        printDBG("Raw video title: %s" % video_title)
        patterns = [
            r"(?i)\bS\s*0*(\d{1,2})\s*E\s*0*(\d{1,2})\b",
            r"(?i)\bS\s*0*(\d{1,2})\s*[- ]+\s*E\s*0*(\d{1,2})\b",
            r"(?i)\bS\s*0*(\d{1,2})\s*EP\s*0*(\d{1,2})\b",
            r"(?i)\b(\d{1,2})x(\d{1,2})\b",
            r"(?i)season\s*(\d{1,2}).*?episode\s*(\d{1,2})",
            r"(?i)staffel\s*(\d{1,2}).*?(?:episode|episoden|folge)\s*(\d{1,2})",
            r"(?i)saison\s*(\d{1,2}).*?episode\s*(\d{1,2})",
            r"(?i)stagione\s*(\d{1,2}).*?episodio\s*(\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, video_title)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
                result = "S%02dE%02d" % (season, episode)
                printDBG(
                    "Extracted season/episode: %s using pattern: %s" % (result, pattern)
                )
                return result
        printDBG("Could not detect season/episode")
        return ""

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
                printDBG("No title or imdb_id provided for search")
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
