# -*- coding: utf-8 -*-
# Last Modified: 06.08.2026 - Centralized watched helper integration incl. favourite hash sync, Custom menu action handling (mark/unmark watched) added - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, ArticleContent, RetHost
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, IsExecutable, printExc, byteify, GetSearchHistoryDir, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvfilehost import IPTVFileHost
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.libs.youtube_oauth import YouTubeOAuth
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecar, buildYoutubeOptions, decorateYoutubeUrl, decorateYoutubeLinkItems
from Plugins.Extensions.IPTVPlayer.libs.youtubeuserlinks import YouTubeUserLinksManager
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper, AsyncMethod, DelegateToMainThread

###################################################

###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
import re
import os
import codecs
from Components.config import config, ConfigDirectory, ConfigYesNo, ConfigSelection, getConfigListEntry

###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.MenuList import MenuList

###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.Sciezkaurllist = ConfigDirectory(default="/hdd/")
config.plugins.iptvplayer.youtube_mkv_chapters = ConfigYesNo(default=True)
config.plugins.iptvplayer.youtube_enigma2_cuts = ConfigYesNo(default=True)
config.plugins.iptvplayer.youtube_download_channel_name = ConfigYesNo(default=True)
# OK-only "action row" for the config screen (see HandleConfigAction); the
# single choice is never really selected, the value carries no meaning.
config.plugins.iptvplayer.youtube_account_action = ConfigSelection(default="fake", choices=[("fake", "  ")])
config.plugins.iptvplayer.youtube_ui_language = ConfigSelection(
    default="system",
    choices=[
        ("system", _("System language")),
        ("ar", "العربية (Arabic)"),
        ("bg", "Български (Bulgarian)"),
        ("cs", "Čeština (Czech)"),
        ("da", "Dansk (Danish)"),
        ("de", _("German")),
        ("el", "Ελληνικά (Greek)"),
        ("en", _("English")),
        ("es", "Español (Spanish)"),
        ("fi", "Suomi (Finnish)"),
        ("fr", "Français (French)"),
        ("he", "עברית (Hebrew)"),
        ("hr", "Hrvatski (Croatian)"),
        ("hu", "Magyar (Hungarian)"),
        ("it", "Italiano (Italian)"),
        ("ja", "日本語 (Japanese)"),
        ("ko", "한국어 (Korean)"),
        ("nl", "Nederlands (Dutch)"),
        ("no", "Norsk (Norwegian)"),
        ("pl", "Polski (Polish)"),
        ("pt", "Português (Portuguese)"),
        ("ro", "Română (Romanian)"),
        ("ru", "Русский (Russian)"),
        ("sk", "Slovenčina (Slovak)"),
        ("sr", "Српски (Serbian)"),
        ("sv", "Svenska (Swedish)"),
        ("tr", "Türkçe (Turkish)"),
        ("uk", "Українська (Ukrainian)"),
        ("zh", "中文 (Chinese)"),
    ],
)


try:
    text_type = unicode
    binary_type = str
    string_types = (basestring,)
    PY2 = True
except NameError:
    text_type = str
    binary_type = bytes
    string_types = (str, bytes)
    PY2 = False


def HandleConfigAction(session, action, callback=None):
    # Called by components/confighost.py when the OK-only account row in
    # GetConfigList() is selected. The device-code sign-in shows a dialog and
    # then polls Google, which blocks - so it runs on a worker thread and
    # drives the UI through MainSessionWrapper, exactly like the host thread
    # does for the same flow from the browse menu.
    def _finish(*args):
        # DelegateToMainThread always calls the wrapped function with the
        # session as its first positional arg (see asynccall.py's
        # CPQItemDelegate/processQueue); the synchronous logout path below
        # calls this with no args at all - accept and ignore either.
        if callable(callback):
            try:
                callback()
            except Exception:
                printExc()

    if action == "youtube_account_logout":
        # Runs synchronously on the main thread (called straight from
        # keyOK()), unlike login below - MainSessionWrapper is only for
        # delegating from a worker thread and raises BaseException if used
        # here, so the session passed in is opened directly instead.
        try:
            YouTubeOAuth.logout()
            session.open(MessageBox, _("Signed out of YouTube."), type=MessageBox.TYPE_INFO, timeout=5)
        except Exception:
            printExc()
        _finish()
        return

    if action == "youtube_account_login":
        def _worker():
            try:
                sessionEx = MainSessionWrapper()
                oauth = YouTubeOAuth()
                dc = oauth.requestDeviceCode()
                if not dc.get("user_code"):
                    sessionEx.open(MessageBox, _("Could not start the YouTube sign-in."), type=MessageBox.TYPE_ERROR, timeout=8)
                    return
                msg = _("To sign in to YouTube:\n\n1. On a phone or computer open:\n     %s\n\n2. Enter this code:\n\n     %s\n\n3. Approve the access, then select OK here.") % (dc["verification_url"], dc["user_code"])
                ret = sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_YESNO, default=True)
                if not (ret and ret[0]):
                    return
                ok = oauth.pollForToken(dc["device_code"], dc["interval"], dc["expires_in"])
                sessionEx.open(MessageBox, _("Signed in to YouTube.") if ok else _("Sign-in was not completed."),
                               type=MessageBox.TYPE_INFO if ok else MessageBox.TYPE_ERROR, timeout=6)
            except Exception:
                printExc()
            finally:
                # _finish() ends up calling confighost.py's _afterConfigAction,
                # which redraws the config-list widget - like every other GUI
                # touch in this worker, that must run on the main thread, not
                # here (same reasoning as MainSessionWrapper above).
                DelegateToMainThread(_finish)()

        # Must run via AsyncMethod, not a bare threading.Thread: pCommon's
        # curl path calls asynccall.SetThreadKillable()/IsThreadTerminated(),
        # which need thread._iptvplayer_ext - only AsyncCall.__call__ sets
        # that on the thread it spawns. Without it every getPage() call on
        # this thread silently fails (sts=False), which is what made the
        # device-code request look like it "could not start".
        AsyncMethod(_worker)()
        return


def GetConfigList():
    optionList = []
    if YouTubeOAuth.isLoggedIn():
        entry = getConfigListEntry(_("Google account") + ":  " + _("signed in") + "  (" + _("select to sign out") + ")", config.plugins.iptvplayer.youtube_account_action)
        entry[1].iptv_host_action = "youtube_account_logout"
    else:
        entry = getConfigListEntry(_("Google account") + ":  " + _("sign in (subscriptions, playlists, age-restricted videos)"), config.plugins.iptvplayer.youtube_account_action)
        entry[1].iptv_host_action = "youtube_account_login"
    optionList.append(entry)
    optionList.append(getConfigListEntry(_("Sort by:"), config.plugins.iptvplayer.ytSortBy))
    optionList.append(getConfigListEntry(_("Search results region:"), config.plugins.iptvplayer.youtube_search_region))
    optionList.append(getConfigListEntry(_("Safe search (restricted mode):"), config.plugins.iptvplayer.youtube_safe_search))
    optionList.append(getConfigListEntry(_("Path to ytlist.txt, urllist.txt"), config.plugins.iptvplayer.Sciezkaurllist))
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.ytDefaultformat))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.ytUseDF))
    optionList.append(getConfigListEntry(_("Display language:"), config.plugins.iptvplayer.youtube_ui_language))
    optionList.append(getConfigListEntry(_("Add channel name to downloaded file") + ":", config.plugins.iptvplayer.youtube_download_channel_name))
    optionList.append(getConfigListEntry(_("Create MKV with chapter marks from description") + ":", config.plugins.iptvplayer.youtube_mkv_chapters))
    optionList.append(getConfigListEntry(_("Create Enigma2 .cuts chapter marks") + ":", config.plugins.iptvplayer.youtube_enigma2_cuts))
    # "Allow watched flag to be set" / "The color of the viewed item" / "Create sidecar
    # files" now live in the global E2iPlayer settings (components/iptvconfigmenu.py),
    # not per-host
    # temporary, the ffmpeg must be in right version to be able to merge file without transcoding
    # checking should be moved to setup
    if IsExecutable("ffmpeg"):
        optionList.append(getConfigListEntry(_("Allow dash format:"), config.plugins.iptvplayer.ytShowDash))
    if config.plugins.iptvplayer.ytShowDash.value != "false":
        optionList.append(getConfigListEntry(_("Allow VP9 codec:"), config.plugins.iptvplayer.ytVP9))
    return optionList


###################################################


def gettytul():
    return "https://youtube.com/"


class YouTubeInfo(Screen):

    skin = """
        <screen name="YouTubeInfo" position="center,center" size="1100,650" title="YouTube info">
            <widget name="title" position="20,20" size="1060,80" font="Regular;32" halign="left" valign="center" />
            <widget name="meta" position="20,105" size="1060,60" font="Regular;24" halign="left" valign="center" />
            <widget name="status" position="20,165" size="1060,35" font="Regular;22" halign="left" valign="center" />
            <widget name="text" position="20,205" size="1060,420" font="Regular;26" />
        </screen>
    """

    def __init__(self, session, host, cItem):
        Screen.__init__(self, session)
        self.host = host
        self.cItem = cItem
        self.videoId = ""
        self.fullDescriptionLoaded = False
        self.watchDataLoaded = False

        self["title"] = Label("")
        self["meta"] = Label("")
        self["status"] = Label("")
        self["text"] = ScrollLabel("")

        self["actions"] = ActionMap(
            ["WizardActions", "DirectionActions", "ColorActions"],
            {
                "back": self.keyBack,
                "red": self.keyBack,
                "ok": self.keyOK,
                "up": self.keyUp,
                "down": self.keyDown,
            },
            -1,
        )

        self.onLayoutFinish.append(self.onStart)

    def onStart(self):
        self._fillBasicData()
        self.loadWatchData()

    def _cleanText(self, text):
        text = str(text or "")
        return text.replace("[/br]", "\n")

    def _setMeta(self, published=""):
        meta = []
        if published:
            meta.append(published)
        elif self.cItem.get("time", ""):
            meta.append(self.cItem.get("time", ""))

        if self.videoId:
            meta.append("videoId: %s" % self.videoId)

        self["meta"].setText(" | ".join(meta))

    def _fillBasicData(self):
        self.videoId = self.host._getVideoIdFromItem(self.cItem)
        title = self.cItem.get("title", "")
        desc = self.cItem.get("desc", "")

        self["title"].setText(title)
        self._setMeta()
        self["text"].setText(self._cleanText(desc))
        self["status"].setText(_("Loading watch data...") if self.videoId else _("No video ID available"))

    def loadWatchData(self):
        if not self.videoId:
            return

        try:
            watchData = self.host.ytp._getWatchPageData(self.videoId)
            self.watchDataLoaded = True

            absolutePublished = watchData.get("absolutePublished", "")
            fullDesc = watchData.get("fullDescription", "")
            shortDesc = self.cItem.get("desc", "")

            if absolutePublished:
                self.cItem["time"] = absolutePublished
                self._setMeta(absolutePublished)
                printDBG("YouTubeInfo.loadWatchData absolutePublished[%s]" % absolutePublished)
            else:
                self._setMeta()

            if fullDesc:
                self["text"].setText(self._cleanText(fullDesc))
                self["status"].setText(_("Full description loaded"))
                self.fullDescriptionLoaded = True
                printDBG("YouTubeInfo.loadWatchData fullDescriptionLen[%d]" % len(fullDesc))
            else:
                self["text"].setText(self._cleanText(shortDesc))
                self["status"].setText(_("Full description not available"))
                printDBG("YouTubeInfo.loadWatchData fullDescription EMPTY")

        except Exception:
            printExc()
            self["status"].setText(_("Error while loading watch data"))

    def keyOK(self):
        if not self.watchDataLoaded:
            self.loadWatchData()

    def keyBack(self):
        self.close()

    def keyUp(self):
        self["text"].pageUp()

    def keyDown(self):
        self["text"].pageDown()


class Youtube(CBaseHostClass):

    def __init__(self):
        printDBG("Youtube.__init__")
        CBaseHostClass.__init__(self, {"history": "ytlist", "cookie": "youtube.cookie"})
        self.UTLIST_FILE = "ytlist.txt"
        self.DEFAULT_ICON_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/YouTube_2024.svg/960px-YouTube_2024.svg.png"
        self.MAIN_GROUPED_TAB = [{"category": "from_file", "title": _("User links"), "desc": _("User links stored in the ytlist.txt file.")}, {"category": "feeds", "title": _("Trending"), "desc": _("Browse youtube trending feeds")}]

        self.SEARCH_TYPES = [(_("Video"), "video"), (_("Channel"), "channel"), (_("Playlist"), "playlist"), (_("Movie"), "movie"), (_("Live"), "live")]  # (_("Program"), "show"),... # (_("traylist"), "traylist"),
        self.ytp = YouTubeParser()
        self.currFileHost = None
        self.userLinks = YouTubeUserLinksManager(self._getUserLinksPath, self._getCategory, self._extractChannelNameFromItem)
        self.watchedHelper = IPTVWatchedHelper('youtube')

    def _getCategory(self, url):
        # printDBG("Youtube._getCategory")
        if "/playlist?list=" in url:
            category = "playlist"
        elif url.split("?")[0].endswith("/playlists"):
            category = "playlists"
        elif None is not re.search(r"/watch\?v=[^\&]+?\&list=", url):
            category = "traylist"
        elif "user/" in url or (("channel/" in url or "/c/" in url or "/@" in url) and not url.endswith("/live")):
            category = "channel"
        else:
            category = "video"
        return category

    def _extractVideoId(self, url):
        printDBG("Youtube._extractVideoId")
        videoId = ""
        try:
            url = str(url)

            match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
            if match is not None:
                videoId = match.group(1)

            if not videoId:
                match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
                if match is not None:
                    videoId = match.group(1)
        except Exception:
            printExc()
        return videoId

    def _getVideoIdFromItem(self, cItem):
        # printDBG("Youtube._getVideoIdFromItem")
        videoId = ""
        try:
            videoId = cItem.get("video_id", "")
        except Exception:
            printExc()

        if not videoId:
            try:
                videoId = self._extractVideoId(cItem.get("url", ""))
            except Exception:
                printExc()
        return videoId

    def _getYouTubeInfoText(self, cItem):
        printDBG("Youtube._getYouTubeInfoText")
        text = cItem.get("desc", "")
        if not text:
            text = cItem.get("title", "")
        return text

    def _extractChannelNameFromItem(self, item, defaultChannel=""):
        invalidTitles = [_("Next page"), "Next page", "Nächste Seite"]

        try:
            if item.get("is_pagination", False):
                return ""
        except Exception:
            printExc()

        try:
            if item.get("type", "") == "more" or item.get("image_type", "") == "NEXT":
                return ""
        except Exception:
            printExc()

        try:
            title = item.get("title", "") or ""
            if isinstance(title, str):
                try:
                    title = title.decode("utf-8")
                except Exception:
                    pass
            title = title.strip()
            if title in invalidTitles:
                return ""
        except Exception:
            printExc()

        try:
            channel = self._cleanChannelCandidate(item.get("channel", ""), invalidTitles)
            if channel:
                return channel
        except Exception:
            printExc()

        try:
            channel = self._cleanChannelCandidate(defaultChannel or "", invalidTitles)
            if channel:
                return channel
        except Exception:
            printExc()

        try:
            desc = item.get("desc", "") or ""
            if isinstance(desc, str):
                try:
                    desc = desc.decode("utf-8")
                except Exception:
                    pass
            desc = re.sub(r"[\x00-\x1f]+", " ", desc)
            m = re.search(r"Channel\s*:\s*([^\n\r]+)", desc, re.IGNORECASE)
            if m:
                ch = m.group(1).strip()
                if ch not in invalidTitles:
                    return ch
        except Exception:
            printExc()

        return ""

    def _cleanChannelCandidate(self, value, invalidTitles):
        # value may be a PY2 byte-string that needs decoding to text; on PY3
        # str has no .decode() so this quietly no-ops (AttributeError caught)
        # - same dance the title/desc checks around this do.
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = value.decode("utf-8")
            except Exception:
                pass
        value = value.strip()
        return value if (value and value not in invalidTitles) else ""

    def _injectChannelNameToItem(self, item, defaultChannel=""):
        try:
            if item.get("is_pagination", False):
                return

            if item.get("type", "") == "more":
                return

            if item.get("image_type", "") == "NEXT":
                return

            title = item.get("title", "") or ""
            if isinstance(title, str):
                try:
                    title = title.decode("utf-8")
                except Exception:
                    pass
            title = title.strip()

            if title in [_("Next page"), "Next page", "Nächste Seite"]:
                return

            channel = self._extractChannelNameFromItem(item, defaultChannel)
            if not channel:
                return

            if not item.get("channel", ""):
                item["channel"] = channel
        except Exception:
            printExc()

    def _injectChannelNameToItems(self, itemList, defaultChannel=""):
        printDBG("Youtube._injectChannelNameToItems count[%d]" % len(itemList))
        try:
            for item in itemList:
                self._injectChannelNameToItem(item, defaultChannel)
        except Exception:
            printExc()

    def _getUserLinksPath(self):
        return os.path.join(config.plugins.iptvplayer.Sciezkaurllist.value, self.UTLIST_FILE)

    def _getWatchedKeyForItem(self, cItem):
        # printDBG("Youtube._getWatchedKeyForItem")
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("is_pagination", False):
                return ""
            if cItem.get("type", "") == "more" or cItem.get("image_type", "") == "NEXT":
                return ""
            category = cItem.get("category", "")
            if category not in ["video", "movie", "traylist"] and cItem.get("type", "") not in ["video", "audio"]:
                if "watch?v=" not in cItem.get("url", "") and not cItem.get("video_id", ""):
                    return ""
            videoId = self._getVideoIdFromItem(cItem)
            if videoId:
                return "videoid:%s" % videoId
            url = str(cItem.get("url", "") or "").strip().replace("&amp;", "&")
            if url:
                return "url:%s" % url
        except Exception:
            printExc()
        return ""

    def readUserLinks(self):
        return self.userLinks.read()

    def deleteUserLink(self, itemToDelete):
        return self.userLinks.delete(itemToDelete)

    def selectUserLinkTargetGroup(self, session, item, callback):
        return self.userLinks.selectTargetGroup(session, item, callback)

    def editUserLinkRaw(self, session, item, callback):
        return self.userLinks.editRaw(session, item, callback)

    def openAddCurrentItemToUserLinks(self, session, cItem=None, callback=None):
        if cItem is None:
            cItem = self.currItem
        return self.userLinks.openAddCurrentItem(session, cItem, callback)

    def openUserLinksEditor(self, session):
        return self.userLinks.openEditor(session)

    def _getSidecarData(self, cItem):
        printDBG("Youtube._getSidecarData")
        sidecarTxt = ""
        sidecarImg = ""

        try:
            article = self.getArticleContent(cItem)
            if article and isinstance(article, list):
                articleItem = article[0]
                try:
                    sidecarTxt = articleItem.get("text", "")
                except Exception:
                    try:
                        sidecarTxt = articleItem.text
                    except Exception:
                        sidecarTxt = ""

                try:
                    images = articleItem.get("images", [])
                except Exception:
                    try:
                        images = articleItem.images
                    except Exception:
                        images = []

                if images and images[0].get("url"):
                    sidecarImg = images[0].get("url")
        except Exception:
            printExc("Youtube.getArticleContent for sidecar failed")

        if not sidecarTxt:
            sidecarTxt = cItem.get("desc", "")
        if not sidecarImg:
            sidecarImg = cItem.get("icon", "")

        return sidecarTxt, sidecarImg

    def _applySidecarMetaToUrl(self, url, sidecarTxt, sidecarImg, sidecarEnabled, mkvChaptersEnabled=False, cutsChaptersEnabled=False, channelName=""):
        try:
            sidecar = buildSidecar(sidecarEnabled, sidecarTxt, sidecarImg)
            youtubeOptions = buildYoutubeOptions(mkvChaptersEnabled, cutsChaptersEnabled, channelName)
            return decorateYoutubeUrl(url, sidecar=sidecar, youtubeOptions=youtubeOptions)
        except Exception:
            printExc()
            return url

    def _addSidecarMetaToUrlTab(self, urlTab, sidecarTxt, sidecarImg, sidecarEnabled, mkvChaptersEnabled=False, cutsChaptersEnabled=False, channelName=""):
        printDBG("Youtube._addSidecarMetaToUrlTab count[%d]" % len(urlTab))
        try:
            sidecar = buildSidecar(sidecarEnabled, sidecarTxt, sidecarImg)
            youtubeOptions = buildYoutubeOptions(mkvChaptersEnabled, cutsChaptersEnabled, channelName)
            return decorateYoutubeLinkItems(urlTab, sidecar=sidecar, youtubeOptions=youtubeOptions)
        except Exception:
            printExc()
            return urlTab

    def listMainMenu(self):
        printDBG("Youtube.listsMainMenu")
        tab = list(self.MAIN_GROUPED_TAB)
        # Signing in / out lives in the host configuration screen now
        # (GetConfigList / HandleConfigAction), not in this browse list.
        if YouTubeOAuth.isLoggedIn():
            tab += [
                {"category": "auth_feed", "feed": "subscriptions", "title": _("My subscriptions"), "desc": _("Latest videos from the channels you are subscribed to.")},
                {"category": "auth_feed", "feed": "watch_later", "title": _("Watch later"), "desc": _("Your 'Watch later' playlist.")},
                {"category": "auth_feed", "feed": "liked", "title": _("Liked videos"), "desc": _("Videos you have liked.")},
                {"category": "auth_feed", "feed": "history", "title": _("Watch history"), "desc": _("Videos you have recently watched.")},
            ]
        tab += self.searchItems()
        for item in tab:
            params = {"name": "category"}
            params.update(item)
            self.addDir(params)

    def listAuthFeed(self, cItem):
        printDBG("Youtube.listAuthFeed [%s]" % cItem)
        feed = cItem.get("feed", "")
        page = cItem.get("page", "1")
        # The signed-in feeds only answer to the TVHTML5 InnerTube client, which
        # returns the living-room "tile" layout - getTvFeed() walks that.
        browseId = {"subscriptions": "FEsubscriptions",
                    "watch_later": "VLWL",
                    "liked": "VLLL",
                    "history": "FEhistory"}.get(feed, "")
        if not browseId:
            return
        tmp = self.ytp.getTvFeed(browseId, page, cItem)
        if not tmp:
            self.addDir({"name": "category", "category": "no_feed", "title": _("(nothing here yet)"),
                         "desc": _("This feed is empty, or the YouTube sign-in has expired - sign out and in again.")})
            return
        self._injectChannelNameToItems(tmp, cItem.get("channel_title", ""))
        self.watchedHelper.updateHostListFlags(self, tmp, self._getWatchedKeyForItem)
        for item in tmp:
            item.update({"name": "category"})
            if item.get("type", "") == "more":
                item.update({"category": "auth_feed", "feed": feed, "title": _("Next page")})
                self.addMore(item)
            elif item.get("type", "") == "video":
                self.addVideo(item)
            else:
                self.addDir(item)

    def listCategory(self, cItem, searchMode=False):
        printDBG("Youtube.listCategory cItem[%s]" % cItem)

        sortList = True
        filespath = config.plugins.iptvplayer.Sciezkaurllist.value
        groupList = True
        if "sub_file_category" not in cItem:
            self.currFileHost = IPTVFileHost()
            self.currFileHost.addFile(filespath + self.UTLIST_FILE, encoding="utf-8")
            tmpList = self.currFileHost.getGroups(sortList)
            if 0 < len(tmpList):
                params = dict(cItem)
                params.update({"sub_file_category": "all", "group": "all", "title": _("--All--")})
                self.addDir(params)
                for item in tmpList:
                    if "" == item:
                        title = _("--Other--")
                    else:
                        title = item
                    params = dict(cItem)
                    params.update({"sub_file_category": "group", "title": title, "group": item})
                    self.addDir(params)
        else:
            if "all" == cItem["sub_file_category"]:
                tmpList = self.currFileHost.getAllItems(sortList)
                for item in tmpList:
                    params = dict(cItem)
                    category = self._getCategory(item["url"])
                    params.update({"good_for_fav": True, "title": item["full_title"], "url": item["url"], "desc": item["url"], "category": category})
                    self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
                    if "video" == category:
                        self.addVideo(params)
                    elif "more" == category:
                        params.update({"image_type": "NEXT"})
                        self.addMore(params)
                    else:
                        self.addDir(params)
            elif "group" == cItem["sub_file_category"]:
                tmpList = self.currFileHost.getItemsInGroup(cItem["group"], sortList)
                for item in tmpList:
                    if "" == item["title_in_group"]:
                        title = item["full_title"]
                    else:
                        title = item["title_in_group"]
                    params = dict(cItem)
                    category = self._getCategory(item["url"])
                    params.update({"good_for_fav": True, "title": title, "url": item["url"], "desc": item["url"], "category": category})
                    self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
                    if "video" == category:
                        self.addVideo(params)
                    elif "more" == category:
                        params.update({"image_type": "NEXT"})
                        self.addMore(params)
                    else:
                        self.addDir(params)

    def listItems(self, cItem):
        printDBG("Youtube.listItems cItem[%s]" % (cItem))
        category = cItem.get("category", "")
        url = cItem.get("url", "")
        page = cItem.get("page", "1")

        if "playlists" == category:
            self.currList = self.ytp.getListPlaylistsItems(url, category, page, cItem)

        for idx in range(len(self.currList)):
            if self.currList[idx]["category"] in ["channel", "playlist", "movie", "traylist"]:
                self.currList[idx]["good_for_fav"] = True

    def listFeeds(self, cItem):
        printDBG("Youtube.listFeeds cItem[%s]" % cItem)

        if cItem.get("category", "") == "feeds_video":
            if cItem.get("pattern", "") != "":
                self._listSearchBasedFeed(cItem)
            else:
                self._listLegacyFeedUrl(cItem)
            return

        self._listFeedCategories()

    def _listSearchBasedFeed(self, cItem):
        # A New Approach: Search-Based Feeds with Pagination
        pattern = cItem.get("pattern", "")
        page = cItem.get("page", "1")
        url = cItem.get("url", "")
        search_type = cItem.get("search_type", "")
        tmpList = self.ytp.getSearchResult(urllib_quote_plus(pattern), search_type if search_type else "video", page, "search_next_page", config.plugins.iptvplayer.ytSortBy.value, url)

        currentChannel = cItem.get("channel", "")
        currentContextTitle = cItem.get("context_title", "")

        for item in tmpList:
            item.update({"name": "category"})

            if item.get("type", "") == "video":
                if currentChannel and not item.get("channel", ""):
                    item["channel"] = currentChannel
                elif currentContextTitle and not item.get("context_title", ""):
                    item["context_title"] = currentContextTitle
                self._injectChannelNameToItem(item)
                self.addVideo(item)
            elif item.get("type", "") == "more":
                item.update(
                    {
                        "title": _("Next page"),
                        "image_type": "NEXT",
                        "category": "feeds_video",
                        "pattern": pattern,
                        "search_type": search_type if search_type else "video",
                    }
                )
                if currentChannel:
                    item["channel"] = currentChannel
                if currentContextTitle:
                    item["context_title"] = currentContextTitle
                self.addMore(item)
            else:
                if currentChannel and not item.get("channel", ""):
                    item["channel"] = currentChannel
                elif currentContextTitle and not item.get("context_title", ""):
                    item["context_title"] = currentContextTitle
                if item.get("category", "") in ["channel", "playlist", "movie", "traylist"]:
                    item["good_for_fav"] = True
                self.addDir(item)

    def _listLegacyFeedUrl(self, cItem):
        # Legacy approach: retain existing behavior for fixed URLs
        sts, data = self.cm.getPage(cItem["url"])
        data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, "videoRenderer", "watchEndpoint")
        for item in data2:
            url = "https://www.youtube.com/watch?v=" + self.cm.ph.getDataBeetwenMarkers(item, 'videoId":"', '","thumbnail":', False)[1]
            icon = self.cm.ph.getDataBeetwenMarkers(item, '},{"url":"', "==", False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(item, '"title":{"runs":[{"text":"', '"}]', False)[1]
            desc = E2ColoR("yellow") + _("Channel") + E2ColoR("white") + ":" + self.cm.ph.getDataBeetwenMarkers(item, 'longBylineText":{"runs":[{"text":"', '","navigationEndpoint"', False)[1] + "\n"
            desc += E2ColoR("yellow") + _("Release") + E2ColoR("white") + ":" + self.cm.ph.getDataBeetwenMarkers(item, '"publishedTimeText":{"simpleText":"', '"},"lengthText":', False)[1] + "\n"
            desc += E2ColoR("yellow") + _("Duration") + E2ColoR("white") + ":" + self.cm.ph.getDataBeetwenMarkers(item, '"lengthText":{"accessibility":{"accessibilityData":{"label":"', '"}},"simpleText":', False)[1] + "\n"
            desc += E2ColoR("yellow") + _("Views") + E2ColoR("white") + ":" + self.cm.ph.getDataBeetwenMarkers(item, '"viewCountText":{"simpleText":"', '"},"navigationEndpoint":', False)[1]
            params = {"title": title, "url": url, "icon": icon, "desc": desc, "video_id": self._extractVideoId(url)}
            self._injectChannelNameToItem(params)
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)

    def _listFeedCategories(self):
        feeds = [
            (_("Movies"), "movies", "video"),
            (_("Music"), "music", "video"),
            (_("Games"), "games", "video"),
            (_("Live"), "live", "live"),
            (_("News"), "news", "video"),
            (_("Shorts"), "shorts", "video"),
            (_("Podcasts"), "podcasts", "video"),
            (_("Sport"), "sport", "video"),
            (_("Knowledge"), "knowledge", "video"),
        ]

        for title, pattern, search_type in feeds:
            params = {"name": "category", "category": "feeds_video", "title": title, "pattern": pattern, "search_type": search_type, "page": "1", "url": ""}
            self.addDir(params)

    def getVideos(self, cItem):
        printDBG("Youtube.getVideos cItem[%s]" % (cItem))

        category = cItem.get("category", "")
        url = strwithmeta(cItem.get("url", ""))
        page = cItem.get("page", "1")
        defaultChannel = cItem.get("channel_title", cItem.get("channel", cItem.get("title", "")))

        if "channel" == category:
            if "browse" not in url and ("ctoken" not in url):
                if url.endswith("/videos"):
                    url = url + "?flow=list&view=0&sort=dd"
                else:
                    url = url + "/videos?flow=list&view=0&sort=dd"

                tmp = self.ytp.getVideosFromChannelList(url, category, page, cItem)
                if len(tmp) > 0:
                    self._injectChannelNameToItems(tmp, defaultChannel)
                    self.watchedHelper.updateHostListFlags(self, tmp, self._getWatchedKeyForItem)
                    params = {"good_for_fav": False, "category": "sub_items", "title": _("Videos"), "sub_items": tmp}
                    self.addDir(params)

                url = url.replace("videos", "streams")
                tmp = self.ytp.getVideosFromChannelList(url, category, page, cItem)
                if len(tmp) > 0:
                    self._injectChannelNameToItems(tmp, defaultChannel)
                    self.watchedHelper.updateHostListFlags(self, tmp, self._getWatchedKeyForItem)
                    params = {"good_for_fav": False, "category": "sub_items", "title": _("Live streams"), "sub_items": tmp}
                    self.addDir(params)
            else:
                self.currList = self.ytp.getVideosFromChannelList(url, category, page, cItem)
                self._injectChannelNameToItems(self.currList, defaultChannel)
                self.watchedHelper.updateHostListFlags(self, self.currList, self._getWatchedKeyForItem)
        elif "playlist" == category:
            self.currList = self.ytp.getVideosApiPlayList(url, category, page, cItem)
        elif "traylist" == category:
            self.currList = self.ytp.getVideosFromTraylist(url, category, page, cItem)
        else:
            printDBG("YTlist.getVideos Error unknown category[%s]" % category)

    def listSearchResult(self, cItem, pattern, searchType):
        page = cItem.get("page", "1")
        url = cItem.get("url", "")

        if url:
            printDBG("URL search -----------> %s" % url)
            tmpList = self.ytp.getSearchResult(urllib_quote_plus(pattern), searchType, page, "search", config.plugins.iptvplayer.ytSortBy.value, url)
        else:
            tmpList = self.ytp.getSearchResult(urllib_quote_plus(pattern), searchType, page, "search", config.plugins.iptvplayer.ytSortBy.value)

        for item in tmpList:
            item.update({"name": "category"})
            if "video" == item["type"]:
                self.watchedHelper.updateHostItemFlag(self, item, self._getWatchedKeyForItem)
                self.addVideo(item)
            elif "more" == item["type"]:
                item.update({"image_type": "NEXT"})
                self.addMore(item)
            else:
                if item["category"] in ["channel", "playlist", "movie", "traylist"]:
                    item["good_for_fav"] = True
                self.addDir(item)

    def getLinksForVideo(self, cItem):
        printDBG("Youtube.getLinksForVideo cItem[%s]" % cItem)

        sidecarEnabled = IsSidecarEnabled()
        mkvChaptersEnabled = config.plugins.iptvplayer.youtube_mkv_chapters.value
        cutsChaptersEnabled = config.plugins.iptvplayer.youtube_enigma2_cuts.value
        downloadChannelNameEnabled = config.plugins.iptvplayer.youtube_download_channel_name.value
        sidecarTxt = ""
        sidecarImg = ""
        channelName = ""

        workItem = dict(cItem)

        # NOTE: marking the item "started" happens later, in iptvplayerwidget.py's
        # playVideo() - not here. This method resolves links for both actually
        # streaming AND downloading, and can also fail/return nothing, so marking
        # here would (and used to) tag failed attempts and downloads as "started" too.

        try:
            if workItem.get("is_pagination", False) or workItem.get("type", "") == "more" or workItem.get("image_type", "") == "NEXT":
                printDBG("Youtube.getLinksForVideo skip pagination item")
                return []
        except Exception:
            printExc()

        if sidecarEnabled or mkvChaptersEnabled or cutsChaptersEnabled:
            sidecarTxt, sidecarImg = self._getSidecarData(workItem)

        if downloadChannelNameEnabled:
            printDBG("Youtube.getLinksForVideo channel field before extract[%s]" % workItem.get("channel", ""))
            channelName = self._extractChannelNameFromItem(workItem)
            printDBG("Youtube.getLinksForVideo channelName extracted[%s]" % channelName)

            if not channelName:
                channelName = workItem.get("channel", "") or ""
                if isinstance(channelName, str):
                    try:
                        channelName = channelName.decode("utf-8")
                    except Exception:
                        pass

            if channelName in [_("Next page"), "Next page", "Nächste Seite"]:
                channelName = ""

        try:
            workItem["url"] = self._applySidecarMetaToUrl(workItem.get("url", ""), sidecarTxt, sidecarImg, sidecarEnabled, mkvChaptersEnabled, cutsChaptersEnabled, channelName)
        except Exception:
            printExc("Youtube.getLinksForVideo apply sidecar/meta to source url failed")

        urlTab = self.up.getVideoLinkExt(workItem["url"])
        urlTab = self._addSidecarMetaToUrlTab(urlTab, sidecarTxt, sidecarImg, sidecarEnabled, mkvChaptersEnabled, cutsChaptersEnabled, channelName)

        if config.plugins.iptvplayer.ytUseDF.value and 0 < len(urlTab):
            return [urlTab[0]]
        return urlTab

    def _replacePublishedLineInDesc(self, text, absolutePublished):
        printDBG("Youtube._replacePublishedLineInDesc")
        try:
            text = str(text or "")
            absolutePublished = str(absolutePublished or "").strip()

            if not text or not absolutePublished:
                return text

            releaseLine = _("Release") + ": " + absolutePublished
            out = self._replaceOrInsertReleaseLine(text.split("\n"), releaseLine)
            return "\n".join(out)

        except Exception:
            printExc()

        return text

    def _replaceOrInsertReleaseLine(self, lines, releaseLine):
        # Swaps the first line that looks like a "published"/"streamed"
        # line for releaseLine; if none of the lines qualify, releaseLine
        # is inserted at the top instead.
        releaseLabels = [
            _("Release"),
            _("Published"),
            _("Streamed"),
            "Release",
            "Published",
            "Streamed",
            "Veröffentlicht",
            "Premiere",
            "Live",
        ]
        relPattern = re.compile(r"(" r"\b\d+\s+(second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago\b|" r"\bvor\s+\d+\s+(sekunde|sekunden|minute|minuten|stunde|stunden|tag|tage|woche|wochen|monat|monate|jahr|jahre)\b|" r"\b\d+\s+(sekunde|sekunden|minute|minuten|stunde|stunden|tag|tage|woche|wochen|monat|monate|jahr|jahre)\s+zuvor\b" r")", re.IGNORECASE)
        streamedPattern = re.compile(r"\b(gestreamt|streamed|live übertragen|streamed live)\b", re.IGNORECASE)

        out = []
        replaced = False
        for line in lines:
            stripped = line.strip()
            if not stripped or replaced:
                out.append(line)
                continue

            if self._looksLikePublishedLine(line, releaseLabels, relPattern, streamedPattern):
                out.append(releaseLine)
                replaced = True
            else:
                out.append(line)

        if not replaced:
            out.insert(0, releaseLine)
            printDBG("Youtube._replacePublishedLineInDesc release line inserted")

        return out

    def _looksLikePublishedLine(self, line, releaseLabels, relPattern, streamedPattern):
        for label in releaseLabels:
            if not label:
                continue
            pattern = r"^.*?\b%s\b\s*:\s*[^\n\r]*$" % re.escape(label)
            if re.search(pattern, line, re.IGNORECASE):
                printDBG("Youtube._replacePublishedLineInDesc exact label replaced")
                return True

        if relPattern.search(line) or streamedPattern.search(line):
            printDBG("Youtube._replacePublishedLineInDesc relative-time line replaced")
            return True

        return False

    def _normalizePublishedDate(self, value):
        try:
            value = str(value or "").strip()
            if len(value) >= 10:
                return value[:10]
        except Exception:
            printExc()
        return str(value or "")

    def getArticleContent(self, cItem):
        printDBG("Youtube.getArticleContent START")
        retTab = []
        try:
            title = str(cItem.get("title", "") or "")
            shortText = str(self._getYouTubeInfoText(cItem) or "")
            icon = str(cItem.get("icon", "") or "")
            videoId = self._getVideoIdFromItem(cItem)
            channelName = self._getInitialChannelName(cItem)

            channelName, absolutePublished, text = self._enrichArticleFromWatchPage(videoId, channelName, shortText)

            channelName = str(channelName or "")
            text = str(text or "")
            if channelName:
                text = channelName + "\n" + text

            richDescParams = self._buildArticleRichDescParams(absolutePublished, cItem, videoId, channelName)

            images = []
            if icon:
                images.append({"title": "", "url": strwithmeta(icon)})

            retTab.append(ArticleContent(title=title, text=text, images=images, richDescParams=richDescParams))
            printDBG("Youtube.getArticleContent END OK")
        except Exception:
            printDBG("Youtube.getArticleContent END EXCEPTION")
            printExc()

        return retTab

    def _getInitialChannelName(self, cItem):
        if cItem.get("channel", ""):
            return cItem.get("channel", "")
        if cItem.get("channel_title", ""):
            return cItem.get("channel_title", "")
        if cItem.get("context_title", ""):
            return cItem.get("context_title", "")
        return ""

    def _enrichArticleFromWatchPage(self, videoId, channelName, shortText):
        # Returns (channelName, absolutePublished, text): text starts as
        # shortText and gets the release line patched in / the full
        # description appended once the watch page data comes back.
        text = shortText
        absolutePublished = ""
        if not videoId:
            return channelName, absolutePublished, text

        try:
            watchData = self.ytp._getWatchPageData(videoId)
            fullText = str(watchData.get("fullDescription", "") or "")
            absolutePublished = self._normalizePublishedDate(watchData.get("absolutePublished", ""))
            parserChannelName = str(watchData.get("channelName", "") or "")

            if not channelName and parserChannelName:
                channelName = parserChannelName

            if absolutePublished:
                printDBG("Youtube.getArticleContent absolutePublished[%s]" % absolutePublished)
                shortText = self._replacePublishedLineInDesc(shortText, absolutePublished)
                text = shortText

            if fullText:
                printDBG("Youtube.getArticleContent fullText FOUND len[%s]" % len(fullText))
                if shortText:
                    text = shortText + "\n\n" + fullText
                else:
                    text = fullText
            else:
                printDBG("Youtube.getArticleContent fullText EMPTY")
        except Exception:
            printDBG("Youtube.getArticleContent _getWatchPageData EXCEPTION")
            printExc()

        return channelName, absolutePublished, text

    def _buildArticleRichDescParams(self, absolutePublished, cItem, videoId, channelName):
        richDescParams = {}
        if absolutePublished:
            richDescParams["published"] = absolutePublished
        elif cItem.get("time", ""):
            richDescParams["published"] = self._normalizePublishedDate(cItem.get("time", ""))

        if videoId:
            richDescParams["videoid"] = str(videoId or "")
        if channelName:
            richDescParams["channel_name"] = channelName
        return richDescParams

    def getFavouriteData(self, cItem):
        printDBG("Youtube.getFavouriteData")
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("Youtube.getLinksForFavourite")
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
            return self.getLinksForVideo({"url": fav_data})
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("Youtube.setInitListFromFavouriteItem")
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Youtube.handleService start")

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Youtube.handleService: ---------> name[%s], category[%s] " % (name, category))
        self.currList = []

        if None is name:
            self.listMainMenu()
        elif "auth_feed" == category:
            self.listAuthFeed(self.currItem)
        elif "no_feed" == category:
            self.listMainMenu()
        elif "from_file" == category:
            self.listCategory(self.currItem)
        elif category in ["channel", "playlist", "movie", "traylist"]:
            self.getVideos(self.currItem)
        elif category.startswith("feeds"):
            self.listFeeds(self.currItem)
        elif category == "playlists":
            self.listItems(self.currItem)
        elif category == "sub_items":
            self.listSubItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)

    def getSuggestionsProvider(self, index):
        printDBG("Youtube.getSuggestionsProvider")
        from Plugins.Extensions.IPTVPlayer.suggestions.google import SuggestionsProvider

        return SuggestionsProvider(True)


class IPTVHost(WatchedFlagHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Youtube(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('youtube')

    def getSearchTypes(self):
        return self.host.SEARCH_TYPES

    def canAddToUserLinks(self, Index=0):
        try:
            cItem = self.host.currList[Index]
            return self.host.userLinks.isChannelItem(cItem)
        except Exception:
            printExc()
        return False

    def addToUserLinks(self, session, Index=0):
        try:
            cItem = self.host.currList[Index]
            self.host.openAddCurrentItemToUserLinks(session, cItem)
            return True
        except Exception:
            printExc()
        return False

    def editUserLinks(self, session):
        try:
            self.host.openUserLinksEditor(session)
            return True
        except Exception:
            printExc()
        return False

    def withArticleContent(self, cItem):
        try:
            category = cItem.get("category", "")
            if category in ["video", "movie", "traylist"] or "video_id" in cItem or "watch?v=" in cItem.get("url", ""):
                return True
        except Exception:
            printExc()
        return False

    def getArticleContent(self, Index=0):
        printDBG("IPTVHost.getArticleContent")
        retCode = RetHost.OK
        retlist = []
        try:
            cItem = self.host.currList[Index]
            retlist = self.host.getArticleContent(cItem)
        except Exception:
            printExc()
            retCode = RetHost.ERROR
        return RetHost(retCode, value=retlist)

    def performCustomAction(self, privateData):
        ret = self.watchedHelper.performCustomAction(privateData)
        if ret.status == RetHost.OK:
            self.refreshAfterWatchedFlagChange = True
        return ret
