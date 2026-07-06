# -*- coding: utf-8 -*-
# Last Modified: 01.07.2026 - Change: configurable YouTube display language, configurable channel name for downloaded files, absolute published date in info view
# LOCAL import
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.youtube import YoutubeIE
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsExecutable
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import decorateUrl
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
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
config.plugins.iptvplayer.ytformat = ConfigSelection(default="mp4", choices=[("flv, mp4", "flv, mp4"), ("flv", "flv"), ("mp4", "mp4")])
config.plugins.iptvplayer.ytDefaultformat = ConfigSelection(default="720", choices=[("0", _("the worst")), ("144", "144p"), ("240", "240p"), ("360", "360p"), ("720", "720p"), ("1080", "1080p"), ("1440", "1440p"), ("2160", "2160p"), ("9999", _("the best"))])
config.plugins.iptvplayer.ytUseDF = ConfigYesNo(default=True)
config.plugins.iptvplayer.ytAgeGate = ConfigYesNo(default=False)
config.plugins.iptvplayer.ytVP9 = ConfigYesNo(default=False)
config.plugins.iptvplayer.ytShowDash = ConfigSelection(default="auto", choices=[("auto", _("Auto")), ("true", _("Yes")), ("false", _("No"))])
config.plugins.iptvplayer.ytSortBy = ConfigSelection(default="A", choices=[("A", _("Relevance")), ("I", _("Upload date")), ("M", _("View count")), ("E", _("Rating"))])


class YouTubeParser:

    def __init__(self):
        self.cm = common()
        self.HTTP_HEADER = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20201112.04.01",
            "X-Requested-With": "XMLHttpRequest"
        }
        self.http_params = {"header": self.HTTP_HEADER, "return_data": True}
        self.postdata = {}
        self.sessionToken = ""
        return

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

    @staticmethod
    def isAgeGateAllowed():
        value = config.plugins.iptvplayer.ytAgeGate.value
        printDBG("ALLOW Age-Gate bypass: >> %s" % value)
        return value

    def checkSessionToken(self, data):
        if not self.sessionToken:
            token = self.cm.ph.getSearchGroups(data, '''"XSRF_TOKEN":"([^"]+?)"''')[0]
            if token:
                printDBG("Update session token: %s" % token)
                self.sessionToken = token
                self.postdata = {"session_token": token}

    def getDirectLinks(self, url, formats="flv, mp4", dash=True, dashSepareteList=False, allowVP9=None, allowAgeGate=None):
        printDBG("YouTubeParser.getDirectLinks")
        linksList = []
        try:
            if self.cm.isValidUrl(url) and "/channel/" in url and url.endswith("/live"):
                sts, data = self.cm.getPage(url)
                if sts:
                    videoId = self.cm.ph.getSearchGroups(data, """<meta[^>]+?itemprop=['"]videoId['"][^>]+?content=['"]([^'^"]+?)['"]""")[0]
                    if videoId == "":
                        videoId = self.cm.ph.getSearchGroups(data, r"""['"]REDIRECT_TO_VIDEO['"]\s*\,\s*['"]([^'^"]+?)['"]""")[0]
                    if videoId != "":
                        url = "https://www.youtube.com/watch?v=" + videoId
            linksList = YoutubeIE()._real_extract(url, allowVP9=allowVP9, allowAgeGate=allowAgeGate)
        except Exception:
            printExc()
            if dashSepareteList:
                return [], []
            else:
                return []

        reNum = re.compile("([0-9]+)")
        retHLSList = []
        retList = []
        dashList = []
        # filter dash
        dashAudioLists = []
        dashVideoLists = []
        if dash:
            # separete audio and video links
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
            # sort by quality -> format

            def _key(x):
                if x["format"].startswith(">"):
                    return int(x["format"][1:-1])
                else:
                    return int(ph.search(x["format"], reNum)[0])

            dashAudioLists = sorted(dashAudioLists, key=_key, reverse=True)
            dashVideoLists = sorted(dashVideoLists, key=_key, reverse=True)

        for item in linksList:
            printDBG(">>>>>>>>>>>>>>>>>>>>>")
            printDBG(str(item))
            printDBG("<<<<<<<<<<<<<<<<<<<<<")
            if -1 < formats.find(item["ext"]):
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

        if len(dashAudioLists):
            # use best audio
            for item in dashVideoLists:
                item = dict(item)
                item["url"] = decorateUrl("merge://audio_url|video_url", {"audio_url": dashAudioLists[0]["url"], "video_url": ensure_str(item["url"])})
                dashList.append(item)

        # try to get hls format with alternative method
        if 0 == len(retList):
            try:
                video_id = YoutubeIE()._extract_id(url)
                url = "http://www.youtube.com/watch?v=%s&gl=US&hl=en&has_verified=1" % video_id
                sts, data = self.cm.getPage(url, {"header": {"User-agent": "Mozilla/5.0 (iPad; CPU OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/146.0.7680.38 Mobile/15E148 Safari/604.1"}})
                if sts:
                    data = data.replace('\\"', '"').replace("\\\\\\/", "/")
                    hlsUrl = self.cm.ph.getSearchGroups(data, r'''"hlsvp"\s*:\s*"(https?://[^"]+?)"''')[0]
                    hlsUrl = json_loads('"%s"' % hlsUrl)
                    if self.cm.isValidUrl(hlsUrl):
                        hlsList = getDirectM3U8Playlist(hlsUrl)
                        if len(hlsList):
                            dashList = []
                            for item in hlsList:
                                item["format"] = "%sx%s" % (item.get("width", 0), item.get("height", 0))
                                item["ext"] = "m3u8"
                                item["m3u8"] = True
                                retList.append(item)
            except Exception:
                printExc()
            if 0 == len(retList):
                retList = retHLSList

            if dash:
                try:
                    sts, data = self.cm.getPage(url, {"header": {"User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"}})
                    data = data.replace('\\"', '"').replace("\\\\\\/", "/").replace("\\/", "/")
                    dashUrl = self.cm.ph.getSearchGroups(data, r'''"dashmpd"\s*:\s*"(https?://[^"]+?)"''')[0]
                    dashUrl = json_loads('"%s"' % dashUrl)
                    if "?" not in dashUrl:
                        dashUrl += "?mpd_version=5"
                    else:
                        dashUrl += "&mpd_version=5"
                    printDBG("DASH URL >> [%s]" % dashUrl)
                    if self.cm.isValidUrl(dashUrl):
                        dashList = getMPDLinksWithMeta(dashUrl, checkExt=False)
                        printDBG(dashList)
                        for idx in range(len(dashList)):
                            dashList[idx]["format"] = "%sx%s" % (dashList[idx].get("height", 0), dashList[idx].get("width", 0))
                            dashList[idx]["ext"] = "mpd"
                            dashList[idx]["dash"] = True
                except Exception:
                    printExc()

        for idx in range(len(retList)):
            if retList[idx].get("m3u8", False):
                retList[idx]["url"] = strwithmeta(retList[idx]["url"], {"iptv_m3u8_live_start_index": -30})

        if dashSepareteList:
            return retList, dashList
        else:
            retList.extend(dashList)
            return retList

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

    def _normalizeThumbnailUrl(self, url):
        url = ensure_str(url)
        if not url:
            return ""
        url = url.replace("\\u0026", "&").replace("\\/", "/").strip()
        if url.startswith("//"):
            url = "https:" + url
        if url.startswith("http://yt3.googleusercontent.com/"):
            url = "https://" + url[len("http://") :]
        elif url.startswith("http://yt3.ggpht.com/"):
            url = "https://" + url[len("http://") :]
        elif url.startswith("http://i.ytimg.com/"):
            url = "https://" + url[len("http://") :]
        elif url.startswith("http://"):
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.endswith("googleusercontent.com") or host.endswith("ggpht.com") or host.endswith("ytimg.com"):
                url = "https://" + url[len("http://") :]
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
                t = ensure_str(item.get("text", ""))
                if t:
                    txt.append(t)
        except Exception:
            printExc()
        return "".join(txt).strip()

    def _getSimpleText(self, data):
        try:
            if isinstance(data, dict):
                if "simpleText" in data:
                    return ensure_str(data.get("simpleText", "")).strip()
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
                pass
        if not desc:
            try:
                desc = self._getSimpleText(jsonData.get("descriptionText", {}))
            except Exception:
                pass
        if not desc:
            try:
                desc = ensure_str(jsonData.get("title", {}).get("accessibility", {}).get("accessibilityData", {}).get("label", "")).strip()
            except Exception:
                pass
        return desc

    def _parseIsoDateToShort(self, value):
        try:
            value = ensure_str(value or "").strip()
            if not value:
                return ""
            m = re.search(r"(\d{4}-\d{2}-\d{2})", value)
            if not m:
                return ""
            ts = time.strptime(m.group(1), "%Y-%m-%d")
            return time.strftime("%d.%m.%y", ts)
        except Exception:
            printExc()
        return ""

    def _getWatchPageData(self, videoId):
        if not videoId:
            return {"fullDescription": "", "absolutePublished": "", "infoLine": ""}
        printDBG("YouTubeParser._getWatchPageData START videoId[%s]" % videoId)
        url = "https://www.youtube.com/watch?v=%s" % videoId
        sts, data = self.cm.getPage(url, self.http_params)
        if not sts:
            printDBG("YouTubeParser._getWatchPageData getPage FAILED")
            return {"fullDescription": "", "absolutePublished": "", "infoLine": ""}
        fullDescription = ""
        absolutePublished = ""
        infoLine = ""
        try:
            m = re.search(r'"publishDate":"([^"]+)"', data, re.IGNORECASE)
            if m:
                absolutePublished = self._parseIsoDateToShort(m.group(1))
                if absolutePublished:
                    printDBG("YouTubeParser._getWatchPageData absolutePublished from publishDate[%s]" % absolutePublished)
        except Exception:
            printExc()
        if not absolutePublished:
            try:
                m = re.search(r'"uploadDate":"([^"]+)"', data, re.IGNORECASE)
                if m:
                    absolutePublished = self._parseIsoDateToShort(m.group(1))
                    if absolutePublished:
                        printDBG("YouTubeParser._getWatchPageData absolutePublished from uploadDate[%s]" % absolutePublished)
            except Exception:
                printExc()
        if not absolutePublished:
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
                        absolutePublished = time.strftime("%d.%m.%y", ts)
                        printDBG("YouTubeParser._getWatchPageData absolutePublished from visible text[%s]" % absolutePublished)
                        break
            except Exception:
                printExc()
        try:
            data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
            if len(data2) == 0:
                data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
            data2 = ensure_str(data2.strip())
            jsonStarts = data2.count("{")
            jsonEnds = data2.count("}")
            while jsonEnds < jsonStarts:
                data2 = data2 + "}"
                jsonEnds += 1
            response = json_loads(data2)
            candidates = list(self.findKeys(response, "description"))
            for item in candidates:
                txt = self._getSimpleText(item)
                if txt and len(txt) > len(fullDescription):
                    fullDescription = txt
        except Exception:
            printExc()
        if not fullDescription:
            try:
                m = re.search(r"\"shortDescription\"\s*:\s*\"((?:\\.|[^\"\\])*)\"", data)
                if m:
                    fullDescription = json_loads('"%s"' % m.group(1))
            except Exception:
                printExc()
        if absolutePublished:
            infoLine = absolutePublished
        printDBG("YouTubeParser._getWatchPageData absolutePublished[%s]" % absolutePublished)
        printDBG("YouTubeParser._getWatchPageData fullDescriptionLen[%d]" % len(ensure_str(fullDescription)))
        return {
            "fullDescription": ensure_str(fullDescription).strip(),
            "absolutePublished": ensure_str(absolutePublished).strip(),
            "infoLine": ensure_str(infoLine).strip(),
        }

    def getVideoData(self, videoJson):
        videoId = videoJson.get("videoId", "")
        if not videoId:
            return {}
        url = "http://www.youtube.com/watch?v=%s" % videoId
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
        return {
            "type": "video",
            "category": "video",
            "title": title,
            "url": ensure_str(url),
            "icon": icon,
            "time": time,
            "desc": desc,
            "video_id": ensure_str(videoId),
        }

    def getChannelData(self, chJson):
        chId = chJson.get("channelId", "")
        if chId:
            url = "https://www.youtube.com/channel/%s" % chId
            title = self._getSimpleText(chJson.get("title", {}))
            title = ensure_str(title)
            icon = self.getThumbnailUrl(chJson)
            desc = self._getDescriptionText(chJson)
            return {"type": "category", "category": "channel", "title": title, "url": ensure_str(url), "icon": icon, "time": "", "desc": desc}
        else:
            return {}

    def getPlaylistData(self, plJson):
        plId = plJson.get("playlistId", "")
        if plId:
            url = "https://www.youtube.com/playlist?list=%s" % plId
            title = plJson["title"]["simpleText"]
            icon = self.getThumbnailUrl(plJson)
            videoCount = plJson["videoCount"]
            desc = _("videos: %s") % videoCount
            try:
                by = plJson["longBylineText"]["runs"][0]["text"]
                desc = desc + "\n" + by
            except Exception:
                pass
            return {"type": "category", "category": "playlist", "title": title, "url": ensure_str(url), "icon": icon, "time": "", "desc": desc}
        else:
            return {}

    def getMenuItemData(self, itemJson):
        try:
            title = itemJson["title"]["simpleText"]
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
        url = "http://www.youtube.com/watch?v=%s" % videoId
        try:
            title = lockupJson["metadata"]["lockupMetadataViewModel"]["title"]["content"]
            title = ensure_str(title)
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
                        desc.append(_("Duration: %s") % ensure_str(duration))
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
                    if text:
                        desc.append(ensure_str(text))
                        if not time and ("temu" in text or "godzin" in text or "minut" in text or "sekund" in text or "dni" in text or "tygodni" in text or "miesięcy" in text or "lat" in text or "Transmisja" in text):
                            time = ensure_str(text)
        except Exception:
            pass
        desc_str = " | ".join(desc)
        return {
            "type": "video",
            "category": "video",
            "title": title,
            "url": ensure_str(url),
            "icon": icon,
            "time": time,
            "desc": desc_str,
        }

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
        lang = "en"
        region = "US"
        try:
            selectedLang = config.plugins.iptvplayer.youtube_ui_language.value
            langMap = {"de": "DE", "en": "US"}

            if selectedLang in langMap:
                lang = selectedLang
                region = langMap[selectedLang]
            else:
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
                    region = langMap.get(lang, "US")
        except Exception:
            printExc()
        return lang, region

    def _getAcceptLanguage(self):
        lang, region = self._getDefaultLangAndRegion()
        return "%s-%s,%s;q=0.9" % (lang, region, lang)

    # CHANNEL LIST PARSER
    def getVideosFromChannelList(self, url, category, page, cItem):
        printDBG("YouTubeParser.getVideosFromChannelList page[%s]" % (page))
        currList = []
        try:
            url = strwithmeta(url)
            self.http_params["header"]["Accept-Language"] = self._getAcceptLanguage()

            if "post_data" in url.meta:
                http_params = dict(self.http_params)
                http_params["header"]["Content-Type"] = "application/json"
                http_params["raw_post_data"] = True
                http_params["header"]["Accept-Language"] = self._getAcceptLanguage()
                sts, data = self.cm.getPage(url, http_params, url.meta["post_data"])
            else:
                sts, data = self.cm.getPage(url, self.http_params)

            if sts:
                if "browse" in url:
                    response = json_loads(data)["onResponseReceivedActions"]
                    rr = {}
                    for r in response:
                        if r.get("appendContinuationItemsAction", ""):
                            rr = r
                            break
                    if not rr:
                        return []
                    r1 = rr["appendContinuationItemsAction"]
                    r4 = r1.get("continuationItems", [])
                else:
                    # first page of videos
                    self.checkSessionToken(data)
                    data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
                    if len(data2) == 0:
                        data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
                    response = json_loads(data2 + "}")
                    r1 = response["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
                    r2 = {}
                    for tab in r1:
                        try:
                            if tab["tabRenderer"]["content"]:
                                r2 = tab["tabRenderer"]["content"]
                        except Exception:
                            pass
                        if r2:
                            break
                    r4 = r2["richGridRenderer"]["contents"]

                nextPage = ""
                for r5 in r4:
                    nP = r5.get("continuationItemRenderer", "")
                    lockup = r5.get("richItemRenderer", {}).get("content", {}).get("lockupViewModel", {})
                    if lockup:
                        params = self.getLockupVideoData(lockup)
                        if params:
                            printDBG(str(params))
                            currList.append(params)
                    else:
                        videoJson = r5.get("richItemRenderer", "")
                        if videoJson:
                            videoJson = videoJson.get("content", {})
                            videoJson = videoJson.get("videoRenderer", "")
                            params = self.getVideoData(videoJson)
                            if params:
                                printDBG(str(params))
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

                    hl, gl = self._getDefaultLangAndRegion()

                    urlNextPage = "https://www.youtube.com/youtubei/v1/browse?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
                    post_data = {
                        "context": {
                            "client": {
                                "clientName": "WEB",
                                "clientVersion": "2.20201021.03.00",
                            }
                        },
                    }
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

                    printDBG(str(params))
                    currList.append(params)
        except Exception:
            printExc()
        return currList

    # SEARCH PARSER
    def getSearchResult(self, pattern, searchType, page, nextPageCategory, sortBy="A", url=""):
        printDBG("YouTubeParser.getSearchResult pattern[%s], searchType[%s], page[%s]" % (pattern, searchType, page))
        currList = []
        try:
            nP = {}
            nP_new = {}
            r2 = []
            if url:
                # next page search
                url = strwithmeta(url)
                if "post_data" in url.meta:
                    http_params = dict(self.http_params)
                    http_params["header"]["Content-Type"] = "application/json"
                    http_params["raw_post_data"] = True
                    http_params["header"]["Accept-Language"] = self._getAcceptLanguage()
                    sts, data = self.cm.getPage(url, http_params, url.meta["post_data"])
                else:
                    sts, data = self.cm.getPage(url, self.http_params, self.postdata)
                if sts:
                    response = json_loads(data)
            else:
                url = "https://www.youtube.com/results?search_query=" + pattern + "&sp="
                if searchType == "video":
                    url += "CA%sSAhAB" % sortBy
                if searchType == "channel":
                    url += "CA%sSAhAC" % sortBy
                if searchType == "playlist":
                    url += "CA%sSAhAD" % sortBy
                if searchType == "live":
                    url += "EgJAAQ%253D%253D"
                sts, data = self.cm.getPage(url, self.http_params)
                if sts:
                    self.checkSessionToken(data)
                    data2 = self.cm.ph.getDataBeetwenMarkers(data, 'window["ytInitialData"] =', "};", False)[1]
                    if len(data2) == 0:
                        data2 = self.cm.ph.getDataBeetwenMarkers(data, "var ytInitialData =", "};", False)[1]
                    data2 = ensure_str(data2.strip())  # just cleaning and ensuring we're working with string
                    # json simple schema verification and correction
                    jsonStarts = data2.count("{")
                    jsonEnds = data2.count("}")
                    printDBG('youtuberparser.YouTubeParser().getSearchResult correcting json string by adding "}" %s time(s) at the end' % (jsonStarts - jsonEnds))
                    while jsonEnds < jsonStarts:
                        data2 = data2 + "}"
                        jsonEnds += 1
                    response = json_loads(data2)

            if not sts:
                return []

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
                content_type = item.get("contentType", "")
                if content_type == "LOCKUP_CONTENT_TYPE_PLAYLIST":
                    try:
                        playlist_id = item.get("contentId", "")
                        title = item.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", "")
                        if playlist_id and title:
                            url = "https://www.youtube.com/playlist?list=%s" % playlist_id
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
                            params = {
                                "type": "category",
                                "category": "playlist",
                                "title": title,
                                "url": ensure_str(url),
                                "icon": icon,
                                "time": "",
                                "desc": ""
                            }
                            printDBG(str(params))
                            currList.append(params)
                    except Exception:
                        printExc()
                elif content_type == "LOCKUP_CONTENT_TYPE_CHANNEL":
                    try:
                        channel_id = item.get("contentId", "")
                        title = item.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", "")
                        if channel_id and title:
                            url = "https://www.youtube.com/channel/%s" % channel_id
                            icon = ""
                            try:
                                sources = item.get("contentImage", {}).get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
                                if sources:
                                    icon = ensure_str(sources[-1].get("url", ""))
                                    icon = self._normalizeThumbnailUrl(icon)
                            except Exception:
                                pass
                            params = {
                                "type": "category",
                                "category": "channel",
                                "title": title,
                                "url": ensure_str(url),
                                "icon": icon,
                                "time": "",
                                "desc": ""
                            }
                            printDBG(str(params))
                            currList.append(params)
                    except Exception:
                        printExc()

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
                params = {"type": "more", "category": "search_next_page", "title": label, "page": str(int(page) + 1), "url": ensure_str(urlNextPage)}
                printDBG(str(params))
                currList.append(params)
            elif nP_new:
                printDBG("-------------------------------------------------")
                printDBG(json_dumps(nP_new))
                printDBG("-------------------------------------------------")
                nextPage = nP_new[0]
                ctoken = nextPage["continuationCommand"]["token"]
                itct = nextPage["clickTrackingParams"]
                label = _("Next page")
                hl, gl = self._getDefaultLangAndRegion()
                urlNextPage = "https://www.youtube.com/youtubei/v1/search?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
                post_data = {
                    "context": {
                        "client": {
                            "clientName": "WEB",
                            "clientVersion": "2.20201021.03.00",
                        }
                    },
                }
                post_data["continuation"] = ctoken
                post_data["context"]["clickTracking"] = {"clickTrackingParams": itct}
                post_data = json_dumps(post_data).encode("utf-8")
                urlNextPage = strwithmeta(urlNextPage, {"post_data": post_data})
                params = {"type": "more", "category": "search_next_page", "title": label, "page": str(int(page) + 1), "url": ensure_str(urlNextPage)}
                printDBG(str(params))
                currList.append(params)
        except Exception:
            printExc()
        return currList

    # PLAYLIST API
    def getVideosApiPlayList(self, url, category, page, cItem):
        printDBG("YouTubeParser.getVideosApiPlayList url[%s]" % url)
        playlistID = self.cm.ph.getSearchGroups(url + "&", "list=([^&]+?)&")[0]
        baseUrl = "https://www.youtube.com/playlist?list=%s" % playlistID
        currList = []
        if baseUrl != "":
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
                            printDBG(str(params))
                            currList.append(params)
            except Exception:
                printExc()
        return currList
