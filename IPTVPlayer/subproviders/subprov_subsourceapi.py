# -*- coding: utf-8 -*-
#########################################################
# Subsource.net API subtitle provider for e2iplayer
# Compatible with Python 2 and 3
# Created By : popking (odem2014)
# Last modified: 23/05/2026 - Mohamed Elsafty (angel_heart)
#########################################################
import os
import zipfile
import requests
import re
from Components.config import config, ConfigText, ConfigSubsection
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import (
    TranslateTXT as _,
    SetIPTVPlayerLastHostError,
)
from Plugins.Extensions.IPTVPlayer.components.isubprovider import (
    CSubProviderBase,
    CBaseSubProviderClass,
)
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    RemoveDisallowedFilenameChars,
    GetSubtitlesDir,
)

#########################################################
# CONFIGURATION (uses existing key)
#########################################################
if not hasattr(config.plugins, "iptvplayer"):
    config.plugins.iptvplayer = ConfigSubsection()

# use the existing SubSource API key variable
if not hasattr(config.plugins.iptvplayer, "subsourceapi"):
    config.plugins.iptvplayer.subsourceapi = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    return optionList


def GetLanguageTab():
    """
    Complete language list from Subsource.net upload page
    Format: [Display Name, ISO 639-1 code, ISO 639-2/3 code]
    API search expects lowercase language names (e.g., "english" not "English")
    """
    tab = [
        # A
        ["Abkhazian", "ab", "abk"],
        ["Afrikaans", "af", "afr"],
        ["Albanian", "sq", "alb"],
        ["Amharic", "am", "amh"],
        ["Arabic", "ar", "ara"],
        ["Aragonese", "an", "arg"],
        ["Armenian", "hy", "arm"],
        ["Assamese", "as", "asm"],
        ["Asturian", "", "ast"],
        ["Azerbaijani", "az", "aze"],
        # B
        ["Basque", "eu", "baq"],
        ["Belarusian", "be", "bel"],
        ["Bengali", "bn", "ben"],
        ["Bosnian", "bs", "bos"],
        ["BosnianLatin", "bs", "bos"],
        ["Breton", "br", "bre"],
        ["Brazilian", "pt", "pob"],  # Brazilian Portuguese
        ["Bulgarian", "bg", "bul"],
        ["Burmese", "my", "bur"],
        # C
        ["Catalan", "ca", "cat"],
        ["Chinese", "zh", "chi"],
        ["Chinese (Cantonese)", "zh", "yue"],
        ["Chinese (Simplified)", "zh", "zhs"],
        ["Chinese (Traditional)", "zh", "zht"],
        ["Chinese Bilingual", "zh", "chi"],
        ["Croatian", "hr", "hrv"],
        ["Czech", "cs", "cze"],
        # D
        ["Danish", "da", "dan"],
        ["Dari", "", "dar"],
        ["Dutch", "nl", "dut"],
        # E
        ["English", "en", "eng"],
        ["Esperanto", "eo", "epo"],  # Fixed: Espranto → Esperanto
        ["Estonian", "et", "est"],
        ["Extremaduran", "", "ext"],
        # F
        ["Farsi/Persian", "fa", "per"],
        ["Filipino", "fil", "fil"],
        ["Finnish", "fi", "fin"],
        ["French", "fr", "fre"],
        ["French (Canada)", "fr", "fre"],
        ["French (France)", "fr", "fre"],
        # G
        ["Gaelic", "gd", "gla"],
        ["Galician", "gl", "glg"],  # Fixed: Gaelician → Galician
        ["Georgian", "ka", "geo"],
        ["German", "de", "ger"],
        ["Greek", "el", "ell"],
        ["Greenlandic", "kl", "kal"],
        # H
        ["Hebrew", "he", "heb"],
        ["Hindi", "hi", "hin"],
        ["Hungarian", "hu", "hun"],
        # I
        ["Icelandic", "is", "ice"],
        ["Igbo", "ig", "ibo"],
        ["Indonesian", "id", "ind"],
        ["Interlingua", "ia", "ina"],
        ["Irish", "ga", "gle"],
        ["Italian", "it", "ita"],
        # J
        ["Japanese", "ja", "jpn"],
        # K
        ["Kannada", "kn", "kan"],
        ["Kazakh", "kk", "kaz"],
        ["Khmer", "km", "khm"],
        ["Korean", "ko", "kor"],
        ["Kurdish", "ku", "kur"],
        ["Kyrgyz", "ky", "kir"],
        # L
        ["Latvian", "lv", "lav"],
        ["Lithuanian", "lt", "lit"],
        ["Luxembourgish", "lb", "ltz"],
        # M
        ["Macedonian", "mk", "mac"],
        ["Malay", "ms", "may"],
        ["Malayalam", "ml", "mal"],
        ["Manipuri", "mni", "mni"],
        ["Marathi", "mr", "mar"],
        ["Mongolian", "mn", "mon"],
        ["Montenegrin", "", "cnr"],
        # N
        ["Navajo", "nv", "nav"],
        ["Nepali", "ne", "nep"],
        ["Northern Sami", "se", "sme"],  # Fixed: Northen → Northern
        ["Norwegian", "no", "nor"],
        # O
        ["Occitan", "oc", "oci"],
        ["Odia", "or", "ori"],
        # P
        ["Pashto", "ps", "pus"],
        ["Polish", "pl", "pol"],
        ["Portuguese", "pt", "por"],
        # R
        ["Romanian", "ro", "rum"],
        ["Russian", "ru", "rus"],
        # S
        ["Santali", "sat", "sat"],  # Fixed: Santli → Santali
        ["Serbian", "sr", "scc"],
        ["Sindhi", "sd", "snd"],
        ["Sinhala", "si", "sin"],  # Kept one: Sinhala/Sinhalese merged
        ["Slovak", "sk", "slo"],
        ["Slovenian", "sl", "slv"],
        ["Somali", "so", "som"],
        ["Sorbian", "", "wen"],
        ["Spanish", "es", "spa"],
        ["Spanish (Latin America)", "es", "spa"],
        ["Spanish (Spain)", "es", "spa"],
        ["Swahili", "sw", "swa"],
        ["Swedish", "sv", "swe"],
        ["Sylheti", "", "syl"],
        ["Syriac", "syr", "syr"],
        # T
        ["Tagalog", "tl", "tgl"],
        ["Tamil", "ta", "tam"],
        ["Tatar", "tt", "tat"],
        ["Telugu", "te", "tel"],
        ["Tetum", "tet", "tet"],
        ["Thai", "th", "tha"],
        ["Toki Pona", "", "tok"],
        ["Turkish", "tr", "tur"],
        ["Turkmen", "tk", "tuk"],
        # U
        ["Ukrainian", "uk", "ukr"],
        ["Urdu", "ur", "urd"],
        ["Uzbek", "uz", "uzb"],
        # V
        ["Vietnamese", "vi", "vie"],
        # W
        ["Welsh", "cy", "wel"],
    ]
    return tab


def get_subsource_api():
    """Return SubSource API key"""
    try:
        return config.plugins.iptvplayer.subsourceapi.value.strip()
    except Exception:
        printExc()
        return ""


#########################################################
# BASE SETTINGS
#########################################################
BASE_URL = "https://api.subsource.net/api/v1"


def build_headers():
    """Return default API headers with X-API-Key"""
    return {"X-API-Key": get_subsource_api()}


#########################################################
# PROVIDER IMPLEMENTATION
#########################################################


class SubsourceAPIProvider(CBaseSubProviderClass):
    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.session = requests.Session()
        self.session.headers.update(build_headers())
        self.defaultParams = {"header": self.session.headers}
        self.dInfo = params.get("discover_info", {})
        self.currList = []

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("SubsourceAPIProvider.getMoviesTitles")
        sts, tab = self.imdbGetMoviesByTitle(self.params["confirmed_title"])
        if not sts:
            return
        printDBG(tab)
        for item in tab:
            params = dict(cItem)
            params.update(item)  # item = {'title', 'imdbid'}
            params.update({"category": nextCategory})
            self.addDir(params)

    def getMovieID(self, cItem):
        printDBG("SubsourceAPIProvider.getMovieID (Integrated Smart Search)")
        raw_title = cItem.get("base_title", cItem.get("title", ""))

        text = re.sub(r"\\[cCpPbBuU][0-9A-Fa-f]{0,8}", "", raw_title)
        text = re.sub(r"[cC][0-9A-Fa-f]{6}", "", text)
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        extracted_year = year_match.group() if year_match else ""
        for sep in ["|", "-", ":", "(", "["]:
            if sep in text:
                text = text.split(sep)[0]
        text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
        words = text.split()
        clean_title = " ".join(words[:5]).strip()
        search_year = cItem.get("year", "") or extracted_year
        if not clean_title:
            return []
        API_KEY = get_subsource_api()
        headers = {
            "X-API-Key": API_KEY,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTVPlayer",
        }
        url = "https://api.subsource.net/api/v1/movies/search"

        def perform_search(query, year=None):
            p = {"searchType": "text", "q": query, "type": "all"}
            if year:
                p["year"] = year
            try:
                printDBG("Requesting: q=[%s] year=[%s]" % (query, year or "None"))
                res = requests.get(url, params=p, headers=headers, timeout=15)
                res.raise_for_status()
                return res.json()
            except Exception:
                return None

        response_json = perform_search(clean_title, search_year)
        if not (
            response_json and response_json.get("success") and response_json.get("data")
        ):
            printDBG("No results with year, trying title only...")
            response_json = perform_search(clean_title)
        if not (
            response_json and response_json.get("success") and response_json.get("data")
        ):
            short_title = " ".join(words[:3]).strip()
            if short_title != clean_title:
                printDBG(
                    "Still no results, trying ultra-short title: [%s]" % short_title
                )
                response_json = perform_search(short_title)
        if response_json and response_json.get("success") and response_json.get("data"):
            for item in response_json["data"]:
                movie_id = item.get("movieId")
                title = item.get("title", "")
                release_year = item.get("releaseYear", "")
                sub_count = item.get("subtitleCount", 0)
                display_title = "%s (%s) [%s subs]" % (title, release_year, sub_count)
                params = dict(cItem)
                params.update(item)
                params.update(
                    {
                        "title": display_title,
                        "movieId": movie_id,
                        "category": "get_languages",
                    }
                )
                self.addDir(params)

    def getLanguages(self, cItem):
        printDBG("\n=== [STEP 4] getLanguages - Filtered ===")
        movie_id = cItem.get("movieId") or cItem.get("movie_id")
        if not movie_id:
            printDBG("❌ No movieId to fetch languages")
            return
        __api = "https://api.subsource.net/api/v1"
        __getSub = __api + "/subtitles"
        API_KEY = get_subsource_api()
        headers = {"X-API-Key": API_KEY}
        params_all = {
            "movieId": movie_id,
            "language": "",
            "limit": 500,
            "sort": "newest",
        }
        available_langs = {}
        try:
            response = requests.get(
                __getSub, params=params_all, headers=headers, timeout=30
            )
            response.raise_for_status()
            json_data = response.json()
            if json_data.get("success") and json_data.get("data"):
                for item in json_data["data"]:
                    lang_name = item.get("language", "")
                    if lang_name:
                        available_langs[lang_name.lower()] = lang_name
                printDBG("Found %d unique languages" % len(available_langs))
        except Exception as e:
            printDBG("Could not fetch languages: %s" % str(e))
            available_langs = None
        langs = GetLanguageTab()
        added_count = 0
        for lang in langs:
            lang_display = lang[0]
            lang_code = lang[1]
            if available_langs is not None:
                if lang_display.lower() not in available_langs:
                    continue
            params = dict(cItem)
            params.update(
                {
                    "language": lang_display,
                    "lang": lang_code,
                    "category": "get_subtitles",
                    "title": lang_display,
                }
            )
            self.addDir(params)
            added_count += 1
        printDBG("Added %d languages to menu" % added_count)

    def getSubtitles(self, cItem):
        printDBG("\n=== [STEP 5] getSubtitles ===")
        list = self._searchSubtitle(cItem)
        for item in list:
            params = dict(cItem)
            params.update(item)
            self.addSubtitle(params)

    def _searchSubtitle(self, cItem):
        printDBG("\n=== [STEP 6] _searchSubtitle ===")
        __api = "https://api.subsource.net/api/v1"
        __getSub = __api + "/subtitles"
        API_KEY = get_subsource_api()
        headers = {"X-API-Key": API_KEY}
        lang_display = cItem.get("language", "English")
        sublanguageid = lang_display.lower()
        movie_id = cItem.get("movieId") or cItem.get("movie_id")
        limit = 100
        params2 = {
            "movieId": movie_id,
            "language": sublanguageid,
            "limit": limit,
            "sort": "newest",
        }
        printDBG(
            "Searching subtitles: movieId=%s, language_api=%s"
            % (movie_id, sublanguageid)
        )
        try:
            response2 = requests.get(
                __getSub, params=params2, headers=headers, timeout=30
            )
            response2.raise_for_status()
            json_data2 = response2.json()
            if not json_data2.get("success") or not json_data2.get("data"):
                printDBG("❌ No subtitles found for language: %s" % sublanguageid)
                return []

            outList = []
            for item in json_data2["data"]:
                sub_id = item.get("subtitleId")
                language = item.get("language", "")
                uploader = ""
                if item.get("contributors"):
                    uploader = item["contributors"][0].get("displayname", "")
                release_infos = item.get("releaseInfo", [])
                commentary = item.get("commentary", "")
                downloads = item.get("downloads", 0)

                for rel in release_infos:
                    params = dict(cItem)
                    params.update(
                        {
                            "title": "%s | %s | %s"
                            % (language.capitalize(), uploader, rel),
                            "subtitleId": sub_id,
                            "lang": language,
                            "category": "get_download",
                            "commentary": commentary,
                            "downloads": downloads,
                        }
                    )
                    outList.append(params)
            printDBG("Found %d subtitle items" % len(outList))

            return outList

        except Exception as e:
            printDBG("❌ Error fetching subtitles: %s" % str(e))
            printExc()
            return []

    def downloadSubtitleFile(self, cItem):
        printDBG("\n=== [STEP 7] downloadSubtitleFile ===")
        sub_id = cItem.get("subtitleId")
        lang = cItem.get("lang", "en")
        title = RemoveDisallowedFilenameChars(cItem.get("title", "subtitle"))
        API_KEY = get_subsource_api()
        headers = {"X-API-Key": API_KEY}
        __api = "https://api.subsource.net/api/v1"
        __getSub = __api + "/subtitles"
        __getSubdown = __getSub + "/" + str(sub_id) + "/download"
        fileName = "%s-[SubSource].zip" % title
        filePath = os.path.join(GetSubtitlesDir(), fileName)
        printDBG("Downloading subtitle to %s" % filePath)
        try:
            response = requests.get(
                __getSubdown,
                headers=headers,
                verify=False,
                allow_redirects=True,
                timeout=60,
                stream=True,
            )  # NOSONAR
            response.raise_for_status()
            with open(filePath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            printDBG("Download complete: %s" % filePath)
            extracted_path = None
            video_title = (
                self.dInfo.get('season_episode', '') or
                self.dInfo.get('episode_title', '') or
                self.dInfo.get('title', '') or
                self.params.get('confirmed_title', '') or
                cItem.get('title', '')
            )
            printDBG("🎬 video_title = %s" % video_title)
            wanted_episode = ''
            episode_match = re.search(
                r'(S\d+E\d+)',
                video_title,
                re.IGNORECASE
            )
            if episode_match:
                wanted_episode = episode_match.group(1).upper()
            else:
                season_episode = re.search(
                    r'(?:Season|Staffel|Saison|Series)\s*(\d+).*?(?:Episode|Episoden|Ep)\s*(\d+)',
                    video_title,
                    re.IGNORECASE
                )
                if season_episode:
                    season_num = int(season_episode.group(1))
                    episode_num = int(season_episode.group(2))
                    wanted_episode = "S%02dE%02d" % (season_num, episode_num)
            printDBG("Wanted episode: %s" % wanted_episode)
            with zipfile.ZipFile(filePath, 'r') as zip_ref:
                zip_list = [x for x in zip_ref.namelist()
                            if x.lower().endswith(('.srt', '.ass', '.ssa', '.sub'))]
                selected_file = None
                if wanted_episode:
                    for item in zip_list:
                        if wanted_episode in item.upper():
                            selected_file = item
                            printDBG("Matched episode subtitle: %s" % item)
                            break
                if not selected_file and zip_list:
                    selected_file = zip_list[0]
                    printDBG("⚠️ No exact episode match, using first subtitle: %s" % selected_file)
                if selected_file:
                    zip_ref.extract(selected_file, GetSubtitlesDir())
                    src_path = os.path.join(GetSubtitlesDir(), *selected_file.split('/'))
                    clean_name = RemoveDisallowedFilenameChars(
                        os.path.basename(selected_file)
                    )
                    extracted_path = os.path.join(GetSubtitlesDir(), clean_name)
                    if src_path != extracted_path:
                        os.rename(src_path, extracted_path)
            if extracted_path:
                retData = {"title": title, "path": extracted_path, "lang": lang}
                printDBG("Extracted subtitle: %s" % extracted_path)
            else:
                retData = {"title": title, "path": filePath, "lang": lang}

            return retData

        except Exception as e:
            printDBG("❌ Error downloading subtitle: %s" % str(e))
            printExc()
            SetIPTVPlayerLastHostError(_("Failed to download subtitle."))
            return {}

    def handleService(self, index, refresh=0):
        printDBG("handleService start")

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

        # === MAIN MENU ===
        if name is None:
            API_KEY = config.plugins.iptvplayer.subsourceapi.value
            if API_KEY != "":
                search_title = self.params.get("confirmed_title", "")
                search_year = self.params.get("year", "")
                if search_title:
                    fake_item = {
                        "name": "search_start",
                        "base_title": search_title,
                        "year": search_year,
                        "category": "get_movieid",
                    }
                    self.getMovieID(fake_item)
                else:
                    printDBG("No title provided for search")
            else:
                printDBG("No API key configured")
        elif category == "get_movieid":
            self.getMovieID(self.currItem)
        elif category == "get_languages":
            self.getLanguages(self.currItem)
        elif category == "get_subtitles":
            self.getSubtitles(self.currItem)
        elif category == "get_download":
            self.downloadSubtitleFile(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


#########################################################
# ENTRY POINT FOR E2IPLAYER
#########################################################


class IPTVSubProvider(CSubProviderBase):
    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubsourceAPIProvider(params))
