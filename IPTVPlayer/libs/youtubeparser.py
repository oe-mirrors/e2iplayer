# -*- coding: utf-8 -*-
# Last Modified: 01.07.2026 - Change: configurable YouTube display language, configurable channel name for downloaded files, absolute published date in info view
# LOCAL import
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.youtube import YoutubeIE
from Plugins.Extensions.IPTVPlayer.libs.youtube_oauth import YouTubeOAuth
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsExecutable
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import decorateUrl
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse, urlunparse, parse_qsl

# FOREIGN import
import re
import time
from datetime import timedelta
from Components.Language import language
from Components.config import config, ConfigSelection, ConfigYesNo

# Config options for HOST
config.plugins.iptvplayer.ytDefaultformat = ConfigSelection(default="720", choices=[("0", _("the worst")), ("144", "144p"), ("240", "240p"), ("360", "360p"), ("720", "720p"), ("1080", "1080p"), ("1440", "1440p"), ("2160", "2160p"), ("9999", _("the best"))])
config.plugins.iptvplayer.ytUseDF = ConfigYesNo(default=True)
config.plugins.iptvplayer.ytVP9 = ConfigYesNo(default=False)
config.plugins.iptvplayer.ytShowDash = ConfigSelection(default="auto", choices=[("auto", _("Auto")), ("true", _("Yes")), ("false", _("No"))])
config.plugins.iptvplayer.ytSortBy = ConfigSelection(default="A", choices=[("A", _("Relevance")), ("I", _("Upload date")), ("M", _("View count")), ("E", _("Rating"))])
config.plugins.iptvplayer.youtube_search_region = ConfigSelection(default="auto", choices=[("auto", _("Automatic"))] + [(c, c) for c in ("US", "GB", "DE", "AT", "CH", "FR", "IT", "ES", "PL", "NL", "BE", "CZ", "RU", "UA", "TR", "GR", "SE", "PT", "BR", "MX", "IN", "JP", "KR", "CA", "AU")])
config.plugins.iptvplayer.youtube_safe_search = ConfigYesNo(default=False)

# InnerTube WEB client. The API key is the long-lived public youtube.com one
# (unchanged for years, also used by yt-dlp); the client version and
# visitorData rot and are refreshed at runtime from ytcfg - see
# YouTubeParser._absorbPageConfig() / _getYtConfig(). These are only the
# fallbacks for when that scrape fails.
YT_INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # NOSONAR
YT_CLIENT_VERSION_FALLBACK = "2.20260904.01.00"

# Fallback region (YouTube gl=) per selectable UI language - only the codes
# where it isn't simply the language code upper-cased.
_YT_LANG_DEFAULT_REGION = {
    "en": "US", "cs": "CZ", "el": "GR", "da": "DK", "sv": "SE", "uk": "UA",
    "ja": "JP", "ko": "KR", "zh": "CN", "ar": "SA", "sr": "RS", "he": "IL",
    "hi": "IN", "no": "NO", "nb": "NO", "sl": "SI", "et": "EE",
}


class YouTubeParser:

    # process-wide cache: {"client_version": str, "api_key": str, "visitor_data": str}
    _ytConfig = None

    def __init__(self):
        self.cm = common()
        self.HTTP_HEADER = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": YT_CLIENT_VERSION_FALLBACK,
            "X-Requested-With": "XMLHttpRequest"
        }
        self.http_params = {"header": self.HTTP_HEADER, "return_data": True}
        self.postdata = {}
        self.sessionToken = ""
        return

    def _absorbPageConfig(self, data):
        # every youtube.com HTML page carries the full ytcfg; harvest the
        # bits that go stale so continuation POSTs stay current for free.
        try:
            data = ensure_str(data)
        except Exception:
            return
        cfg = dict(YouTubeParser._ytConfig or {})
        m = re.search(r'"INNERTUBE_(?:CONTEXT_)?CLIENT_VERSION":"([0-9.]+)"', data)
        if m:
            cfg["client_version"] = m.group(1)
        m = re.search(r'"INNERTUBE_API_KEY":"([A-Za-z0-9_\-]+)"', data)
        if m:
            cfg["api_key"] = m.group(1)
        m = re.search(r'"visitorData":"([^"\\]{20,2000})"', data)
        if m:
            cfg["visitor_data"] = m.group(1)
        if cfg:
            YouTubeParser._ytConfig = cfg

    def _getYtConfig(self, fetchIfMissing=False):
        if fetchIfMissing and not (YouTubeParser._ytConfig or {}).get("client_version"):
            # continuation-only flow with nothing harvested yet - one cheap
            # fetch of the home page, else fall through to the constants
            try:
                sts, data = self.cm.getPage("https://www.youtube.com/", self.http_params)
                if sts and data:
                    self._absorbPageConfig(data)
            except Exception:
                printExc()
        cfg = YouTubeParser._ytConfig or {}
        return {
            "client_version": cfg.get("client_version") or YT_CLIENT_VERSION_FALLBACK,
            "api_key": cfg.get("api_key") or YT_INNERTUBE_API_KEY,
            "visitor_data": cfg.get("visitor_data") or "",
        }

    @staticmethod
    def isDashAllowed():
        value = config.plugins.iptvplayer.ytShowDash.value
        printDBG("ALLOW DASH: >> %s" % value)
        if value == "true" and IsExecutable("ffmpeg"):
            return True
        elif value == "auto" and IsExecutable("ffmpeg") and IsExecutable("/usr/bin/exteplayer3"):
            return True
        else:
            return False

    @staticmethod
    def isVP9Allowed():
        value = config.plugins.iptvplayer.ytVP9.value
        printDBG("1. ALLOW VP9: >> %s" % value)
        value = YouTubeParser.isDashAllowed() and value
        printDBG("2. ALLOW VP9: >> %s" % value)
        return value

    def checkSessionToken(self, data):
        self._absorbPageConfig(data)
        if not self.sessionToken:
            token = self.cm.ph.getSearchGroups(data, '''"XSRF_TOKEN":"([^"]+?)"''')[0]
            if token:
                printDBG("Update session token: %s" % token)
                self.sessionToken = token
                self.postdata = {"session_token": token}

    # DIRECT LINK RESOLUTION
    def getDirectLinks(self, url, dash=True, dashSepareteList=False, allowVP9=None):
        printDBG("YouTubeParser.getDirectLinks")
        linksList = self._resolveVideoLinks(url, allowVP9)
        if linksList is None:
            return ([], []) if dashSepareteList else []

        dashAudioLists, dashVideoLists, dashList = self._splitDashLists(linksList) if dash else ([], [], [])
        retList, retHLSList = self._filterFormatLists(linksList)
        dashList = self._appendMergedDashItems(dashAudioLists, dashVideoLists, dashList)

        # no progressive/muxed format survived - fall back to the HLS list
        # (_real_extract already resolves hlsManifestUrl and the DASH
        # adaptiveFormats; the old "hlsvp"/"dashmpd" watch-page keys this
        # used to scrape were removed by YouTube years ago)
        if 0 == len(retList):
            retList = retHLSList

        for idx in range(len(retList)):
            if retList[idx].get("m3u8", False):
                retList[idx]["url"] = strwithmeta(retList[idx]["url"], {"iptv_m3u8_live_start_index": -30})

        if dashSepareteList:
            return retList, dashList
        else:
            retList.extend(dashList)
            return retList

    def _resolveVideoLinks(self, url, allowVP9):
        # Resolves a /channel/.../live URL to its live video's watch URL,
        # then runs the real extractor. None on failure (the caller returns
        # the dashSepareteList-appropriate empty result for that).
        try:
            if self.cm.isValidUrl(url) and "/channel/" in url and url.endswith("/live"):
                sts, data = self.cm.getPage(url)
                if sts:
                    videoId = self.cm.ph.getSearchGroups(data, """<meta[^>]+?itemprop=['"]videoId['"][^>]+?content=['"]([^'^"]+?)['"]""")[0]
                    if videoId == "":
                        videoId = self.cm.ph.getSearchGroups(data, r"""['"]REDIRECT_TO_VIDEO['"]\s*\,\s*['"]([^'^"]+?)['"]""")[0]
                    if videoId != "":
                        url = "https://www.youtube.com/watch?v=" + videoId
            return YoutubeIE()._real_extract(url, allowVP9=allowVP9, authHeader=self._getAuthHeader())
        except Exception:
            printExc()
            return None

    def _splitDashLists(self, linksList):
        # Separates the audio-only / video-only DASH renditions (best
        # quality first); mpd items are expanded into a dash-tagged list of
        # their own straight away.
        reNum = re.compile("([0-9]+)")
        dashAudioLists = []
        dashVideoLists = []
        dashList = []
        for item in linksList:
            if "mp4a" == item["ext"]:
                dashAudioLists.append(item)
            elif item["ext"] in ("mp4v", "webmv"):
                dashVideoLists.append(item)
            elif "mpd" == item["ext"]:
                tmpList = getMPDLinksWithMeta(ensure_str(item["url"]), checkExt=False)
                printDBG(tmpList)
                for idx in range(len(tmpList)):
                    tmpList[idx]["format"] = "%sx%s" % (tmpList[idx].get("height", 0), tmpList[idx].get("width", 0))
                    tmpList[idx]["ext"] = "mpd"
                    tmpList[idx]["dash"] = True
                dashList.extend(tmpList)

        def _key(x):
            if x["format"].startswith(">"):
                return int(x["format"][1:-1])
            else:
                return int(ph.search(x["format"], reNum)[0])

        dashAudioLists = sorted(dashAudioLists, key=_key, reverse=True)
        dashVideoLists = sorted(dashVideoLists, key=_key, reverse=True)
        return dashAudioLists, dashVideoLists, dashList

    def _filterFormatLists(self, linksList):
        # Progressive/muxed mp4 formats, split into plain (retList) and
        # HLS (retHLSList). mp4 is the only progressive container YouTube
        # still serves (webm/3gp progressive formats died years ago).
        retHLSList = []
        retList = []
        for item in linksList:
            printDBG(">>>>>>>>>>>>>>>>>>>>>")
            printDBG(str(item))
            printDBG("<<<<<<<<<<<<<<<<<<<<<")
            if "mp4" == item["ext"]:
                if "yes" == item["m3u8"]:
                    format = re.search("([0-9]+?)p$", item["format"])
                    if format is not None:
                        item["format"] = format.group(1) + "x"
                        item["ext"] = item["ext"] + "_M3U8"
                        item["url"] = decorateUrl(ensure_str(item["url"]), {"iptv_proto": "m3u8"})
                        retHLSList.append(item)
                else:
                    format = re.search("([0-9]+?x[0-9]+?$)", item["format"])
                    if format is not None:
                        item["format"] = format.group(1)
                        item["url"] = decorateUrl(ensure_str(item["url"]))
                        retList.append(item)
        return retList, retHLSList

    def _appendMergedDashItems(self, dashAudioLists, dashVideoLists, dashList):
        if len(dashAudioLists):
            # use best audio
            for item in dashVideoLists:
                item = dict(item)
                # iptv_use_ffmpeg: mux the two renditions with ffmpeg
                # (FFMPEGDownloader, progressive) rather than wget-both-then-mux
                # (MergeDownloader), which downloaded the whole file before
                # playback could start. Only the buffered path reads this flag;
                # no-buffer playback hands exteplayer3 the two URLs via -x.
                mergeMeta = {"audio_url": dashAudioLists[0]["url"], "video_url": ensure_str(item["url"]), "iptv_use_ffmpeg": True}
                # carry the caption tracks over - decorateUrl on the literal
                # "merge://" string would otherwise drop them
                try:
                    subs = strwithmeta(item["url"]).meta.get("external_sub_tracks", [])
                    if subs:
                        mergeMeta["external_sub_tracks"] = subs
                except Exception:
                    printExc()
                item["url"] = decorateUrl("merge://audio_url|video_url", mergeMeta)
                dashList.append(item)
        return dashList

    def updateQueryUrl(self, url, queryDict):
        urlParts = urlparse(url)
        query = dict(parse_qsl(urlParts[4]))
        query.update(queryDict)
        new_query = urllib_urlencode(query)
        new_url = urlunparse((urlParts[0], urlParts[1], urlParts[2], urlParts[3], new_query, urlParts[5]))
        return new_url

    def findKeys(self, node, kv):
        if isinstance(node, list):
            for i in node:
                for x in self.findKeys(i, kv):
                    yield x
        elif isinstance(node, dict):
            if kv in node:
                yield node[kv]
            for j in list(node.values()):
                for x in self.findKeys(j, kv):
                    yield x

    def _normalizeText(self, txt):
        txt = ensure_str(txt or "")
        txt = txt.replace("\\u0026", "&")
        txt = txt.replace("\\u003c", "<")
        txt = txt.replace("\\u003e", ">")
        txt = txt.replace("\\/", "/")
        return txt

    def _normalizeThumbnailUrl(self, url):
        url = self._normalizeText(url)
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if url.startswith("http:") and not url.startswith("https:"):
            host = urlparse(url).netloc.lower()
            if host.endswith(("googleusercontent.com", "ggpht.com", "ytimg.com")):
                url = "https:" + url[5:]
        if "?" in url:
            url = url.split("?", 1)[0]
        url = re.sub(r"=s([0-9]+)(?:-c)?(?:-k-c0x00ffffff)?(?:-no-rj)?(?:-mo)?$", "", url, flags=re.IGNORECASE)
        url = re.sub(r"(/hq720)(?:_custom_[0-9]+)+(\.(jpg|jpeg|png|webp))$", r"\1\2", url, flags=re.IGNORECASE)
        url = re.sub(r"(/hqdefault)(?:_custom_[0-9]+)+(\.(jpg|jpeg|png|webp))$", r"\1\2", url, flags=re.IGNORECASE)
        url = re.sub(r"(/mqdefault)(?:_custom_[0-9]+)+(\.(jpg|jpeg|png|webp))$", r"\1\2", url, flags=re.IGNORECASE)
        url = re.sub(r"(/default)(?:_custom_[0-9]+)+(\.(jpg|jpeg|png|webp))$", r"\1\2", url, flags=re.IGNORECASE)
        if "/ytc/" in url:
            url = url.replace("yt3.ggpht.com/ytc/", "yt3.googleusercontent.com/ytc/")
        return strwithmeta(url)

    def getThumbnailUrl(self, thumbJson, maxWidth=1000, hq=False):
        url = ""
        videoId = ""
        best = ""
        bestWidth = -1
        try:
            thumbJson2 = []
            try:
                videoId = ensure_str(thumbJson.get("videoId", ""))
            except Exception:
                pass
            try:
                thumbJson2 = thumbJson["thumbnail"]["thumbnails"]
            except Exception:
                pass
            if len(thumbJson2) == 0:
                try:
                    thumbJson2 = thumbJson["thumbnails"][0]["thumbnails"]
                except Exception:
                    pass
            thumbJson = thumbJson2
            width = 0
            i = 0
            while i < len(thumbJson):
                img = thumbJson[i]
                tmp = ensure_str(img.get("url", ""))
                width = img.get("width", 0)
                if tmp:
                    tmp = self._normalizeThumbnailUrl(tmp)
                    if tmp and width <= maxWidth and width > bestWidth:
                        best = tmp
                        bestWidth = width
                    elif tmp and not best:
                        best = tmp
                i += 1
            url = best
            if not url and videoId:
                if hq:
                    url = "https://i.ytimg.com/vi/%s/hqdefault.jpg" % videoId
                else:
                    url = "https://i.ytimg.com/vi/%s/mqdefault.jpg" % videoId
                url = self._normalizeThumbnailUrl(url)
        except Exception:
            printExc()
        return url

    def _getTextFromRuns(self, runs):
        txt = []
        try:
            for item in runs:
                t = self._normalizeText(item.get("text", ""))
                if t:
                    txt.append(t)
        except Exception:
            printExc()
        return "".join(txt).strip()

    def _getSimpleText(self, data):
        try:
            if isinstance(data, dict):
                if "simpleText" in data:
                    return self._normalizeText(data.get("simpleText", "")).strip()
                if "runs" in data:
                    return self._getTextFromRuns(data.get("runs", []))
        except Exception:
            printExc()
        return ""

    def _getDescriptionText(self, jsonData):
        desc = ""
        try:
            desc = self._getSimpleText(jsonData.get("descriptionSnippet", {}))
        except Exception:
            pass
        if not desc:
            try:
                metaList = jsonData.get("detailedMetadataSnippets", [])
                for meta in metaList:
                    desc = self._getSimpleText(meta.get("snippetText", {}))
                    if desc:
                        break
            except Exception:
                printExc()
        if not desc:
            try:
                desc = self._getSimpleText(jsonData.get("descriptionText", {}))
            except Exception:
                pass
        if not desc:
            try:
                desc = self._normalizeText(jsonData.get("title", {}).get("accessibility", {}).get("accessibilityData", {}).get("label", "")).strip()
            except Exception:
                pass
        return self._normalizeText(desc)

    def parseIsoDateToShort(self, value):
        try:
            value = self._normalizeText(ensure_str(value or "").strip())
            if not value:
                return ""
            m = re.search(r"\d{4}-\d{2}-\d{2}", value)
            if not m:
                m = re.search(r"\d{2}\.\d{2}\.\d{2}", value)
                if m:
                    ts = time.strptime(m.group(0), "%d.%m.%y")
                    return time.strftime("%Y-%m-%d", ts)
                return ""
            ts = time.strptime(m.group(0), "%Y-%m-%d")
            return time.strftime("%Y-%m-%d", ts)
        except Exception:
            printExc()
            return ""

    # WATCH PAGE PARSER
    def _getWatchPageData(self, videoId):
        printDBG("YouTubeParser._getWatchPageData START videoId[%s]" % videoId)
        retData = {
            "fullDescription": "",
            "absolutePublished": "",
            "channelName": "",
        }
        try:
            videoId = str(videoId or "").strip()
            if not videoId:
                return retData
            url = "https://www.youtube.com/watch?v=%s" % videoId
            sts, data = self.cm.getPage(url, self._applyYoutubeHeaders())
            if not sts or not data:
                printDBG("YouTubeParser._getWatchPageData getPage FAILED")
                return retData
            data = ensure_str(data)
            self._absorbPageConfig(data)
            publishDate = ""
            m = re.search(r'"publishDate":"([^"]+)"', data, re.IGNORECASE)
            if m:
                publishDate = self._normalizeText(m.group(1))
            if not publishDate:
                m = re.search(r'"uploadDate":"([^"]+)"', data, re.IGNORECASE)
                if m:
                    publishDate = self._normalizeText(m.group(1))
            if publishDate:
                retData["absolutePublished"] = self.parseIsoDateToShort(publishDate)
            if not retData["absolutePublished"]:
                try:
                    patterns = [
                        r"Live übertragen am\s+(\d{1,2}\.\d{1,2}\.\d{4})",
                        r"Premiere hatte am\s+(\d{1,2}\.\d{1,2}\.\d{4})",
                        r"Veröffentlicht am\s+(\d{1,2}\.\d{1,2}\.\d{4})",
                        r"Streamed live on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                        r"Published on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                    ]
                    for pattern in patterns:
                        m = re.search(pattern, data, re.IGNORECASE)
                        if m:
                            value = ensure_str(m.group(1)).strip()
                            try:
                                ts = time.strptime(value, "%d.%m.%Y")
                            except Exception:
                                try:
                                    ts = time.strptime(value, "%B %d, %Y")
                                except Exception:
                                    ts = time.strptime(value, "%b %d, %Y")
                            retData["absolutePublished"] = time.strftime("%Y-%m-%d", ts)
                            printDBG("YouTubeParser._getWatchPageData absolutePublished from visible text[%s]" % retData["absolutePublished"])
                            break
                except Exception:
                    printExc()
            channelName = ""
            for pattern in [r'"ownerChannelName":"([^"]+)"', r'"channelName":"([^"]+)"', r'"author":"([^"]+)"']:
                m = re.search(pattern, data)
                if m:
                    channelName = self._normalizeText(m.group(1))
                    break
            if channelName:
                retData["channelName"] = str(channelName or "")
            fullDesc = ""
            try:
                m = re.search(r'"shortDescription":"((?:\\.|[^"\\])*)"', data)
                if m:
                    fullDesc = json_loads('"%s"' % m.group(1))
            except Exception:
                printExc()
            if not fullDesc:
                try:
                    data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
                    if len(data2) == 0:
                        data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
                    data2 = ensure_str(data2.strip())
                    if data2:
                        response = json_loads(data2)
                        candidates = list(self.findKeys(response, "description"))
                        for item in candidates:
                            txt = self._getSimpleText(item)
                            if txt and len(txt) > len(fullDesc):
                                fullDesc = txt
                except Exception:
                    printExc()
            if fullDesc:
                fullDesc = self._normalizeText(ensure_str(fullDesc)).replace(r"\n", "\n").replace(r"\/", "/")
                retData["fullDescription"] = str(fullDesc or "")
            printDBG("YouTubeParser._getWatchPageData absolutePublished[%s]" % retData["absolutePublished"])
            printDBG("YouTubeParser._getWatchPageData fullDescriptionLen[%d]" % len(retData["fullDescription"]))
            printDBG("YouTubeParser._getWatchPageData channelName[%s]" % retData["channelName"])
        except Exception:
            printExc()
        return retData

    @staticmethod
    def _isShortCommand(command):
        # a YouTube Short opens with a reelWatchEndpoint / a /shorts/ url instead of /watch
        if not isinstance(command, dict):
            return False
        if "reelWatchEndpoint" in command:
            return True
        return "/shorts/" in str(command.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", ""))

    @staticmethod
    def _markShort(params):
        # a Short stays a video, only its list icon differs (ShortItem.png, components/iptvlist.py)
        params["image_type"] = "SHORT"
        return params

    def getShortsLockupData(self, shortsJson):
        # a Short of a channel's Shorts tab or of a search (shortsLockupViewModel)
        command = shortsJson.get("onTap", {}).get("innertubeCommand", {})
        videoId = command.get("reelWatchEndpoint", {}).get("videoId", "")
        if not videoId:
            videoId = str(shortsJson.get("entityId", "")).replace("shorts-shelf-item-", "")
        if not re.match(r"^[A-Za-z0-9_-]{11}$", videoId):
            return {}
        overlay = shortsJson.get("overlayMetadata", {})
        title = self._normalizeText(overlay.get("primaryText", {}).get("content", ""))
        if not title:
            return {}
        views = self._normalizeText(overlay.get("secondaryText", {}).get("content", ""))
        return self._markShort({
            "type": "video",
            "category": "video",
            "title": title,
            "url": "https://www.youtube.com/watch?v=%s" % videoId,
            "icon": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % videoId,
            "time": "",
            "desc": " | ".join(part for part in ("Short", views) if part),
            "video_id": ensure_str(videoId),
        })

    # VIDEO DATA PARSER
    def getVideoData(self, videoJson):
        videoId = videoJson.get("videoId", "")
        if not videoId:
            return {}
        url = "https://www.youtube.com/watch?v=%s" % videoId
        try:
            title = self._getSimpleText(videoJson.get("title", {}))
            if not title:
                title = ensure_str(videoJson["title"]["runs"][0]["text"])
        except Exception:
            try:
                title = ensure_str(videoJson["title"]["simpleText"])
            except Exception:
                title = ""
        title = ensure_str(title)
        badges = []
        videoBadges = videoJson.get("badges", [])
        for videoBadge in videoBadges:
            try:
                badgeLabel = ensure_str(videoBadge["metadataBadgeRenderer"]["label"])
                if badgeLabel:
                    badges.append(badgeLabel.upper())
            except Exception:
                pass
        if badges:
            title = title + " [" + (" , ".join(badges)) + "]"
        icon = self.getThumbnailUrl(videoJson)
        descTab = []
        try:
            duration = self._getSimpleText(videoJson.get("lengthText", {}))
            if duration:
                descTab.append(_("Duration: %s") % ensure_str(duration))
        except Exception:
            pass
        try:
            views = self._getSimpleText(videoJson.get("viewCountText", {}))
            if views:
                descTab.append(ensure_str(views))
        except Exception:
            pass
        try:
            time = self._getSimpleText(videoJson.get("publishedTimeText", {}))
            if time:
                descTab.append(ensure_str(time))
        except Exception:
            time = ""
        owner = ""
        try:
            owner = self._getSimpleText(videoJson.get("ownerText", {}))
        except Exception:
            owner = ""
        if not owner:
            try:
                owner = self._getSimpleText(videoJson.get("longBylineText", {}))
            except Exception:
                owner = ""
        owner = ensure_str(owner)
        if descTab:
            desc = " | ".join(descTab)
            if owner:
                desc += "\n" + owner
        else:
            desc = owner
        extraDesc = self._getDescriptionText(videoJson)
        if extraDesc:
            if desc:
                if extraDesc != owner:
                    desc += "\n" + extraDesc
            else:
                desc = extraDesc
        desc = self._normalizeText(desc)
        params = {
            "type": "video",
            "category": "video",
            "title": title,
            "url": ensure_str(url),
            "icon": icon,
            "time": time,
            "desc": desc,
            "video_id": ensure_str(videoId),
        }
        if self._isShortCommand(videoJson.get("navigationEndpoint", {})):
            self._markShort(params)
        return params

    # CHANNEL DATA PARSER
    def getChannelData(self, chJson):
        chId = chJson.get("channelId", "")
        if chId:
            url = "https://www.youtube.com/channel/%s" % chId
            title = self._normalizeText(self._getSimpleText(chJson.get("title", {})))
            icon = self.getThumbnailUrl(chJson)
            desc = self._normalizeText(self._getDescriptionText(chJson))
            return {"type": "category", "category": "channel", "title": title, "url": ensure_str(url), "icon": icon, "time": "", "desc": desc}
        else:
            return {}

    # PLAYLIST DATA PARSER
    def getPlaylistData(self, plJson):
        plId = plJson.get("playlistId", "")
        if plId:
            url = "https://www.youtube.com/playlist?list=%s" % plId
            title = self._normalizeText(plJson["title"]["simpleText"])
            icon = self.getThumbnailUrl(plJson)
            videoCount = plJson["videoCount"]
            desc = _("videos: %s") % videoCount
            try:
                by = self._normalizeText(plJson["longBylineText"]["runs"][0]["text"])
                desc = desc + "\n" + by
            except Exception:
                pass
            return {"type": "category", "category": "playlist", "title": title, "url": ensure_str(url), "icon": icon, "time": "", "desc": self._normalizeText(desc)}
        else:
            return {}

    # MENU ITEM PARSER
    def getMenuItemData(self, itemJson):
        try:
            title = self._normalizeText(itemJson["title"]["simpleText"])
            icon = self.getThumbnailUrl(itemJson)
            try:
                feedId = itemJson["navigationEndpoint"]["browseEndpoint"]["params"]
                url = "https://www.youtube.com/feed/trending?bp=%s&pbj=1" % feedId
                cat = "feeds_" + title
            except Exception:
                try:
                    url = "https://www.youtube.com" + itemJson["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
                except Exception:
                    printExc()
                    return {}
            if "/channel/" in url or "/@" in url:
                return {"type": "category", "category": "channel", "title": title, "url": ensure_str(url), "icon": icon, "time": "", "desc": ""}
            else:
                return {"type": "feed", "category": cat, "title": title, "url": ensure_str(url), "icon": icon, "time": "", "desc": ""}
        except Exception:
            printExc()
            return {}

    # FEED PARSER
    def getFeedsList(self, url):
        printDBG("YouTubeParser.getFeedList")
        currList = []
        try:
            sts, data = self.cm.getPage(url, self.http_params)
            if sts:
                self.checkSessionToken(data)
                data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
                if len(data2) == 0:
                    data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
                try:
                    response = json_loads(data2 + "}")
                    submenu = response["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"]["subMenu"]
                    for item in submenu["channelListSubMenuRenderer"]["contents"]:
                        menuJson = item.get("channelListSubMenuAvatarRenderer", "")
                        if menuJson:
                            params = self.getMenuItemData(menuJson)
                            if params:
                                printDBG(str(params))
                                currList.append(params)
                except Exception:
                    printExc()
        except Exception:
            printExc()
        return currList

    # VIDEO FROM FEED PARSER
    def getVideoFromFeed(self, url):
        printDBG("YouTubeParser.getVideosFromFeed")
        currList = []
        try:
            sts, data = self.cm.getPage(url, self.http_params)
            if sts:
                self.checkSessionToken(data)
                try:
                    response = json_loads(data)
                    rr = {}
                    for r in response:
                        if r.get("response", ""):
                            rr = r
                            break
                    if not rr:
                        return []
                    r1 = rr["response"]["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"]["contents"]
                    r2 = r1[0]["itemSectionRenderer"]["contents"][0]["shelfRenderer"]["content"]["expandedShelfContentsRenderer"]["items"]
                    for item in r2:
                        chJson = item.get("channelRenderer", "")
                        videoJson = item.get("videoRenderer", "")
                        plJson = item.get("playlistRenderer", "")
                        params = {}
                        if videoJson:
                            # it is a video
                            params = self.getVideoData(videoJson)
                        elif chJson:
                            # it is a channel
                            params = self.getChannelData(chJson)
                        elif plJson:
                            # it is a playlist
                            params = self.getPlaylistData(plJson)
                        if params:
                            printDBG(str(params))
                            currList.append(params)
                except Exception:
                    printExc()
        except Exception:
            printExc()
        return currList

    # New parsing function for lockupViewModel
    def getLockupVideoData(self, lockupJson):
        videoId = lockupJson.get("contentId", "")
        if not videoId:
            return {}
        # Videos only, no other types
        if lockupJson.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
            return {}
        url = "https://www.youtube.com/watch?v=%s" % videoId
        try:
            title = lockupJson["metadata"]["lockupMetadataViewModel"]["title"]["content"]
            title = self._normalizeText(title)
        except Exception:
            return {}
        # Thumbnail - Trim query parameters
        icon = ""
        try:
            sources = lockupJson["contentImage"]["thumbnailViewModel"]["image"]["sources"]
            icon = ensure_str(sources[-1]["url"])
            icon = self._normalizeThumbnailUrl(icon)
            if "?" in icon:
                icon = icon.split("?")[0]
        except Exception:
            pass
        # Duration of the overlays
        desc = []
        time = ""
        try:
            overlays = lockupJson["contentImage"]["thumbnailViewModel"]["overlays"]
            for overlay in overlays:
                badge = overlay.get("thumbnailBottomOverlayViewModel", {}).get("badges", [])
                if badge:
                    duration = badge[0].get("thumbnailBadgeViewModel", {}).get("text", "")
                    if duration:
                        desc.append(_("Duration: %s") % self._normalizeText(duration))
                        break
        except Exception:
            pass
        # Views and date
        try:
            meta_rows = lockupJson["metadata"]["lockupMetadataViewModel"]["metadata"]["contentMetadataViewModel"]["metadataRows"]
            for row in meta_rows:
                parts = row.get("metadataParts", [])
                for part in parts:
                    text = part.get("text", {}).get("content", "")
                    text = self._normalizeText(text)
                    if text:
                        desc.append(text)
                        if not time and ("temu" in text or "godzin" in text or "minut" in text or "sekund" in text or "dni" in text or "tygodni" in text or "miesięcy" in text or "lat" in text or "Transmisja" in text):
                            time = text
        except Exception:
            pass
        desc_str = self._normalizeText(" | ".join(desc))
        params = {
            "type": "video",
            "category": "video",
            "title": title,
            "url": ensure_str(url),
            "icon": icon,
            "time": time,
            "desc": desc_str,
            "video_id": ensure_str(videoId),
        }
        if self._isShortCommand(lockupJson.get("rendererContext", {}).get("commandContext", {}).get("onTap", {}).get("innertubeCommand", {})):
            self._markShort(params)
        return params

    # Tray List PARSER
    def getVideosFromTraylist(self, url, category, page, cItem):
        printDBG("YouTubeParser.getVideosFromTraylist")
        return self.getVideosApiPlayList(url, category, page, cItem)

    # PLAYLIST PARSER
    def getVideosFromPlaylist(self, url, category, page, cItem):
        printDBG("YouTubeParser.getVideosFromPlaylist")
        return self.getVideosApiPlayList(url, category, page, cItem)

    # LOCALE HELPERS
    def _getDefaultLangAndRegion(self):
        lang, region = self._deriveLangAndRegion()
        try:
            searchRegion = ensure_str(config.plugins.iptvplayer.youtube_search_region.value)
            if searchRegion and searchRegion != "auto":
                region = searchRegion
        except Exception:
            printExc()
        return lang, region

    def _deriveLangAndRegion(self):
        lang = "en"
        region = "US"
        try:
            selectedLang = ensure_str(config.plugins.iptvplayer.youtube_ui_language.value).lower()
            if selectedLang and selectedLang != "system":
                return selectedLang, _YT_LANG_DEFAULT_REGION.get(selectedLang, selectedLang.upper())
            locale = ensure_str(language.getLanguage())
            if "_" in locale:
                tmp = locale.split("_", 1)
                if len(tmp) == 2:
                    lang = (tmp[0] or "en").lower()
                    region = (tmp[1] or "US").upper()
            elif "-" in locale:
                tmp = locale.split("-", 1)
                if len(tmp) == 2:
                    lang = (tmp[0] or "en").lower()
                    region = (tmp[1] or "US").upper()
            elif locale:
                lang = locale.lower()
                region = "US"
        except Exception:
            printExc()
        return lang, region

    def _getAcceptLanguage(self):
        lang, region = self._getDefaultLangAndRegion()
        return "%s-%s,%s;q=0.9" % (lang, region, lang)

    def _getAuthHeader(self):
        try:
            if not hasattr(self, "_oauth"):
                self._oauth = YouTubeOAuth()
            return self._oauth.getAuthHeader()
        except Exception:
            printExc()
            return {}

    def _applyYoutubeHeaders(self, http_params=None, accept_language=None):
        params = self.http_params if http_params is None else dict(http_params)
        hdr = dict(params.get("header", {}))
        hdr["Accept-Language"] = accept_language if accept_language is not None else self._getAcceptLanguage()
        cfg = self._getYtConfig()
        hdr["X-YouTube-Client-Name"] = "1"
        hdr["X-YouTube-Client-Version"] = cfg["client_version"]
        hdr["Origin"] = "https://www.youtube.com"
        # NB: the OAuth bearer token is deliberately NOT added here - InnerTube
        # rejects it on the WEB client (browse/search/continuations all 400).
        # It is only usable on the TVHTML5 client (see _tvBrowse) and on the
        # player request (see getDirectLinks -> _real_extract authHeader=).
        hdr["X-Youtube-Bootstrap-Logged-In"] = "false"
        if cfg["visitor_data"]:
            hdr["X-Goog-Visitor-Id"] = cfg["visitor_data"]
        params["header"] = hdr
        return params

    def _ytContext(self):
        hl, gl = self._getDefaultLangAndRegion()
        cfg = self._getYtConfig(fetchIfMissing=True)
        client = {"clientName": "WEB", "clientVersion": cfg["client_version"], "hl": hl, "gl": gl}
        if cfg["visitor_data"]:
            client["visitorData"] = cfg["visitor_data"]
        context = {"client": client}
        if config.plugins.iptvplayer.youtube_safe_search.value:
            context["user"] = {"enableSafetyMode": True}
        return cfg, context

    # ---- signed-in personal feeds (TVHTML5) ------------------------------
    # The OAuth token from the "sign in on TV" flow is only honoured by
    # InnerTube for the TVHTML5 client; the WEB client answers 400 to it. A
    # TVHTML5 browse reply uses the living-room "tile" renderers, not the web
    # ytInitialData shape, so it gets its own small walk here.
    YT_TV_CLIENT_VERSION = "7.20250312.16.00"

    def _tvBrowse(self, browseId, continuation=None):
        auth = self._getAuthHeader()
        if not auth:
            return {}
        hl, gl = self._getDefaultLangAndRegion()
        context = {"client": {"clientName": "TVHTML5", "clientVersion": self.YT_TV_CLIENT_VERSION, "hl": hl, "gl": gl}}
        if config.plugins.iptvplayer.youtube_safe_search.value:
            context["user"] = {"enableSafetyMode": True}
        body = {"context": context}
        if continuation:
            body["continuation"] = continuation
        else:
            body["browseId"] = browseId
        hdr = {"Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version",
               "Origin": "https://www.youtube.com",
               "X-YouTube-Client-Name": "7",
               "X-YouTube-Client-Version": self.YT_TV_CLIENT_VERSION}
        hdr.update(auth)
        http_params = {"header": hdr, "raw_post_data": True}
        sts, data = self.cm.getPage("https://www.youtube.com/youtubei/v1/browse", http_params, json_dumps(body).encode("utf-8"))
        if not sts:
            return {}
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return {}

    def _firstFind(self, node, key):
        return next(self.findKeys(node, key), None)

    def _tvTileToVideo(self, tile):
        videoId = self._firstFind(tile.get("onSelectCommand", {}), "videoId") or ""
        if not videoId:
            return {}
        md = tile.get("metadata", {}).get("tileMetadataRenderer", {})
        title = self._getSimpleText(md.get("title", {}))
        lines = []
        for line in md.get("lines", []):
            parts = [self._getSimpleText(it.get("lineItemRenderer", {}).get("text", {}))
                     for it in line.get("lineRenderer", {}).get("items", [])]
            parts = [p for p in parts if p]
            if parts:
                lines.append(" ".join(parts))
        # first line is the channel name, the rest are views / age / etc.
        owner = ensure_str(lines[0]) if lines else ""
        descLines = lines[1:] if len(lines) > 1 else []
        icon = ""
        thumbs = self._firstFind(tile.get("header", {}), "thumbnails")
        if isinstance(thumbs, list) and thumbs:
            icon = thumbs[-1].get("url", "")
        desc = " | ".join(descLines)
        if owner:
            desc = (desc + "\n" + owner) if desc else owner
        return {
            "type": "video",
            "category": "video",
            "title": self._normalizeText(ensure_str(title)),
            "url": "https://www.youtube.com/watch?v=%s" % videoId,
            "icon": ensure_str(icon),
            "time": "",
            "desc": self._normalizeText(desc),
            "channel": owner,
            "channel_title": owner,
            "video_id": ensure_str(videoId),
        }

    def getTvFeed(self, browseId, page, cItem):
        printDBG("YouTubeParser.getTvFeed browseId[%s] page[%s]" % (browseId, page))
        currList = []
        response = self._tvBrowse(browseId, cItem.get("tv_continuation", "") or None)
        if not response:
            return currList
        seen = set()
        for tile in self.findKeys(response, "tileRenderer"):
            params = self._tvTileToVideo(tile)
            if params and params["video_id"] not in seen:
                seen.add(params["video_id"])
                currList.append(params)
        # "load more" for this list: the token carried by a
        # continuationItemRenderer (ignore unrelated continuationCommands
        # elsewhere in the shell)
        nextToken = ""
        for cir in self.findKeys(response, "continuationItemRenderer"):
            tok = self._firstFind(cir, "token")
            if tok:
                nextToken = tok
        if nextToken and currList:
            currList.append({"type": "more", "category": cItem.get("category", ""), "title": _("Next page"),
                             "page": str(int(page) + 1), "tv_continuation": nextToken})
        return currList

    def _extractEntriesFromBrowse(self, response):
        entries = []
        try:
            tabs = response.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            for tab in tabs:
                content = tab.get("tabRenderer", {}).get("content", {})
                if not content:
                    continue
                rg = content.get("richGridRenderer", {})
                if rg:
                    entries.extend(rg.get("contents", []))
                sl = content.get("sectionListRenderer", {})
                if sl:
                    for c in sl.get("contents", []):
                        ir = c.get("itemSectionRenderer", {})
                        if ir:
                            entries.extend(ir.get("contents", []))
        except Exception:
            printExc()
        return entries

    # CHANNEL LIST PARSER
    def getVideosFromChannelList(self, url, category, page, cItem):
        printDBG("YouTubeParser.getVideosFromChannelList page[%s]" % (page))
        currList = []
        try:
            url = strwithmeta(url)
            self.http_params = self._applyYoutubeHeaders(self.http_params)
            if "post_data" in url.meta:
                http_params = dict(self.http_params)
                http_params["header"]["Content-Type"] = "application/json"
                http_params["raw_post_data"] = True
                http_params = self._applyYoutubeHeaders(http_params)
                sts, data = self.cm.getPage(url, http_params, url.meta["post_data"])
            else:
                sts, data = self.cm.getPage(url, self.http_params)
            if not sts:
                return currList
            if "browse" in url:
                response = json_loads(data)
                rr = {}
                for r in response.get("onResponseReceivedActions", []):
                    if r.get("appendContinuationItemsAction", ""):
                        rr = r
                        break
                if not rr:
                    return []
                r4 = rr["appendContinuationItemsAction"].get("continuationItems", [])
            else:
                # first page of videos
                self.checkSessionToken(data)
                data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
                if len(data2) == 0:
                    data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
                response = json_loads(data2 + "}")
                r4 = self._extractEntriesFromBrowse(response)
            nextPage = ""
            for r5 in r4:
                nP = r5.get("continuationItemRenderer", "")
                lockup = r5.get("richItemRenderer", {}).get("content", {}).get("lockupViewModel", {})
                shortsLockup = r5.get("richItemRenderer", {}).get("content", {}).get("shortsLockupViewModel", {})
                if lockup:
                    params = self.getLockupVideoData(lockup)
                    if params:
                        currList.append(params)
                elif shortsLockup:
                    # the channel's Shorts tab
                    params = self.getShortsLockupData(shortsLockup)
                    if params:
                        currList.append(params)
                else:
                    videoJson = r5.get("richItemRenderer", {})
                    if videoJson:
                        videoJson = videoJson.get("content", {})
                        videoJson = videoJson.get("videoRenderer", "")
                        params = self.getVideoData(videoJson)
                        if params:
                            currList.append(params)
                if nP != "":
                    nextPage = nP
            if nextPage:
                ctoken = nextPage["continuationEndpoint"]["continuationCommand"].get("token", "")
                ctit = nextPage["continuationEndpoint"]["clickTrackingParams"]
                try:
                    label = nextPage["nextContinuationData"]["label"]["runs"][0]["text"]
                except Exception:
                    label = _("Next page")
                # continuation page for channel list
                cfg, context = self._ytContext()
                urlNextPage = "https://www.youtube.com/youtubei/v1/browse?key=" + cfg["api_key"]
                post_data = {"context": context}
                post_data["continuation"] = ctoken
                post_data["context"]["clickTracking"] = {"clickTrackingParams": ctit}
                post_data = json_dumps(post_data).encode("utf-8")
                urlNextPage = strwithmeta(urlNextPage, {"post_data": post_data})
                params = {"type": "more", "image_type": "NEXT", "category": category, "title": label, "page": str(int(page) + 1), "url": ensure_str(urlNextPage), "is_pagination": True}
                if cItem.get("channel_title", ""):
                    params["channel_title"] = cItem.get("channel_title", "")
                elif cItem.get("channel", ""):
                    params["channel"] = cItem.get("channel", "")
                elif cItem.get("title", "") and cItem.get("category", "") == "channel":
                    params["channel_title"] = cItem.get("title", "")
                currList.append(params)
        except Exception:
            printExc()
        return currList

    # SEARCH PARSER
    def getSearchResult(self, pattern, searchType, page, nextPageCategory, sortBy="A", url=""):
        printDBG("YouTubeParser.getSearchResult pattern[%s], searchType[%s], page[%s]" % (pattern, searchType, page))
        currList = []
        try:
            response, url = self._fetchSearchResponse(pattern, searchType, sortBy, url)
            if response is None:
                return []
            # currList is mutated in place from here on (not returned+merged)
            # so a mid-parse exception still keeps whatever was already found,
            # same as when all of this sat inline in one try block.
            self._parseSearchRenderers(response, currList)
            self._appendSearchNextPage(response, url, page, currList)
        except Exception:
            printExc()
        return currList

    def _fetchSearchResponse(self, pattern, searchType, sortBy, url):
        # Returns (response, url) - url is the possibly-rewritten request URL
        # (an old-style nextContinuationData continuation is built from it
        # later via updateQueryUrl). (None, url) on a failed fetch.
        if url:
            # next page / continuation handling
            url = strwithmeta(url)
            if "post_data" in url.meta:
                http_params = dict(self.http_params)
                http_params["header"]["Content-Type"] = "application/json"
                http_params["raw_post_data"] = True
                http_params = self._applyYoutubeHeaders(http_params)
                sts, data = self.cm.getPage(url, http_params, url.meta["post_data"])
            else:
                self.http_params = self._applyYoutubeHeaders(self.http_params)
                sts, data = self.cm.getPage(url, self.http_params, self.postdata)
            if not sts:
                return None, url
            return json_loads(data), url

        # first search request - plain HTML GET of /results + scrape
        # ytInitialData, kept identical to the plain python3 host. An
        # InnerTube POST here reads as more bot-like and got the box
        # walled faster. (safe-search / region only take effect from
        # page 2 on via the continuation context - acceptable.)
        url = "https://www.youtube.com/results?search_query=" + pattern + "&sp="
        if searchType == "video":
            url += "CA%sSAhAB" % sortBy
        if searchType == "channel":
            url += "CA%sSAhAC" % sortBy
        if searchType == "playlist":
            url += "CA%sSAhAD" % sortBy
        if searchType == "live":
            url += "EgJAAQ%253D%253D"
        if searchType == "shorts":
            # filter "Type: Shorts" - the results come as shortsLockupViewModel (_parseSearchRenderers)
            url += "EgIQCQ%253D%253D"
        # minimal headers only (a plain page navigation) - built from the
        # pristine HTTP_HEADER, not the session-accumulated self.http_params,
        # and without _applyYoutubeHeaders' Origin / bootstrap / visitor-id
        # (those read as XHR)
        hdr = dict(self.HTTP_HEADER)
        hdr["Accept-Language"] = self._getAcceptLanguage()
        sts, data = self.cm.getPage(url, {"header": hdr, "return_data": True})
        if not sts:
            return None, url
        self.checkSessionToken(data)
        data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
        if len(data2) == 0:
            data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
        data2 = ensure_str(data2.strip())
        # json simple schema verification and correction
        jsonStarts = data2.count("{")
        jsonEnds = data2.count("}")
        printDBG('YouTubeParser.getSearchResult correcting json string by adding "}" %s time(s) at the end' % (jsonStarts - jsonEnds))
        while jsonEnds < jsonStarts:
            data2 = data2 + "}"
            jsonEnds += 1
        return json_loads(data2), url

    def _parseSearchRenderers(self, response, currList):
        # search videos
        r2 = list(self.findKeys(response, "videoRenderer"))
        printDBG("---------Returned DICT ------------")
        for item in r2:
            printDBG(str(item))
        printDBG("---------------------")
        for item in r2:
            params = self.getVideoData(item)
            if params:
                printDBG(str(params))
                currList.append(params)

        # search Shorts (filter "Type: Shorts", the Shorts shelf of a plain search): marked with the Short icon
        known = set(params.get("video_id", "") for params in currList)
        for item in self.findKeys(response, "shortsLockupViewModel"):
            params = self.getShortsLockupData(item)
            if params and params["video_id"] not in known:
                known.add(params["video_id"])
                currList.append(params)

        # search channels
        r2 = list(self.findKeys(response, "channelRenderer"))
        printDBG("---------------------")
        printDBG(json_dumps(r2))
        printDBG("---------------------")
        for item in r2:
            params = self.getChannelData(item)
            if params:
                printDBG(str(params))
                currList.append(params)

        # search playlists
        r2 = list(self.findKeys(response, "playlistRenderer"))
        printDBG("---------------------")
        printDBG(json_dumps(r2))
        printDBG("---------------------")
        for item in r2:
            params = self.getPlaylistData(item)
            if params:
                printDBG(str(params))
                currList.append(params)

        # New feature: lockupViewModel for playlists and channels in search
        r2 = list(self.findKeys(response, "lockupViewModel"))
        printDBG("---------lockupViewModel in search ------------")
        for item in r2:
            printDBG(str(item)[:500])
        printDBG("---------------------")
        for item in r2:
            self._appendLockupSearchItem(item, currList)

    def _appendLockupSearchItem(self, item, currList):
        content_type = item.get("contentType", "")
        if content_type == "LOCKUP_CONTENT_TYPE_PLAYLIST":
            try:
                playlist_id = item.get("contentId", "")
                title = item.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", "")
                if playlist_id and title:
                    url2 = "https://www.youtube.com/playlist?list=%s" % playlist_id
                    icon = ""
                    try:
                        sources = item.get("contentImage", {}).get("collectionThumbnailViewModel", {}).get("primaryThumbnail", {}).get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
                        if sources:
                            icon = ensure_str(sources[-1].get("url", ""))
                            icon = self._normalizeThumbnailUrl(icon)
                    except Exception:
                        try:
                            sources = item.get("contentImage", {}).get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
                            if sources:
                                icon = ensure_str(sources[-1].get("url", ""))
                                icon = self._normalizeThumbnailUrl(icon)
                        except Exception:
                            pass
                    currList.append({"type": "category", "category": "playlist", "title": title, "url": ensure_str(url2), "icon": icon, "time": "", "desc": ""})
            except Exception:
                printExc()
        elif content_type == "LOCKUP_CONTENT_TYPE_CHANNEL":
            try:
                channel_id = item.get("contentId", "")
                title = item.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", "")
                if channel_id and title:
                    url2 = "https://www.youtube.com/channel/%s" % channel_id
                    icon = ""
                    try:
                        sources = item.get("contentImage", {}).get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
                        if sources:
                            icon = ensure_str(sources[-1].get("url", ""))
                            icon = self._normalizeThumbnailUrl(icon)
                    except Exception:
                        pass
                    currList.append({"type": "category", "category": "channel", "title": title, "url": ensure_str(url2), "icon": icon, "time": "", "desc": ""})
            except Exception:
                printExc()

    def _appendSearchNextPage(self, response, url, page, currList):
        nP = list(self.findKeys(response, "nextContinuationData"))
        nP_new = list(self.findKeys(response, "continuationEndpoint"))
        if nP:
            nextPage = nP[0]
            ctoken = nextPage["continuation"]
            itct = nextPage["clickTrackingParams"]
            try:
                label = nextPage["label"]["runs"][0]["text"]
            except Exception:
                label = _("Next page")
            urlNextPage = self.updateQueryUrl(url, {"pbj": "1", "ctoken": ctoken, "continuation": ctoken, "itct": itct})
            currList.append({"type": "more", "category": "search_next_page", "title": label, "page": str(int(page) + 1), "url": ensure_str(urlNextPage)})
        elif nP_new:
            printDBG("-------------------------------------------------")
            printDBG(json_dumps(nP_new))
            printDBG("-------------------------------------------------")
            nextPage = nP_new[0]
            ctoken = nextPage["continuationCommand"]["token"]
            itct = nextPage["clickTrackingParams"]
            label = _("Next page")
            cfg, context = self._ytContext()
            urlNextPage = "https://www.youtube.com/youtubei/v1/search?key=" + cfg["api_key"]
            post_data = {"context": context}
            post_data["continuation"] = ctoken
            post_data["context"]["clickTracking"] = {"clickTrackingParams": itct}
            post_data = json_dumps(post_data).encode("utf-8")
            urlNextPage = strwithmeta(urlNextPage, {"post_data": post_data})
            currList.append({"type": "more", "category": "search_next_page", "title": label, "page": str(int(page) + 1), "url": ensure_str(urlNextPage)})

    # PLAYLIST API PARSER
    def getVideosApiPlayList(self, url, category, page, cItem):
        printDBG("YouTubeParser.getVideosApiPlayList url[%s]" % url)
        playlistID = self.cm.ph.getSearchGroups(url + "&", "list=([^&]+?)&")[0]
        baseUrl = "https://www.youtube.com/playlist?list=%s" % playlistID
        currList = []
        if baseUrl != "":
            self.http_params = self._applyYoutubeHeaders(self.http_params)
            sts, data = self.cm.getPage(baseUrl, self.http_params)
            if not sts:
                return currList
            data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
            if not data2:
                return currList
            data2 = ensure_str(data2.strip())
            jsonStarts = data2.count("{")
            jsonEnds = data2.count("}")
            while jsonEnds < jsonStarts:
                data2 = data2 + "}"
                jsonEnds += 1
            try:
                response = json_loads(data2)
            except Exception:
                printExc()
                return currList
            try:
                tabs = response.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
                if not tabs:
                    return currList
                section_contents = tabs[0].get("tabRenderer", {}).get("content", {}).get("sectionListRenderer", {}).get("contents", [])
                if not section_contents:
                    return currList
                items = section_contents[0].get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    lockup = item.get("lockupViewModel")
                    if lockup:
                        params = self.getLockupVideoData(lockup)
                        if params:
                            currList.append(params)
            except Exception:
                printExc()
        return currList
