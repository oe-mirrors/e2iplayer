# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for Philizz (philizz.nl, Dutch DJ video megamixes)
#   Static html pages (windows-1252) per series: Yearmix, Decademix, Heroes of the Zer00s,
#   Back to the 80s / 90s, Holland in de Mix, Mashups, Powermix, Tropical Summer.
#   Every mix is a "DialogTitle" table with a video.js <source> MP4 on philizzmedia.nl, an MP3
#   of the audio mix and/or a YouTube embed, plus description, release date and tracklist.
#   Watched flag / downloaded flag / name normalisation ("Back To The 90s - S02E03") / sidecar /
#   INFO (description + tracklist) / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://philizz.nl/"


SECTIONS = [("index.htm", _("Latest")), ("yrmx.htm", "Yearmix"), ("decade.htm", "Decademix"),
            ("hotz.htm", "Heroes of the Zer00s"), ("90s.htm", "Back to the 90s"), ("80s.htm", "Back to the 80s"),
            ("holland.htm", "Holland in de Mix"), ("mashup.htm", "Mashups"), ("powermix.htm", "The Powermix"),
            ("tropical.htm", "Tropical Summer")]


class PhilizzNL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "page_url", "video", "audio", "youtube", "icon")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "philizznl", "cookie": "philizznl.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "convert_charset": False}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("img/favicon.png")
        self.watchedHelper = IPTVWatchedHelper("philizznl")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type", "") in ("video", "audio"):
                url = self.wfNormalizeUrlKey(cItem.get("url", ""))
                return "%s:%s" % (cItem["type"], url) if url else ""
            if isinstance(cItem, dict) and cItem.get("category") == "list_page" and cItem.get("url"):
                # a series page (Back to the 90s ...) is the folder of its mixes
                return "folder:%s" % self.wfNormalizeUrlKey(cItem["url"])
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _decode(self, data):
        # the pages are windows-1252 without a charset header
        try:
            if isPY2():
                try:
                    data.decode("utf-8")
                    return data
                except Exception:
                    return data.decode("cp1252", "replace").encode("utf-8")
            if isinstance(data, bytes):
                try:
                    return data.decode("utf-8")
                except Exception:
                    return data.decode("cp1252", "replace")
        except Exception:
            printExc()
        return data

    def getPage(self, url):
        sts, data = self.cm.getPage(url, dict(self.defaultParams))
        if not sts:
            return False, ""
        return True, self._decode(data)

    def _mediaUrl(self, url):
        url = url.replace("&amp;", "&").strip()
        if url.startswith("http://www.philizzmedia.nl/") or url.startswith("http://www.philizz.nl/"):
            url = "https://" + url[len("http://"):]  # NOSONAR - upgrades http links to https
        return self.getFullUrl(url.replace(" ", "%20"))

    def _niceTitle(self, title):
        if not IsMediaNamingNormalized():
            return title
        m = re.match(r"^(.+?)\s+-\s+(?:Season\s+(\d+)\s+)?Episode\s+(\d+)\s*$", title, re.I)
        if m:
            return "%s - %s" % (m.group(1).strip(), formatSxxExx(m.group(2) or "1", m.group(3)))
        return title

    def _parseBlock(self, block):
        m = re.search(r"^[^>]*>(.*?)</TD>", block, re.S | re.I)
        title = self.cleanHtmlStr(m.group(1)) if m else ""
        body = block.split("</TD></TR>", 1)[-1]
        video = self.cm.ph.getSearchGroups(body, r'<source[^>]+src="([^"]+\.mp4)"', ignoreCase=True)[0]
        audio = self.cm.ph.getSearchGroups(body, r'<audio[^>]+src="([^"]+)"', ignoreCase=True)[0]
        youtube = self.cm.ph.getSearchGroups(body, r'src="((?:https?:)?//www\.youtube(?:-nocookie)?\.com/embed/[^"?]+)')[0]
        poster = self.cm.ph.getSearchGroups(body, r'poster="([^"]+)"')[0]
        if not poster and youtube:
            poster = "https://i.ytimg.com/vi/%s/hqdefault.jpg" % youtube.rstrip("/").rsplit("/", 1)[-1]
        text = body
        for marker in ("</video>", "</iframe>"):
            if marker in text:
                text = text.split(marker, 1)[1]
        text = re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)
        text = text.split("Download Video", 1)[0]
        info = {}
        for key, label in (("Duration", "duration"), ("Releasedate", "released"), ("BPM", "bpm")):
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(text, r"%s</b>\s*:\s*([^<]+)<" % key)[0])
            if not val:
                val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(text, r"%s:\s*([^<]+)<" % key)[0])
            if val:
                info[label] = val
        tracklist = ""
        pos = text.find("Tracklist")
        if pos >= 0:
            tracklist = re.sub(r"\s*\n\s*", "\n", self.cleanHtmlStr(text[pos:].replace("<br>", "\n").replace("<br />", "\n")).strip())
            tracklist = tracklist.split("\n", 1)[-1].strip(" :\n")
            text = text[:pos]
        desc = self.cleanHtmlStr(re.sub(r"<b>\s*(?:Duration|Releasedate|BPM|Resolution|Size [A-Za-z]+)</b>.*?<br>", "", text, flags=re.S))
        desc = re.sub(r"540p preview\..*?Full HD downloads\.", "", desc).strip()
        return {"title": title, "video": video, "audio": audio, "youtube": youtube, "poster": poster,
                "desc": desc, "tracklist": tracklist, "info": info}

    def _slug(self, title):
        return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        for page, label in SECTIONS:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_page", "title": label, "url": self.getFullUrl(page)})
            self.addDir(params)

    def listPage(self, cItem):
        pageUrl = cItem["url"]
        printDBG("PhilizzNL.listPage |%s|" % pageUrl)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return
        seen = set()
        for block in data.split("class=DialogTitle")[1:]:
            item = self._parseBlock(block)
            if not item["title"] or not (item["video"] or item["audio"] or item["youtube"]):
                continue
            key = item["video"] or item["audio"] or item["youtube"]
            if key in seen:
                continue
            seen.add(key)
            descTab = [x for x in (item["info"].get("duration", ""), item["info"].get("released", "")) if x]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "mix", "title": self._niceTitle(item["title"]), "s_title": item["title"],
                           "url": "%s#%s" % (pageUrl.split("#", 1)[0], self._slug(item["title"])), "page_url": pageUrl,
                           "video": self._mediaUrl(item["video"]) if item["video"] else "",
                           "audio": self._mediaUrl(item["audio"]) if item["audio"] else "",
                           "youtube": ("https:" + item["youtube"]) if item["youtube"].startswith("//") else item["youtube"],
                           "icon": self.getFullIconUrl(item["poster"], pageUrl) if item["poster"] else "",
                           "desc": " | ".join(descTab) + ("[/br]" + item["desc"] if item["desc"] else "")})
            if item["video"] or item["youtube"]:
                self.addVideo(params)
            else:
                self.addAudio(params)

    ###################################################
    # links
    ###################################################
    def _findBlock(self, cItem):
        sts, data = self.getPage(cItem.get("page_url") or cItem.get("url", "").split("#", 1)[0])
        if not sts:
            return None
        for block in data.split("class=DialogTitle")[1:]:
            item = self._parseBlock(block)
            if item["title"] and self._slug(item["title"]) == cItem.get("url", "").rsplit("#", 1)[-1]:
                return item
        return None

    def getLinksForVideo(self, cItem):
        printDBG("PhilizzNL.getLinksForVideo [%s]" % cItem.get("url", ""))
        video, audio, youtube = cItem.get("video", ""), cItem.get("audio", ""), cItem.get("youtube", "")
        if not (video or audio or youtube):
            item = self._findBlock(cItem)
            if item:
                video = self._mediaUrl(item["video"]) if item["video"] else ""
                audio = self._mediaUrl(item["audio"]) if item["audio"] else ""
                youtube = item["youtube"]
        meta = {"User-Agent": self.HEADER.get("User-Agent", ""), "Referer": self.MAIN_URL}
        urltab = []
        if video:
            urltab.append({"name": "MP4 video", "url": strwithmeta(video, meta), "need_resolve": 0})
        if youtube:
            urltab.append({"name": "YouTube", "url": "https:" + youtube if youtube.startswith("//") else youtube, "need_resolve": 1})
        if audio:
            urltab.append({"name": "MP3 audio", "url": strwithmeta(audio, meta), "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("PhilizzNL.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("PhilizzNL.getArticleContent [%s]" % cItem.get("url", ""))
        item = self._findBlock(cItem)
        if not item:
            return [{"title": cItem.get("s_title", cItem.get("title", "")), "text": cItem.get("desc", ""),
                     "images": [{"title": "", "url": cItem["icon"]}] if cItem.get("icon") else [], "other_info": {}}]
        text = item["desc"]
        if item["tracklist"]:
            text = "%s\n\n%s:\n%s" % (text, _("Tracklist"), item["tracklist"]) if text else item["tracklist"]
        otherInfo = {}
        for key in ("duration", "released"):
            if item["info"].get(key):
                otherInfo[key] = item["info"][key]
        icon = self.getFullIconUrl(item["poster"], cItem.get("page_url")) if item["poster"] else cItem.get("icon", "")
        return [{"title": item["title"], "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("PhilizzNL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "list_page":
            self.listPage(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, PhilizzNL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("philizznl")

    def withArticleContent(self, cItem):
        return cItem.get("type") in ("video", "audio")
