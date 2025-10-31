# -*- coding: utf-8 -*-
#########################################################
# Subsource.net API subtitle provider for e2iplayer
# Compatible with Python 2 and 3
# Created By : popking (odem2014)
# Last modified: 31/10/2025 - popking (odem2014)
#########################################################
import os
import zipfile
import requests
from Components.config import config, ConfigText, ConfigSubsection
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, RemoveDisallowedFilenameChars, GetSubtitlesDir

#########################################################
# CONFIGURATION (uses existing key)
#########################################################
if not hasattr(config.plugins, 'iptvplayer'):
    config.plugins.iptvplayer = ConfigSubsection()

# use the existing SubSource API key variable
if not hasattr(config.plugins.iptvplayer, 'subsourceapi'):
    config.plugins.iptvplayer.subsourceapi = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    return optionList


def GetLanguageTab():
    tab = [
        ["Albanian", "sq", "alb"],
        ["Arabic", "ar", "ara"],
        ["Belarusian", "hy", "arm"],
        ["Bosnian", "bs", "bos"],
        ["BosnianLatin", "bs", "bos"],
        ["Bulgarian", "bg", "bul"],
        ["Brazilian", "pb", "pob"],
        ["Catalan", "ca", "cat"],
        ["Chinese", "zh", "chi"],
        ["Croatian", "hr", "hrv"],
        ["Czech", "cs", "cze"],
        ["Danish", "da", "dan"],
        ["Dutch", "nl", "dut"],
        ["English", "en", "eng"],
        ["Espanol", "es", "spa"],
        ["Estonian", "et", "est"],
        ["Persian", "fa", "per"],
        ["Farsi", "fa", "per"],
        ["Finnish", "fi", "fin"],
        ["French", "fr", "fre"],
        ["German", "de", "ger"],
        ["Greek", "el", "ell"],
        ["Hebrew", "he", "heb"],
        ["Hindi", "hi", "hin"],
        ["Hungarian", "hu", "hun"],
        ["Icelandic", "is", "ice"],
        ["Indonesian", "id", "ind"],
        ["Italian", "it", "ita"],
        ["Japanese", "ja", "jpn"],
        ["Korean", "ko", "kor"],
        ["Latvian", "lv", "lav"],
        ["Lithuanian", "lt", "lit"],
        ["Macedonian", "mk", "mac"],
        ["Malay", "ms", "may"],
        ["Norwegian", "no", "nor"],
        ["Polish", "pl", "pol"],
        ["Portuguese", "pt", "por"],
        ["Romanian", "ro", "rum"],
        ["Russian", "ru", "rus"],
        ["Serbian", "sr", "scc"],
        ["Slovak", "sk", "slo"],
        ["Slovenian", "sl", "slv"],
        ["Spanish", "es", "spa"],
        ["Swedish", "sv", "swe"],
        ["Thai", "th", "tha"],
        ["Turkish", "tr", "tur"],
        ["Ukrainian", "uk", "ukr"],
        ["Vietnamese", "vi", "vie"]
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
    return {
        "X-API-Key": get_subsource_api()
    }

#########################################################
# PROVIDER IMPLEMENTATION
#########################################################


class SubsourceAPIProvider(CBaseSubProviderClass):
    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.session = requests.Session()
        self.session.headers.update(build_headers())
        self.defaultParams = {'header': self.session.headers}
        self.dInfo = params.get('discover_info', {})
        self.currList = []

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("SubsourceAPIProvider.getMoviesTitles")
        sts, tab = self.imdbGetMoviesByTitle(self.params['confirmed_title'])
        if not sts:
            return
        printDBG(tab)
        for item in tab:
            params = dict(cItem)
            params.update(item)  # item = {'title', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)

    def getMovieID(self, cItem):
        printDBG("SubsourceAPIProvider.getMovieID")
        title = cItem['base_title']
        year = cItem['year']
        params1 = {"searchType": "text", "q": title, "year": year, "type": "all"}
        url = "https://api.subsource.net/api/v1/movies/search"
        API_KEY = get_subsource_api()
        headers = {"X-API-Key": API_KEY}
        try:
            response1 = requests.get(url, params=params1, headers=headers)
            response1.raise_for_status()
            response_json = response1.json()
        except Exception as e:
            print(("Error fetching search results:", str(e)))
            return []

        if response_json.get("success") and response_json.get("data"):
            for item in response_json["data"]:
                movie_id = item.get("movieId")
                title = item.get("title", "")
                release_year = item.get("releaseYear", "")
                sub_count = item.get("subtitleCount", 0)
                m_type = item.get("type", "")
                params = dict(cItem)
                params.update(item)
                params.update({'category': 'get_languages'})
                self.addDir(params)

    def getLanguages(self, cItem):
        printDBG("\n=== [STEP 4] getLanguages ===")
        langs = GetLanguageTab()
        for lang in langs:
            params = dict(cItem)
            params.update({
                'language': lang[0].lower(),  # display name
                'lang': lang[1],              # ISO code (used later)
                'category': "get_subtitles",
                'title': lang[0]              # show readable title in UI
            })
            self.addDir(params)

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
        sublanguageid = cItem.get('language', 'en')
        movie_id = cItem.get('movieId') or cItem.get('movie_id')
        limit = 100
        params2 = {
            "movieId": movie_id,
            "language": sublanguageid,
            "limit": limit,
            "sort": "newest"
        }

        try:
            response2 = requests.get(__getSub, params=params2, headers=headers, timeout=30)
            response2.raise_for_status()
            json_data2 = response2.json()

            if not json_data2.get("success") or not json_data2.get("data"):
                printDBG("❌ No subtitles found for this movie")
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
                    params.update({
                        "title": "%s | %s | %s" % (language.capitalize(), uploader, rel),
                        "subtitleId": sub_id,
                        "lang": language,
                        "category": "get_download",
                        "commentary": commentary,
                        "downloads": downloads,
                    })
                    outList.append(params)

            return outList

        except Exception as e:
            printDBG("❌ Error fetching subtitles for movieId %s: %s" % (movie_id, str(e)))
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
            response = requests.get(__getSubdown, headers=headers, verify=False, allow_redirects=True, timeout=60, stream=True)
            response.raise_for_status()

            with open(filePath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            printDBG("✅ Download complete: %s" % filePath)

            # Optionally unzip to .srt (SubSource always gives a single file inside zip)
            extracted_path = None
            with zipfile.ZipFile(filePath, 'r') as zip_ref:
                zip_list = zip_ref.namelist()
                if zip_list:
                    first_file = zip_list[0]
                    extracted_path = os.path.join(GetSubtitlesDir(), RemoveDisallowedFilenameChars(first_file))
                    zip_ref.extract(first_file, GetSubtitlesDir())
                    os.rename(os.path.join(GetSubtitlesDir(), first_file), extracted_path)

            if extracted_path:
                retData = {'title': title, 'path': extracted_path, 'lang': lang}
                printDBG("✅ Extracted subtitle: %s" % extracted_path)
            else:
                retData = {'title': title, 'path': filePath, 'lang': lang}

            return retData

        except Exception as e:
            printDBG("❌ Error downloading subtitle: %s" % str(e))
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if name is None:
            API_KEY = config.plugins.iptvplayer.subsourceapi.value
            if API_KEY != '':
                self.getMoviesTitles({'name': 'category'}, 'get_movieid')
        elif category == 'get_movieid':
            self.getMovieID(self.currItem)
        elif category == 'get_languages':
            self.getLanguages(self.currItem)
        elif category == 'get_subtitles':
            self.getSubtitles(self.currItem)
        elif category == 'get_download':
            self.downloadSubtitleFile(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)

#########################################################
# ENTRY POINT FOR E2IPLAYER
#########################################################


class IPTVSubProvider(CSubProviderBase):
    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubsourceAPIProvider(params))
