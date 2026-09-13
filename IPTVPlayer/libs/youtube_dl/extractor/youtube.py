#!/usr/bin/env python
# -*- coding: utf-8 -*-
import urllib.parse
import re
import time
from urllib.parse import urlparse, urlunparse, unquote as _unquote
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, byteify, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph

from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute_ext, is_js_cached

from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str

# InnerTube ANDROID player client. It hands unthrottled, un-ciphered
# progressive/adaptive URLs to an anonymous caller (verified: no &n=
# throttle param, full CDN speed), so no player-JS / signature / nsig
# work is needed on this path.
#
# Deliberately NOT yt-dlp's current fingerprint (21.x + androidSdkVersion
# 30 + Android 11 + contentCheckOk/racyCheckOk): YouTube challenges that
# exact combo with the "sign in to confirm you're not a bot" wall within
# a handful of requests. These are the older values the plain python3
# host has used for months without ever tripping it - keep them in step
# with origin/python3, do not chase yt-dlp here.
YT_ANDROID_CLIENT_VERSION = "20.32.35"
YT_ANDROID_SDK_VERSION = 35
YT_ANDROID_OS_VERSION = "15"


class CYTSignAlgoExtractor:
    MAX_REC_DEPTH = 5  # MAX RECURSION Depth for security
    RE_FUNCTION_NAMES = re.compile(r"[ =(,]([a-zA-Z$]+?)\([a-z0-9,]*?\)")
    RE_OBJECTS = re.compile(r"[ =(,;]([a-zA-Z$]+?)\.([a-zA-Z$]+?)\(")
    RE_MAIN = re.compile(r"([a-zA-Z0-9$]+)\(")

    def __init__(self, cm):
        self.cm = cm

    def _getAllLocalSubFunNames(self, mainFunBody):
        match = self.RE_FUNCTION_NAMES.findall(mainFunBody)
        if len(match):
            funNameTab = set(match[1:])
            return funNameTab
        return set()

    def _getAllObjectsWithMethods(self, mainFunBody):
        objects = {}
        data = self.RE_OBJECTS.findall(mainFunBody)
        for item in data:
            if item[1] not in ["split", "length", "slice", "join"]:
                if item[0] not in objects:
                    objects[item[0]] = []
                objects[item[0]].append("%s:" % item[1])
        return objects

    def _findMainFunctionName(self):
        data = self.playerData
        patterns = [
            r"\b[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*encodeURIComponent\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r"\b[a-zA-Z0-9]+\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*encodeURIComponent\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r'\b(?P<sig>[a-zA-Z0-9$]{2})\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\)',
            r'(?P<sig>[a-zA-Z0-9$]+)\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\).*a\.join\(\s*""\s*\)',
            # Obsolete patterns
            r'(["\'])signature\1\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(',
            r"\.sig\|\|(?P<sig>[a-zA-Z0-9$]+)\(",
            r"yt\.akamaized\.net/\)\s*\|\|\s*.*?\s*[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*(?:encodeURIComponent\s*\()?\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r"\b[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r"\b[a-zA-Z0-9]+\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r"\bc\s*&&\s*a\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r"\bc\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",
            r"\bc\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",
        ]

        for reg in patterns:
            tmp = re.findall(reg, data)
            for name in tmp:
                if name and not any((c in name) for c in ''', '"'''):
                    printDBG("pattern: " + reg)
                    printDBG("name: " + name)
                    return name.strip()

        return ""

    def _findFunctionByMarker(self, marker):
        data = self.playerData
        idxStart = 0
        while idxStart < len(data):
            idxStart = data.find(marker, idxStart)
            if idxStart > 1:
                if data[idxStart - 1] in (" ", ",", ";", "\n", "\r", "\t"):
                    idxEnd = data.find("}", idxStart)
                    if idxEnd > 0:
                        return data[idxStart: idxEnd + 1]
            else:
                return ""
            idxStart += len(marker)
        return ""

    def _findFunction(self, funcname):
        data = self._findFunctionByMarker("function %s(" % funcname)
        if data:
            return data
        return self._findFunctionByMarker("%s=function(" % funcname)

    def _findObject(self, objname, methods):
        data = self.playerData
        marker = "%s={" % objname
        idxStart = 0
        while idxStart < len(data):
            idxStart = data.find(marker, idxStart)
            if idxStart > 1:
                if data[idxStart - 1] in (" ", ",", ";", "\n", "\r", "\t"):
                    idxEnd = data.find("};", idxStart)
                    if idxEnd > 0:
                        if ph.all(methods, data, idxStart, idxEnd):
                            return data[idxStart: idxEnd + 2]
            else:
                return ""
            idxStart += len(marker)
        return ""

    def decryptSignatures(self, encSignatures, playerUrl):
        decSignatures = []
        code = ""
        jsname = "ytsigndec"
        jshash = "hash7_" + playerUrl.split("://", 1)[-1]
        if not is_js_cached(jsname, jshash):

            # get main function
            sts, self.playerData = self.cm.getPage(playerUrl)
            if not sts:
                return []

            t1 = time.time()
            code = []
            mainFunctionName = self._findMainFunctionName()
            if not mainFunctionName:
                SetIPTVPlayerLastHostError(_("Encryption function name extraction failed!\nPlease report the problem to %s") % "https://github.com/oe-mirrors/e2iplayer/issues")
                return []
            printDBG("mainFunctionName >> %s" % mainFunctionName)

            mainFunction = self._findFunction(mainFunctionName)
            if not mainFunction:
                SetIPTVPlayerLastHostError(_("Encryption function body extraction failed!\nPlease report the problem to %s") % "https://github.com/oe-mirrors/e2iplayer/issues")
                return []
            code.append(mainFunction)

            funNames = self._getAllLocalSubFunNames(mainFunction)
            for funName in funNames:
                fun = self._findFunction(funName)
                code.insert(0, fun)

            objects = self._getAllObjectsWithMethods(mainFunction)
            for objName, methods in objects.items():
                obj = self._findObject(objName, methods)
                code.insert(0, obj)

            code.append("e2i_dec=[];for (var idx in e2i_enc){e2i_dec.push(%s(e2i_enc[idx]));};print(JSON.stringify(e2i_dec));" % mainFunctionName)
            code = "\n".join(code)
            printDBG("---------------------------------------")
            printDBG("|    ALGO FOR SIGNATURE DECRYPTION    |")
            printDBG("---------------------------------------")
            printDBG(code)
            printDBG("---------------------------------------")
        else:
            printDBG("USE ALGO FROM CACHE: %s" % jshash)

        js_params = [{"code": "e2i_enc = %s;" % json_dumps(encSignatures)}]
        js_params.append({"name": jsname, "code": code, "hash": jshash})
        ret = js_execute_ext(js_params)
        if ret["sts"] and 0 == ret["code"]:
            try:
                decSignatures = json_loads(ret["data"])
            except Exception:
                printExc()
        return decSignatures


def reportExtractorError(text):
    # Not an exception. This used to be named ExtractorError, shadowing the
    # real class from youtube_dl.utils, so `raise ExtractorError(...)` raised
    # None -> a spurious TypeError on every deep failure. It only surfaces
    # the message now; callers return an empty result themselves.
    printDBG(text)
    SetIPTVPlayerLastHostError(_(text))


class YoutubeIE(object):
    """Information extractor for youtube.com."""

    _VALID_URL = r"""^
                     (
                         (?:https?://)?                                       # http(s):// (optional)
                         (?:youtu\.be/|(?:\w+\.)?youtube(?:-nocookie)?\.com/|
                            tube\.majestyc\.net/)                             # the various hostnames, with wildcard subdomains
                         (?:.*?\#/)?                                          # handle anchor (#/) redirect urls
                         (?:                                                  # the various things that can precede the ID:
                             (?:(?:v|embed|e)/)                               # v/ or embed/ or e/
                             |(?:                                             # or the v= param in all its forms
                                 (?:watch(?:_popup)?(?:\.php)?)?              # preceding watch(_popup|.php) or nothing (like /?v=xxxx)
                                 (?:\?|\#!?)                                  # the params delimiter ? or # or #!
                                 (?:.*?&)?                                    # any other preceding param (like /?s=tuff&v=xxxx)
                                 v=
                             )
                         )?                                                   # optional -> youtube.com/xxxx is OK
                     )?                                                       # all until now is optional -> you can pass the naked ID
                     ([0-9A-Za-z_-]+)                                         # here is it! the YouTube video ID
                     (?(1).+)?                                                # if we found the ID, everything can follow
                     $"""
    _NEXT_URL_RE = r"[\?&]next_url=([^&]+)"
    # Listed in order of quality
    _available_formats_prefer_free = [
        "38",
        "46",
        "37",
        "45",
        "22",
        "44",
        "35",
        "43",
        "34",
        "18",
        "6",
        "5",
        "36",
        "17",
        "13",
        # Apple HTTP Live Streaming
        "96",
        "95",
        "94",
        "93",
        "92",
        "132",
        "151",
        # 3D
        "85",
        "102",
        "84",
        "101",
        "83",
        "100",
        "82",
        # Dash video
        "138",
        "248",
        "137",
        "247",
        "136",
        "246",
        "245",
        "244",
        "135",
        "243",
        "134",
        "242",
        "133",
        "160",
        "298",
        "299",
        # Dash audio
        "172",
        "141",
        "171",
        "140",
        "139",
    ]

    _video_extensions = {
        "13": "3gp",
        "17": "3gp",
        "18": "mp4",
        "22": "mp4",
        "36": "3gp",
        "37": "mp4",
        "38": "mp4",
        "43": "webm",
        "44": "webm",
        "45": "webm",
        "46": "webm",
        # 3d videos
        "82": "mp4",
        "83": "mp4",
        "84": "mp4",
        "85": "mp4",
        "100": "webm",
        "101": "webm",
        "102": "webm",
        # Apple HTTP Live Streaming
        "92": "mp4",
        "93": "mp4",
        "94": "mp4",
        "95": "mp4",
        "96": "mp4",
        "132": "mp4",
        "151": "mp4",
        # Dash mp4
        "133": "mp4v",
        "134": "mp4v",
        "135": "mp4v",
        "136": "mp4v",
        "137": "mp4v",
        "138": "mp4v",
        "160": "mp4v",
        "298": "mp4v",
        "299": "mp4v",
        # Dash mp4 audio
        "139": "mp4a",
        "140": "mp4a",
        "141": "mp4a",
        # Dash webm
        "171": "webm",
        "172": "webm",
        "242": "webm",
        "243": "webm",
        "244": "webm",
        "245": "webm",
        "246": "webm",
        "247": "webm",
        "248": "webm",
        "271": "webmv",
        "313": "webmv",
        "315": "webmv",
        "mpd": "mpd",
    }
    _video_dimensions = {
        "5": "240x400",
        "6": "???",
        "13": "???",
        "17": "144x176",
        "18": "360x640",
        "22": "720x1280",
        "34": "360x640",
        "35": "480x854",
        "36": "240x320",
        "37": "1080x1920",
        "38": "3072x4096",
        "43": "360x640",
        "44": "480x854",
        "45": "720x1280",
        "46": "1080x1920",
        "82": "360p",
        "83": "480p",
        "84": "720p",
        "85": "1080p",
        "92": "240p",
        "93": "360p",
        "94": "480p",
        "95": "720p",
        "96": "1080p",
        "100": "360p",
        "101": "480p",
        "102": "720p",
        "132": "240p",
        "151": "72p",
        "133": "240p",
        "134": "360p",
        "135": "480p",
        "136": "720p",
        "137": "1080p",
        "138": ">1080p",
        "139": "48k",
        "140": "128k",
        "141": "256k",
        "160": "192p",
        "171": "128k",
        "172": "256k",
        "242": "240p",
        "243": "360p",
        "244": "480p",
        "245": "480p",
        "246": "480p",
        "247": "720p",
        "248": "1080p",
        "298": "720p60",
        "299": "1080p60",
        "271": "1440p",
        "313": "2160p",
        "315": "2160p60"
    }

    IE_NAME = "youtube"

    def __init__(self, params={}):
        proxyURL = params.get("proxyURL", "")
        useProxy = params.get("useProxy", False)
        self.cm = common(proxyURL, useProxy)
        self.cm.HOST = "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0"  # 'Mpython-urllib/2.7'

    def _extract_id(self, url):
        video_id = ""
        mobj = re.match(self._VALID_URL, url, re.VERBOSE)
        if mobj is not None:
            video_id = mobj.group(2)

        return video_id

    _YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;'
    _YT_INITIAL_PLAYER_RESPONSE_RE = r"ytInitialPlayerResponse\s*=\s*({.+?})\s*;"
    _YT_INITIAL_BOUNDARY_RE = r"(?:var\s+meta|</script|\n)"

    def _extract_yt_initial_variable(self, webpage, regex, video_id, name):
        return json_loads(self._search_regex((r"%s\s*%s" % (regex, self._YT_INITIAL_BOUNDARY_RE), regex), webpage, name, default="{}"))

    def _extract_caption_tracks(self, video_id, source=None):
        # source may be a player_response dict, a watch-page HTML string, or
        # None (fetch the watch page). YouTube dropped the old
        # api/timedtext?type=list endpoint; captionTracks in the player
        # response is the only listing now.
        if isinstance(source, dict):
            player_response = source
        else:
            webpage = source
            if webpage is None:
                url = "https://www.youtube.com/watch?v=%s&hl=%s&has_verified=1" % (video_id, GetDefaultLang())
                sts, webpage = self.cm.getPage(url)
                if not sts:
                    return []
            player_response = self._extract_yt_initial_variable(webpage, self._YT_INITIAL_PLAYER_RESPONSE_RE, video_id, "initial player response")
        try:
            return player_response["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"] or []
        except Exception:
            printDBG("youtube - captionTracks not found in player response")
            return []

    @staticmethod
    def _caption_track_name(lang):
        name = lang.get("name", {})
        if isinstance(name, dict):
            if name.get("simpleText"):
                return name["simpleText"]
            for run in name.get("runs", []):
                if run.get("text"):
                    return run["text"]
        return lang.get("languageCode", "")

    def _caption_tracks_to_subs(self, tracks, want_asr, start_idx=0):
        sub_tracks = []
        for lang in tracks or []:
            try:
                if (lang.get("kind") == "asr") != want_asr:
                    continue
                sub_url = urllib.parse.unquote_plus(lang["baseUrl"])
                sub_format = self.cm.ph.getSearchGroups(sub_url + "&", r"[\?&]fmt=([^\?^&]+)[\?&]")[0]
                if sub_format != "":
                    sub_url = sub_url.replace(sub_format, "vtt")
                else:
                    sub_url = sub_url + "&fmt=vtt"
                sub_lang = lang["languageCode"]
                sub_tracks.append({"title": self._caption_track_name(lang) or sub_lang, "url": sub_url, "lang": sub_lang, "ytid": start_idx + len(sub_tracks), "format": "vtt"})
            except Exception:
                printExc()
        return sub_tracks

    def _get_automatic_captions(self, video_id, webpage=None):
        # ASR (auto-generated) caption tracks
        return self._caption_tracks_to_subs(self._extract_caption_tracks(video_id, webpage), want_asr=True)

    def _get_subtitles(self, video_id, source=None):
        # manually authored / community caption tracks
        return self._caption_tracks_to_subs(self._extract_caption_tracks(video_id, source), want_asr=False)

    def _real_extract(self, url, allowVP9=False, authHeader=None):
        # authHeader: {"Authorization": "Bearer ..."} when the user is signed
        # in - lets the player request reach members-only / age-restricted
        # content. Broken into named steps below (was one 250+ line function);
        # each step's inputs/outputs are just what's in its signature/return.
        authHeader = authHeader or {}
        url = self._followNextUrlRedirect(url)
        video_id = self._extract_id(url)

        isGoogleDoc, video_id, sts, video_webpage, player_response, cookieFile = \
            self._resolvePlayerResponse(url, video_id, authHeader)

        if isGoogleDoc and not sts:
            reportExtractorError("Unable to download video webpage")
            return []
        if not player_response:
            reportExtractorError("Unable to get player response")
            return []

        video_info = player_response.get("videoDetails", {})
        video_duration = video_info.get("lengthSeconds", "")

        video_url_list, is_m3u8 = self._extractFormatUrls(player_response, video_info, video_id, allowVP9)
        if not video_url_list:
            return []

        if not self._decryptSignedUrls(video_url_list, video_webpage, video_id):
            return []

        cookieHeader = self.cm.getCookieHeader(cookieFile) if isGoogleDoc else None
        return self._buildResults(video_id, player_response, video_url_list, video_duration, is_m3u8, isGoogleDoc, cookieHeader)

    def _followNextUrlRedirect(self, url):
        # follow a next_url= redirect (old age-verification style link) if present
        mobj = re.search(self._NEXT_URL_RE, url)
        if mobj:
            # https
            return "https://www.youtube.com/" + _unquote(mobj.group(1)).lstrip("/")
        return url

    def _resolvePlayerResponse(self, url, video_id, authHeader):
        # Resolves the player response for a video, or for a legacy embedded
        # Google Doc ("yt-video-id" placeholder). Returns (isGoogleDoc,
        # video_id, sts, video_webpage, player_response, cookieFile) -
        # player_response is None when nothing playable was found.
        player_response = None
        if "yt-video-id" == video_id:
            video_id = self.cm.ph.getSearchGroups(url + "&", r"[\?&]docid=([^\?^&]+)[\?&]")[0]
            isGoogleDoc = True
            cookieFile = GetCookieDir("docs.google.com.cookie")
            sts, video_webpage = self.cm.getPage(url)
            return isGoogleDoc, video_id, sts, video_webpage, player_response, cookieFile

        isGoogleDoc = False
        cookieFile = None
        playerRequestUrl = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
        lang = GetDefaultLang()
        # Anonymous: ANDROID only, one request per video - the same
        # footprint the plain python3 host runs at without ever tripping
        # the bot wall. No IOS second request (also a yt-dlp fingerprint).
        it_clients = [
            ("3", YT_ANDROID_CLIENT_VERSION, False,
             "com.google.android.youtube/%s(Linux; U; Android %s) gzip" % (YT_ANDROID_CLIENT_VERSION, YT_ANDROID_OS_VERSION),
             "'clientVersion': '%s', 'clientName': 'ANDROID', 'androidSdkVersion': %s, 'osName': 'Android', 'osVersion': '%s'" % (YT_ANDROID_CLIENT_VERSION, YT_ANDROID_SDK_VERSION, YT_ANDROID_OS_VERSION)),
        ]
        video_webpage = ""
        ageReason = ""
        if authHeader:
            # Signed in: InnerTube only accepts the OAuth bearer token on
            # the TVHTML5 client (ANDROID/IOS/WEB + bearer -> HTTP 400), so
            # it is added as a last-resort client and is the only one the
            # token is attached to. It honours the token for age-restricted
            # / members content and gets past the bot wall (authenticated),
            # so it is tried even after an anonymous LOGIN_REQUIRED.
            it_clients.append(("7", "7.20250101.10.00", True,
                               "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version",
                               "'clientName': 'TVHTML5', 'clientVersion': '7.20250101.10.00'"))
        botWalled = False
        sts = False
        for cname, cver, extraChecks, ua, client_ctx in it_clients:
            header = {"User-Agent": ua, "Content-Type": "application/json", "Origin": "https://www.youtube.com", "X-YouTube-Client-Name": cname, "X-YouTube-Client-Version": cver}
            if cname == "7":
                header.update(authHeader)
            http_params = {"header": header, "raw_post_data": True}
            # contentCheckOk/racyCheckOk only on the authenticated client -
            # sending them anonymously is part of the yt-dlp fingerprint
            checks = " 'contentCheckOk': true, 'racyCheckOk': true," if extraChecks else ""
            post_data = "{'videoId': '%s',%s 'params': '2AMB', 'context': {'client': {'hl': '%s', %s,}}}" % (video_id, checks, lang, client_ctx)
            sts, data = self.cm.getPage(playerRequestUrl, http_params, post_data)
            if not sts:
                continue
            try:
                pr = json_loads(data)
            except Exception:
                continue
            status = pr.get("playabilityStatus", {}).get("status", "") if isinstance(pr, dict) else ""
            printDBG("_real_extract: player client %s -> %s" % (cname, status or "no status"))
            if isinstance(pr, dict) and pr.get("streamingData"):
                player_response, video_webpage = pr, data
                break
            if status in ("LOGIN_REQUIRED", "ERROR", "UNPLAYABLE", "AGE_VERIFICATION_REQUIRED"):
                player_response = pr
                ageReason = pr.get("playabilityStatus", {}).get("reason", "") or ageReason
                reason = (pr.get("playabilityStatus", {}).get("reason", "") or "").lower()
                if status == "LOGIN_REQUIRED" and ("bot" in reason or "sign in to confirm" in reason):
                    # YouTube's "sign in to confirm you're not a bot" wall.
                    # Every anonymous client and the watch page is gated the
                    # same way from the same IP, so hammering the rest just
                    # piles more flagged requests on and deepens the block.
                    # Anonymous -> stop now. Signed in -> keep going so the
                    # authenticated TVHTML5 client (7) still gets its try.
                    botWalled = True
                    if not authHeader:
                        break

        # last resort: the watch page's ytInitialPlayerResponse (its URLs
        # need sig + nsig descrambling, so worse quality, but sometimes the
        # only thing left) - skip it when we're already bot-walled, it is
        # gated too and only adds another flagged request
        if not botWalled and not (player_response and player_response.get("streamingData")):
            sts, wp = self.cm.getPage("https://www.youtube.com/watch?v=%s&bpctr=9999999999&has_verified=1&" % video_id)
            if sts:
                video_webpage = wp
                wr = self._extract_yt_initial_variable(wp, self._YT_INITIAL_PLAYER_RESPONSE_RE, video_id, "initial player response")
                if wr and wr.get("streamingData"):
                    player_response = wr

        if not (player_response and player_response.get("streamingData")):
            # nothing playable - almost always an age / sign-in wall, which
            # no anonymous YouTube client can pass any more
            SetIPTVPlayerLastHostError(ageReason or _("This video requires you to sign in to a YouTube account."))

        return isGoogleDoc, video_id, sts, video_webpage, player_response, cookieFile

    def _extractFormatUrls(self, player_response, video_info, video_id, allowVP9):
        # Returns (video_url_list, is_m3u8) built from streamingData's
        # formats/adaptiveFormats (with cipher/signatureCipher decoding), or
        # from the HLS manifest instead when it's a live broadcast or nothing
        # else was playable.
        url_map = {}
        video_url_list = {}

        try:
            is_m3u8 = "no"
            cipher = {}
            streaming_data = player_response.get("streamingData", {}) or {}
            # some clients (TVHTML5, a few age/members responses) return only
            # adaptiveFormats and no muxed "formats" list at all
            url_data_str = list(streaming_data.get("formats", []) or [])
            url_data_str += list(streaming_data.get("adaptiveFormats", []) or [])

            for url_data in url_data_str:

                printDBG(str(url_data))

                if "url" in url_data:
                    url_item = {"url": url_data["url"]}
                else:
                    cipher = ensure_str(url_data.get("cipher", "")) + ensure_str(url_data.get("signatureCipher", ""))
                    printDBG(cipher)

                    cipher = cipher.split("&")
                    sig_item = ""
                    s_item = ""
                    sp_item = ""
                    for item in cipher:
                        if "url=" in item:
                            url_item = {"url": _unquote(item.replace("url=", ""), None)}
                        if "sig=" in item:
                            sig_item = item.replace("sig=", "")
                        if "s=" in item:
                            s_item = item.replace("s=", "")
                        if "sp=" in item:
                            sp_item = item.replace("sp=", "")
                    if sig_item:
                        signature = sig_item
                        url_item["url"] += "&signature=" + signature
                    elif len(s_item):
                        url_item["esign"] = _unquote(s_item)
                        if len(sp_item):
                            url_item["url"] += "&%s={0}" % sp_item
                        else:
                            url_item["url"] += "&signature={0}"
                    if "ratebypass" not in url_item["url"]:
                        url_item["url"] += "&ratebypass=yes"

                url_map[str(url_data["itag"])] = url_item
            video_url_list = self._get_video_url_list(url_map, allowVP9)
        except Exception:
            printExc()

        # A currently-running live stream is served as server-side fragmented
        # DASH from googlevideo - a plain GET of those adaptiveFormats URLs
        # yields a stream exteplayer3/ffmpeg cannot demux (and the merge://
        # A/V downloader only ever grabs one fragment), so for a live video
        # the HLS manifest is the only thing that actually plays. Prefer it
        # even though adaptiveFormats are present. isLive is only set while
        # the broadcast is live; a finished stream's VOD has isLive absent
        # and keeps the normal DASH path.
        is_live = bool(video_info.get("isLive"))
        manifest_url = player_response.get("streamingData", {}).get("hlsManifestUrl")
        if manifest_url and (not video_url_list or is_live):
            hls_url_map = self._extract_from_m3u8(_unquote(manifest_url, None), video_id)
            hls_url_list = self._get_video_url_list(hls_url_map, allowVP9)
            if hls_url_list:
                is_m3u8 = "yes"
                video_url_list = hls_url_list

        return video_url_list, is_m3u8

    def _decryptSignedUrls(self, video_url_list, video_webpage, video_id):
        # Fills signItems' final URLs in place (dicts are mutable, so this
        # propagates straight into video_url_list). Returns False when the
        # caller should abort extraction with [], True otherwise (including
        # the common case of no ciphered formats at all).
        signItems = []
        signatures = []
        for idx in range(len(video_url_list)):
            if "esign" in video_url_list[idx][1]:
                signItems.append(video_url_list[idx][1])
                signatures.append(video_url_list[idx][1]["esign"])

        if not signatures:
            return True

        # decrypt signatures
        printDBG("signatures: %s" % signatures)
        playerUrl = ""
        tmp = ph.find(video_webpage, ("<script", ">", "player/base"))[1]
        playerUrl = ph.getattr(tmp, "src")
        if not playerUrl:
            for reObj in [r'"assets"\:[^\}]+?"js"\s*:\s*"([^"]+?)"', 'src="([^"]+?)"[^>]+?name="player.*?/base"', '"jsUrl":"([^"]+?)"']:
                playerUrl = ph.search(video_webpage, reObj)[0]
                if playerUrl:
                    break
        if not playerUrl:
            # video_webpage is the InnerTube JSON, not HTML - grab base.js
            # from the watch page instead
            sts, wp = self.cm.getPage("https://www.youtube.com/watch?v=%s" % video_id)
            if sts:
                playerUrl = self._search_regex([r'"jsUrl":"([^"]+?)"', r'"(?:PLAYER_JS_URL|jsUrl)"\s*:\s*"([^"]+base\.js)"'], wp, "player URL", default="")
        playerUrl = self.cm.getFullUrl(playerUrl.replace("\\", ""), self.cm.meta["url"])
        if playerUrl:
            decSignatures = CYTSignAlgoExtractor(self.cm).decryptSignatures(signatures, playerUrl)
            if len(signatures) == len(signItems):
                try:
                    for idx in range(len(signItems)):
                        signItems[idx]["url"] = signItems[idx]["url"].format(decSignatures[idx])
                except Exception:
                    printExc()
                    SetIPTVPlayerLastHostError(_("Decrypt Signatures Error"))
                    return False
            else:
                return False
        return True

    def _buildResults(self, video_id, player_response, video_url_list, video_duration, is_m3u8, isGoogleDoc, cookieHeader):
        caption_tracks = self._extract_caption_tracks(video_id, player_response)
        manual_sub_tracks = self._caption_tracks_to_subs(caption_tracks, False)
        sub_tracks = manual_sub_tracks + self._caption_tracks_to_subs(caption_tracks, True, start_idx=len(manual_sub_tracks))
        results = []
        for format_param, url_item in video_url_list:
            # Extension
            video_extension = self._video_extensions.get(format_param, "flv")

            # video_format = '{0} - {1}'.format(format_param if format_param else video_extension,
            #                                  self._video_dimensions.get(format_param, '???'))
            video_format = self._video_dimensions.get(format_param, "???")
            video_real_url = url_item["url"]
            if len(sub_tracks):
                video_real_url = strwithmeta(video_real_url, {"external_sub_tracks": sub_tracks})
            if isGoogleDoc:
                video_real_url = strwithmeta(video_real_url, {"Cookie": cookieHeader})

            results.append(
                {
                    "id": video_id,
                    "url": video_real_url,
                    "uploader": "",
                    "title": "",
                    "ext": video_extension,
                    "format": video_format,
                    "thumbnail": "",
                    "duration": video_duration,
                    "player_url": "",
                    "m3u8": is_m3u8,
                }
            )

        return results

    def _extract_from_m3u8(self, manifest_url, video_id):
        url_map = {}

        def _get_urls(_manifest):
            lines = _manifest.split("\n")
            urls = [l for l in lines if l and not l.startswith("#")]
            return urls

        sts, manifest = self.cm.getPage(manifest_url)
        if not sts:
            return url_map
        for format_url in _get_urls(manifest):
            itag = self._search_regex(r"itag/(\d+?)/", format_url, "itag", default="")
            if itag:
                url_map[itag] = {"url": format_url}
        return url_map

    def _search_regex(self, pattern, string, name, default=None, fatal=True, flags=0):
        compiled_regex_type = type(re.compile(""))
        mobj = None
        if isinstance(pattern, (str, compiled_regex_type)):
            mobj = re.search(pattern, string, flags)
        else:
            for p in pattern:
                mobj = re.search(p, string, flags)
                if mobj:
                    break

        if mobj:
            # return the first matching group
            return next(g for g in mobj.groups() if g is not None)
        elif default is not None:
            return default
        elif fatal:
            raise Exception("Unable to extract %s" % name)
        else:
            printDBG("unable to extract %s" % name)
            return None

    def _get_video_url_list(self, url_map, allowVP9=False):
        format_list = list(self._available_formats_prefer_free)  # available_formats
        if allowVP9:
            format_list.extend(["313", "315", "271"])
        existing_formats = [x for x in format_list if x in url_map]

        return [(f, url_map[f]) for f in existing_formats]  # All formats
