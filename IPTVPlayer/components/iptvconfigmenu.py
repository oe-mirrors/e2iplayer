# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#

###################################################
# LOCAL import
###################################################

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, \
                                                          IsExecutable, CFakeMoviePlayerOption, GetCookieDir, GetJSCacheDir, \
                                                          GetSubtitlesDir, GetMovieMetaDataDir, RemoveDirContents, RemoveAllDirsIconsFromPath, \
                                                          GetSearchHistoryDir, GetFavouritesDir, GetWatchedDir, GetMoviePlayerPerHostDir, GetHostOrderDir, IsPathSafeToWipe, \
                                                          IsSameDir, IsSameOrSubDir
from Plugins.Extensions.IPTVPlayer.components.configbase import ConfigBaseWidget
from Plugins.Extensions.IPTVPlayer.components.confighost import ConfigHostsMenu
from Plugins.Extensions.IPTVPlayer.components.iptvdirbrowser import IPTVDirectorySelectorWidget
from Plugins.Extensions.IPTVPlayer.components.configextmovieplayer import ConfigExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.__init__ import _, GRIDSUPPORT
from .iptvpin import IPTVPinWidget
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.MessageBox import MessageBox

from Components.ActionMap import ActionMap
from Components.config import config, ConfigSelection, ConfigDirectory, ConfigText, getConfigListEntry, configfile
from Tools.BoundFunction import boundFunction
###################################################


###################################################
# Config options for HOST
###################################################
# The options themselves live in iptvconfig.py (loaded at enigma2 start by
# plugin.py); the names are passed on here for everything that imports them
# from this module.
from Plugins.Extensions.IPTVPlayer.components.iptvconfig import GetMoviePlayerName, ConfigPlayer, \
                                                                GetAlternativeProxyList, GetAlternativeProxyChoices, GetAlternativeProxyUrl, \
                                                                IsPluginBrowserEntryShown, IsExternalResolveAllowed, IsSidecarEnabled, \
                                                                GetConfigExpectedPin, IsMediaNamingNormalized, \
                                                                ConfigIPTVHostOnOff, GetListOfHostsNames  # noqa: F401


###################################################


def GetOskOwnModelConfigList(indent=True):
    # the "Own model" keyboard's own options - shared by ConfigMenu's
    # "Grundkonfiguration" section (indented, nested under "Virtual Keyboard
    # type") and E2iVKQuickSettings (the keyboard's own MENU -> Settings
    # screen, shown standalone since that screen only exists while the "own"
    # model is already active) so both stay in sync
    #
    # The indent is purely presentational, so it's applied to the already-
    # translated result instead of being baked into the msgid - that used to
    # be the case (msgid "    Show suggestions") and every .po's msgstr had
    # the same 4 spaces baked in too, so this only works untranslated for
    # E2iVKQuickSettings (indent=False) before now. Migrated all 12 locales'
    # existing translations onto the unindented msgid instead of leaving
    # them stuck on a dead, presentation-specific key.
    prefix = '    ' if indent else ''
    list = []
    list.append(getConfigListEntry(prefix + _("Background color"), config.plugins.iptvplayer.osk_background_color))
    list.append(getConfigListEntry(prefix + _("Show suggestions"), config.plugins.iptvplayer.osk_allow_suggestions))
    list.append(getConfigListEntry(prefix + _("Default suggestions provider"), config.plugins.iptvplayer.osk_default_suggestions))
    list.append(getConfigListEntry(prefix + _("Allow host to override suggestions provider"), config.plugins.iptvplayer.osk_allow_host_suggestions))
    list.append(getConfigListEntry(prefix + _("Show search history"), config.plugins.iptvplayer.osk_allow_search_history))
    list.append(getConfigListEntry(prefix + _("Show flags"), config.plugins.iptvplayer.osk_show_flags))
    list.append(getConfigListEntry(prefix + _("Font size offset"), config.plugins.iptvplayer.osk_font_size_offset))
    list.append(getConfigListEntry(prefix + _("Text field alignment"), config.plugins.iptvplayer.osk_searchfield_align))
    return list


def GetOskConfigList():
    list = []
    list.append(getConfigListEntry(_("Virtual Keyboard type"), config.plugins.iptvplayer.osk_type))
    if config.plugins.iptvplayer.osk_type.value in ('', 'own'):
        list.append(getConfigListEntry('    ' + _("Numeric keypad for numbers"), config.plugins.iptvplayer.osk_numpad))
    if config.plugins.iptvplayer.osk_type.value == 'own':
        list.extend(GetOskOwnModelConfigList(indent=True))
    return list


class E2iVKQuickSettings(ConfigBaseWidget):
    def __init__(self, session):
        self.list = []
        ConfigBaseWidget.__init__(self, session)

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self.setTitle(_("E2iPlayer - keyboard settings"))

    def runSetup(self):
        self.list = GetOskOwnModelConfigList(indent=False)
        ConfigBaseWidget.runSetup(self)

    def getSubOptionsList(self):
        return []

    def keyDefaults(self):
        # ConfigBaseWidget's own keyDefaults() is a no-op stub; ConfigMenu
        # overrides it for the full settings list, this does the same but
        # scoped to just the keyboard options shown here.
        def keyDefaultsConfirm(result):
            if result:
                for item in self.list:
                    if len(item) > 1:
                        configItem = item[1]
                        if not isinstance(configItem, ConfigText):
                            configItem.value = configItem.default
                self.close()
        message = _("Are you sure you want to reset all settings to their default values?")
        self.session.openWithCallback(keyDefaultsConfirm, MessageBox, text=message, type=MessageBox.TYPE_YESNO)


class ConfigMenu(ConfigBaseWidget):

    HAS_BLUE_KEY = True

    def __init__(self, session):
        printDBG("ConfigMenu.__init__ -------------------------------")
        self.list = []
        # category view: the screen starts on the list of categories (_section None) and OK opens one
        # of them (_section = its index in getSections()), EXIT goes back. The view is remembered per
        # build so runSetup() can keep the cursor where it is when it only rebuilds the same view.
        self._categoryView = config.plugins.iptvplayer.configMenuView.value == "categories"
        self._section = None
        self._builtView = None
        ConfigBaseWidget.__init__(self, session)
        # "<" / ">" (KEY_PREVIOUS / KEY_NEXT) page through the categories, LEFT/RIGHT stay reserved
        # for changing the value of the selected row
        self["sectionActions"] = ActionMap(["IPTVPlayerConfigActions"],
            {
                "prevSection": self.keyPrevSection,
                "nextSection": self.keyNextSection,
            }, -2)
        try:
            self["key_blue"].setText(_("Info"))
        except Exception:
            printExc()
        self.runtimeOptionsValues = self.getRuntimeOptionsValues()

    def __del__(self):
        printDBG("ConfigMenu.__del__ -------------------------------")

    def __onClose(self):
        printDBG("ConfigMenu.__onClose -----------------------------")
        ConfigBaseWidget.__onClose(self)

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self._updateTitle()

    def _updateTitle(self):
        if self._section is None:
            self.setTitle(_("E2iPlayer - settings"))
        else:
            sections = ConfigMenu.getSections()
            self.setTitle("E2iPlayer - < %s > (%d/%d)" % (ConfigMenu.getSectionLabel(sections[self._section][1]), self._section + 1, len(sections)))

    @staticmethod
    def getSectionLabel(header):
        # "----- BASIC CONFIGURATION -----" -> "Basic Configuration"
        return header.strip("- ").title()

    def _inOverview(self):
        return self._categoryView and self._section is None

    def keyBlue(self):
        try:
            from Plugins.Extensions.IPTVPlayer.components.iptvplayerinfoview import OpenInfoView
            OpenInfoView(self.session)
        except Exception:
            printExc()

    @staticmethod
    def _fillBasic(list):
        list.append(getConfigListEntry(_("Settings screen layout"), config.plugins.iptvplayer.configMenuView))
        list.append(getConfigListEntry(_("Initialize web interface"), config.plugins.iptvplayer.IPTVWebIterface))
        list.append(getConfigListEntry(_("Show IPTVPlayer in plugin browser"), config.plugins.iptvplayer.showinPluginBrowser))
        list.append(getConfigListEntry(_("Show IPTVPlayer in extension list (blue button)"), config.plugins.iptvplayer.showinextensions))
        list.append(getConfigListEntry(_("Show IPTVPlayer in main menu"), config.plugins.iptvplayer.showinMainMenu))
        list.append(getConfigListEntry(_("Show E2iPlayer settings in system menu"), config.plugins.iptvplayer.showinSystemMenu))
        list.append(getConfigListEntry(_("E2iPlayer auto start at Enigma2 start"), config.plugins.iptvplayer.plugin_autostart))
        if config.plugins.iptvplayer.plugin_autostart.value:
            list.append(getConfigListEntry(_("Auto start method"), config.plugins.iptvplayer.plugin_autostart_method))
        list.append(getConfigListEntry(_("Disable live at plugin start"), config.plugins.iptvplayer.disable_live))
        list.append(getConfigListEntry(_("Use the PyCurl for HTTP(S) requests"), config.plugins.iptvplayer.usepycurl))

    @staticmethod
    def _fillKeyboard(list):
        list.extend(GetOskConfigList())
        list.append(getConfigListEntry(_("T9 letter jump in lists"), config.plugins.iptvplayer.enableT9MainList))
        list.append(getConfigListEntry("    ===== " + _("Search").upper() + " =====",))
        list.append(getConfigListEntry("    " + _("Remember last search entry"), config.plugins.iptvplayer.osk_remember_last_search))
        list.append(getConfigListEntry("    " + _("Remember last search history selection"), config.plugins.iptvplayer.rememberHistorySelection))
        list.append(getConfigListEntry("    " + _("The number of items in the search history"), config.plugins.iptvplayer.search_history_size))

    @staticmethod
    def _fillService(list):
        list.append(getConfigListEntry(_("Services configuration"), config.plugins.iptvplayer.fakeHostsList))
        list.append(getConfigListEntry(_("Allow watched flag to be set"), config.plugins.iptvplayer.favourites_use_watched_flag))
        if config.plugins.iptvplayer.favourites_use_watched_flag.value:
            list.append(getConfigListEntry("    " + _("The color of the viewed item"), config.plugins.iptvplayer.watched_item_color))
            list.append(getConfigListEntry("    " + _("The color of the started item"), config.plugins.iptvplayer.started_item_color))
        list.append(getConfigListEntry(_("Mark downloaded items"), config.plugins.iptvplayer.mark_downloaded_items))
        if config.plugins.iptvplayer.mark_downloaded_items.value:
            list.append(getConfigListEntry("    " + _("The color of the downloaded item"), config.plugins.iptvplayer.downloaded_item_color))
        list.append(getConfigListEntry(_("Mark favourite items"), config.plugins.iptvplayer.mark_favourite_items))
        if config.plugins.iptvplayer.mark_favourite_items.value:
            list.append(getConfigListEntry("    " + _("The color of the favourite item"), config.plugins.iptvplayer.favourite_item_color))
        list.append(getConfigListEntry(_("Colored text in titles and descriptions"), config.plugins.iptvplayer.use_colors))
        list.append(getConfigListEntry("https://vk.com/ " + _("login"), config.plugins.iptvplayer.vkcom_login))
        list.append(getConfigListEntry("https://vk.com/ " + _("password"), config.plugins.iptvplayer.vkcom_password))
        list.append(getConfigListEntry("https://1fichier.com/ " + _("e-mail"), config.plugins.iptvplayer.fichiercom_login))
        list.append(getConfigListEntry("http://1fichier.com/ " + _("password"), config.plugins.iptvplayer.fichiercom_password))

    @staticmethod
    def _fillMetadata(list):
        # libs/moviemeta.py: details on the info screen of hosts which support it, the
        # services are asked in this order until one knows the title
        cp = config.plugins.iptvplayer
        list.append(getConfigListEntry(_("Language of the details (TMDb, IMDb)"), cp.meta_language))
        list.append(getConfigListEntry(_("Use TMDb"), cp.meta_tmdb))
        if cp.meta_tmdb.value:
            list.append(getConfigListEntry("    " + _("TMDb API key (free at themoviedb.org)"), cp.meta_tmdb_apikey))
        list.append(getConfigListEntry(_("Use IMDb (no key)"), cp.meta_imdb))
        list.append(getConfigListEntry(_("Use TVmaze for series (no key, English)"), cp.meta_tvmaze))
        list.append(getConfigListEntry(_("Use Cinemeta (no key, English)"), cp.meta_cinemeta))
        list.append(getConfigListEntry(_("Use OMDb"), cp.meta_omdb))
        if cp.meta_omdb.value:
            list.append(getConfigListEntry("    " + _("OMDb API key (free at omdbapi.com)"), cp.meta_omdb_apikey))

    @staticmethod
    def _fillSecurity(list):
        list.append(getConfigListEntry(_("Pin protection for plugin"), config.plugins.iptvplayer.pluginProtectedByPin))
        list.append(getConfigListEntry(_("Pin protection for configuration"), config.plugins.iptvplayer.configProtectedByPin))
        if config.plugins.iptvplayer.configProtectedByPin.value:
            list.append(getConfigListEntry("    " + _("Use own pin for configuration"), config.plugins.iptvplayer.configOwnPin))
        if config.plugins.iptvplayer.pluginProtectedByPin.value or (config.plugins.iptvplayer.configProtectedByPin.value and not config.plugins.iptvplayer.configOwnPin.value):
            list.append(getConfigListEntry(_("Set pin code"), config.plugins.iptvplayer.fakePin))
        if config.plugins.iptvplayer.configProtectedByPin.value and config.plugins.iptvplayer.configOwnPin.value:
            list.append(getConfigListEntry("    " + _("Set own configuration pin code"), config.plugins.iptvplayer.fakeConfigPin))
        list.append(getConfigListEntry(_("https - validate SSL certificates"), config.plugins.iptvplayer.httpssslcertvalidation))
        list.append(getConfigListEntry(_("Allow external link-decryption service (enc-dec.app)"), config.plugins.iptvplayer.allow_external_resolve))

    @staticmethod
    def _fillSkin(list):
        list.append(getConfigListEntry(_("Skin"), config.plugins.iptvplayer.skin))
        list.append(getConfigListEntry(_("Force internal skin: all E2iPlayer screens"), config.plugins.iptvplayer.skinforceallinternal))
        if not config.plugins.iptvplayer.skinforceallinternal.value:
            list.append(getConfigListEntry(_("Force internal skin: main screen only"), config.plugins.iptvplayer.skinforceinternal))
        list.append(getConfigListEntry(_("Show clock in header"), config.plugins.iptvplayer.show_header_clock))
        list.append(getConfigListEntry(_("Video player OSD clock format"), config.plugins.iptvplayer.extplayer_infobanner_clockformat))
        list.append(getConfigListEntry(_("Player Skin"), config.plugins.iptvplayer.extplayer_skin))
        list.append(getConfigListEntry(_("Display thumbnails"), config.plugins.iptvplayer.showcover))
        # list.append(getConfigListEntry("Sort the lists?", config.plugins.iptvplayer.sortuj))
        # list.append(getConfigListEntry(_("Graphic services selector"), config.plugins.iptvplayer.ListaGraficzna))
        # if config.plugins.iptvplayer.ListaGraficzna.value is True:
        list.append(getConfigListEntry(_("Hosts list type"), config.plugins.iptvplayer.hostsListType))
        list.append(getConfigListEntry("    " + _("Enable hosts groups"), config.plugins.iptvplayer.group_hosts))
        if config.plugins.iptvplayer.hostsListType.value == "G":
            list.append(getConfigListEntry("    " + _("Service icon size"), config.plugins.iptvplayer.IconsSize))
        if not GRIDSUPPORT and config.plugins.iptvplayer.hostsListType.value == "G":
            list.append(getConfigListEntry("    " + _("Number of rows"), config.plugins.iptvplayer.numOfRow))
            list.append(getConfigListEntry("    " + _("Number of columns"), config.plugins.iptvplayer.numOfCol))
        # list.append(getConfigListEntry(_("VFD set current title:"), config.plugins.iptvplayer.set_curr_title))
        list.append(getConfigListEntry(_("Create LCD/VFD summary screen"), config.plugins.iptvplayer.extplayer_summary))

    @staticmethod
    def _fillProxies(list):
        for slot, label, cfg in GetAlternativeProxyList():
            list.append(getConfigListEntry(label, cfg))

    @staticmethod
    def _fillStorage(list):
        list.append(getConfigListEntry(_("Folder for cache data"), config.plugins.iptvplayer.CacheDir))
        list.append(getConfigListEntry(_("Folder for temporary data"), config.plugins.iptvplayer.TmpDir))
        list.append(getConfigListEntry(_("Folder for config data"), config.plugins.iptvplayer.ConfigDir))
        list.append(getConfigListEntry(_("Detail/expert mode"), config.plugins.iptvplayer.storageExpertMode))
        if config.plugins.iptvplayer.storageExpertMode.value:
            # a one-element row cannot be coloured: indent + "=====" framing + upper case mark a sub-heading
            list.append(getConfigListEntry("    ===== " + _("Cache").upper() + " =====",))
            list.append(getConfigListEntry("    " + _("Delete cookies cache after (days, 0 = never)"), config.plugins.iptvplayer.cookiesCacheDeleteAfterDays))
            list.append(getConfigListEntry("    " + _("Delete cookies cache now"), config.plugins.iptvplayer.fakeCookiesCacheDelete))
            list.append(getConfigListEntry("    " + _("Delete JS cache after (days, 0 = never)"), config.plugins.iptvplayer.jsCacheDeleteAfterDays))
            list.append(getConfigListEntry("    " + _("Delete JS cache now"), config.plugins.iptvplayer.fakeJSCacheDelete))
            list.append(getConfigListEntry("    " + _("Delete subtitles cache after (days, 0 = never)"), config.plugins.iptvplayer.subtitlesCacheDeleteAfterDays))
            list.append(getConfigListEntry("    " + _("Delete subtitles cache now"), config.plugins.iptvplayer.fakeSubtitlesCacheDelete))
            list.append(getConfigListEntry("    " + _("Delete movie metadata cache after (days, 0 = never)"), config.plugins.iptvplayer.movieMetaDataCacheDeleteAfterDays))
            list.append(getConfigListEntry("    " + _("Delete movie metadata cache now"), config.plugins.iptvplayer.fakeMovieMetaDataCacheDelete))
            list.append(getConfigListEntry("    " + _("Remove thumbnails"), config.plugins.iptvplayer.deleteIcons))
            list.append(getConfigListEntry("    " + _("Delete thumbnails cache now"), config.plugins.iptvplayer.fakeIconsCacheDelete))
            list.append(getConfigListEntry("    " + _("Delete all cache files now"), config.plugins.iptvplayer.fakeAllCacheDelete))
            list.append(getConfigListEntry("    ===== " + _("Config").upper() + " =====",))
            list.append(getConfigListEntry("    " + _("Delete movie player preferences now"), config.plugins.iptvplayer.fakeMoviePlayerDelete))
            list.append(getConfigListEntry("    " + _("Delete host order and groups now"), config.plugins.iptvplayer.fakeHostOrderDelete))
            list.append(getConfigListEntry("    " + _("Delete search history now"), config.plugins.iptvplayer.fakeSearchHistoryDelete))
            list.append(getConfigListEntry("    " + _("Delete favourites and watched status now"), config.plugins.iptvplayer.fakeFavouritesDelete))
            list.append(getConfigListEntry("    " + _("Delete all config files now"), config.plugins.iptvplayer.fakeAllConfigDelete))

    @staticmethod
    def _fillBuffering(list):
        list.append(getConfigListEntry(_("[HTTP] buffering"), config.plugins.iptvplayer.buforowanie))
        list.append(getConfigListEntry(_("[HLS/M3U8] buffering"), config.plugins.iptvplayer.buforowanie_m3u8))
        if config.plugins.iptvplayer.buforowanie_m3u8.value:
            list.append(getConfigListEntry("    " + _("[HLS/M3U8] live stream starts behind live"), config.plugins.iptvplayer.hlsdlLiveStartOffset))
        list.append(getConfigListEntry(_("[RTMP] buffering (rtmpdump required)"), config.plugins.iptvplayer.buforowanie_rtmp))
        if config.plugins.iptvplayer.buforowanie.value or config.plugins.iptvplayer.buforowanie_m3u8.value or config.plugins.iptvplayer.buforowanie_rtmp.value:
            list.append(getConfigListEntry("    " + _("Video buffer size [MB]"), config.plugins.iptvplayer.requestedBuffSize))
            list.append(getConfigListEntry("    " + _("Audio buffer size [KB]"), config.plugins.iptvplayer.requestedAudioBuffSize))
            list.append(getConfigListEntry(_("Buffering location"), config.plugins.iptvplayer.bufferingPath))

    @staticmethod
    def _fillDownloading(list):
        list.append(getConfigListEntry("    ===== " + _("Download manager").upper() + " =====",))
        list.append(getConfigListEntry("    " + _("Downloads location"), config.plugins.iptvplayer.DownloadsDir))
        list.append(getConfigListEntry("    " + _("Start download manager per default"), config.plugins.iptvplayer.IPTVDMRunAtStart))
        list.append(getConfigListEntry("    " + _("Show download manager after adding new item"), config.plugins.iptvplayer.IPTVDMShowAfterAdd))
        list.append(getConfigListEntry("    " + _("Number of downloaded files simultaneously"), config.plugins.iptvplayer.IPTVDMMaxDownloadItem))
        list.append(getConfigListEntry("    " + _("Program for file downloads (HTTP/FTP)"), config.plugins.iptvplayer.http_downloader))
        list.append(getConfigListEntry("    " + _("Show download notification"), config.plugins.iptvplayer.IPTVDMShowNotification))
        if config.plugins.iptvplayer.IPTVDMShowNotification.value:
            list.append(getConfigListEntry("        " + _("Download notification duration"), config.plugins.iptvplayer.IPTVDMNotificationDuration))
        list.append(getConfigListEntry("    ===== " + _("Files").upper() + " =====",))
        list.append(getConfigListEntry("    " + _("Create sidecar files (.txt/.jpg)"), config.plugins.iptvplayer.sidecar_enabled))
        list.append(getConfigListEntry("    " + _("Normalize item / file names (Show - SxxExx - Title)"), config.plugins.iptvplayer.normalize_media_names))

    @staticmethod
    def _fillCaptcha(list):
        list.append(getConfigListEntry("    ===== " + _("Solver").upper() + " =====",))
        list.append(getConfigListEntry("    " + _("Default captcha bypass"), config.plugins.iptvplayer.captcha_bypass))
        list.append(getConfigListEntry("    " + _("MyE2i extension: increase security"), config.plugins.iptvplayer.mye2i_security))
        list.append(getConfigListEntry("    ===== " + _("Accounts & API keys").upper() + " =====",))
        # list.append(getConfigListEntry(_("Captcha solver order"), config.plugins.iptvplayer.captcha_bypass_order))
        # list.append(getConfigListEntry(_("Captcha bypass free service"), config.plugins.iptvplayer.captcha_bypass_free))
        # list.append(getConfigListEntry(_("Captcha bypass paid service"), config.plugins.iptvplayer.captcha_bypass_pay))
        # if config.plugins.iptvplayer.captcha_bypass_pay.value == "9kw.eu":
        list.append(getConfigListEntry("    https://9kw.eu/ " + _("API Key"), config.plugins.iptvplayer.api_key_9kweu))
        # if config.plugins.iptvplayer.captcha_bypass_pay.value == "2captcha.com":
        list.append(getConfigListEntry("    https://2captcha.com/ " + _("API Key"), config.plugins.iptvplayer.api_key_2captcha))
        list.append(getConfigListEntry("    " + _("%s e-mail") % ('My JDownloader'), config.plugins.iptvplayer.myjd_login))
        list.append(getConfigListEntry("    " + _("%s password") % ('My JDownloader'), config.plugins.iptvplayer.myjd_password))
        list.append(getConfigListEntry("    " + _("%s device name") % ('My JDownloader'), config.plugins.iptvplayer.myjd_jdname))

    @staticmethod
    def _fillSubtitles(list):
        list.append(getConfigListEntry(_("Use subtitles parser extension if available"), config.plugins.iptvplayer.useSubtitlesParserExtension))
        list.append(getConfigListEntry("https://subsource.net/ " + _("API Key"), config.plugins.iptvplayer.subsourceapi))
        list.append(getConfigListEntry("https://subdl.com/ " + _("API Key"), config.plugins.iptvplayer.subdlapi))
        list.append(getConfigListEntry("https://sub.wyzie.io/ " + _("API Key"), config.plugins.iptvplayer.wyzieapi))
        list.append(getConfigListEntry("https://opensubtitles.org/ " + _("login"), config.plugins.iptvplayer.opensuborg_login))
        list.append(getConfigListEntry("https://opensubtitles.org/ " + _("password"), config.plugins.iptvplayer.opensuborg_password))
        list.append(getConfigListEntry("https://napisy24.pl/ " + _("login"), config.plugins.iptvplayer.napisy24pl_login))
        list.append(getConfigListEntry("https://napisy24.pl/ " + _("password"), config.plugins.iptvplayer.napisy24pl_password))
        list.append(getConfigListEntry("https://www.titulky.com/ " + _("login"), config.plugins.iptvplayer.titulky_login))
        list.append(getConfigListEntry("https://www.titulky.com/ " + _("password"), config.plugins.iptvplayer.titulky_password))
        list.append(getConfigListEntry("https://titlovi.com/ " + _("login"), config.plugins.iptvplayer.titlovi_login))
        list.append(getConfigListEntry("https://titlovi.com/ " + _("password"), config.plugins.iptvplayer.titlovi_password))
        list.append(getConfigListEntry("https://www.prijevodi-online.org/ " + _("login"), config.plugins.iptvplayer.prijevodi_login))
        list.append(getConfigListEntry("https://www.prijevodi-online.org/ " + _("password"), config.plugins.iptvplayer.prijevodi_password))

    @staticmethod
    def _fillPlayers(list):
        list.append(getConfigListEntry(_("Autoplay start delay"), config.plugins.iptvplayer.autoplay_start_delay))
        list.append(getConfigListEntry(_("Block wmv files"), config.plugins.iptvplayer.ZablokujWMV))
        players = []
        list.append(getConfigListEntry(_("Movie player selection list"), config.plugins.iptvplayer.moviePlayerPickerMode))
        list.append(getConfigListEntry(_("First movie player without buffering mode"), config.plugins.iptvplayer.defaultMoviePlayer0))
        players.append(config.plugins.iptvplayer.defaultMoviePlayer0)
        list.append(getConfigListEntry(_("Second movie player without buffering mode"), config.plugins.iptvplayer.alternativeMoviePlayer0))
        players.append(config.plugins.iptvplayer.alternativeMoviePlayer0)
        list.append(getConfigListEntry(_("First movie player in buffering mode"), config.plugins.iptvplayer.defaultMoviePlayer))
        players.append(config.plugins.iptvplayer.defaultMoviePlayer)
        list.append(getConfigListEntry(_("Second movie player in buffering mode"), config.plugins.iptvplayer.alternativeMoviePlayer))
        players.append(config.plugins.iptvplayer.alternativeMoviePlayer)
        playersValues = [player.value for player in players]
        if 'exteplayer' in playersValues or 'extgstplayer' in playersValues or 'auto' in playersValues:
            list.append(getConfigListEntry(_("External movie player config"), config.plugins.iptvplayer.fakExtMoviePlayerList))
        list.append(getConfigListEntry(_("Write current title to file:"), config.plugins.iptvplayer.curr_title_file))

    @staticmethod
    def _fillDebug(list):
        list.append(getConfigListEntry(_("Debug logs"), config.plugins.iptvplayer.debugprint))
        if config.plugins.iptvplayer.debugprint.value != "":
            list.append(getConfigListEntry("    " + _("Keep FFmpeg command files (.iptv.cmd)"), config.plugins.iptvplayer.debug_keep_ffmpeg_cmd))
            list.append(getConfigListEntry("        " + _("saved next to the downloaded video file"), ))
            list.append(getConfigListEntry("    " + _("Keep temporary JS scripts"), config.plugins.iptvplayer.debug_keep_js_scripts))
            list.append(getConfigListEntry("        " + _("saved in the temporary data folder"), ))
        if config.plugins.iptvplayer.debugprint.value not in ("", "console"):
            list.append(getConfigListEntry("    " + _("Clear the log file at plugin start"), config.plugins.iptvplayer.debug_clear_on_start))
            list.append(getConfigListEntry("    " + _("Maximum log file size"), config.plugins.iptvplayer.debug_max_size))
            if config.plugins.iptvplayer.debug_max_size.value != "0":
                list.append(getConfigListEntry("    " + _("When the maximum is reached"), config.plugins.iptvplayer.debug_on_limit))
                if config.plugins.iptvplayer.debug_on_limit.value == "rotate":
                    list.append(getConfigListEntry("        " + _("Number of rotated files to keep"), config.plugins.iptvplayer.debug_rotate_keep))

    # (id, header, filler) in display order. The header is what the long list shows and, without
    # the dashes, what the category view names the category - so the existing translations of the
    # headers are reused as they are
    @staticmethod
    def getSections():
        return (
            ("basic", _("----- BASIC CONFIGURATION -----"), ConfigMenu._fillBasic),
            ("keyboard", _("----- VIRTUAL KEYBOARD & SEARCH CONFIGURATION -----"), ConfigMenu._fillKeyboard),
            ("service", _("----- SERVICE CONFIGURATION -----"), ConfigMenu._fillService),
            ("metadata", _("----- METADATA PROVIDERS CONFIGURATION -----"), ConfigMenu._fillMetadata),
            ("security", _("----- SECURITY CONFIGURATION -----"), ConfigMenu._fillSecurity),
            ("skin", _("----- SKIN CONFIGURATION -----"), ConfigMenu._fillSkin),
            ("proxies", _("----- PROXIES CONFIGURATION -----"), ConfigMenu._fillProxies),
            ("storage", _("----- STORAGE CONFIGURATION -----"), ConfigMenu._fillStorage),
            ("buffering", _("----- BUFFERING CONFIGURATION -----"), ConfigMenu._fillBuffering),
            ("downloading", _("----- DOWNLOADING CONFIGURATION -----"), ConfigMenu._fillDownloading),
            ("captcha", _("----- CAPTCHA CONFIGURATION -----"), ConfigMenu._fillCaptcha),
            ("subtitles", _("----- SUBTITLES CONFIGURATION -----"), ConfigMenu._fillSubtitles),
            ("players", _("----- PLAYERS & PLAYBACK CONFIGURATION -----"), ConfigMenu._fillPlayers),
            ("debug", _("----- DEBUG CONFIGURATION -----"), ConfigMenu._fillDebug),
        )

    @staticmethod
    def fillConfigList(list, sectionId=None):
        # sectionId None = every section, each below its header (the long list, also used by the web
        # interface); otherwise just the rows of that one section (the category view)
        for currId, header, fill in ConfigMenu.getSections():
            if sectionId is None:
                list.append(getConfigListEntry(header,))
            if sectionId is None or sectionId == currId:
                fill(list)

    def runSetup(self):
        view = (self._categoryView, self._section)
        try:
            keepIndex = self["config"].getCurrentIndex() if view == self._builtView else None
        except Exception:
            printExc()
            keepIndex = None
        self.list = []
        if self._inOverview():
            self._fillOverview(self.list)
        elif self._categoryView:
            ConfigMenu.fillConfigList(self.list, ConfigMenu.getSections()[self._section][0])
        else:
            ConfigMenu.fillConfigList(self.list)
        ConfigBaseWidget.runSetup(self)
        self._builtView = view
        # rebuilding the list (a parent option was toggled, changes were cancelled, ...) puts the cursor
        # back on top - leave it where it was when it is still the same view
        if keepIndex:
            self._moveCursorTo(keepIndex)
        self._updateTitle()

    def _moveCursorTo(self, index):
        try:
            if 0 <= index < len(self.list):
                self["config"].setCurrentIndex(index)
        except Exception:
            printExc()

    def _fillOverview(self, list):
        # one OK-only row per category (same kind of placeholder row as "Services configuration")
        for sectionId, header, fill in ConfigMenu.getSections():
            list.append(getConfigListEntry(ConfigMenu.getSectionLabel(header), ConfigSelection(default="open", choices=[("open", ">")])))

    def _getAllConfigItems(self):
        # the category view only shows one category's rows (or just the category list), but saving,
        # cancelling and the "changes made?" question have to cover all of them
        if self._categoryView:
            allItems = []
            ConfigMenu.fillConfigList(allItems)
            return allItems
        return ConfigBaseWidget._getAllConfigItems(self)

    def _openSection(self, index):
        sections = ConfigMenu.getSections()
        self._section = index % len(sections)
        self.runSetup()

    def _backToOverview(self):
        index = self._section
        self._section = None
        self.runSetup()
        self._moveCursorTo(index)

    def keyPrevSection(self):
        if self._categoryView and self._section is not None:
            self._openSection(self._section - 1)

    def keyNextSection(self):
        if self._categoryView and self._section is not None:
            self._openSection(self._section + 1)

    def keyExit(self):
        if self._categoryView and self._section is not None:
            self._backToOverview()
        else:
            ConfigBaseWidget.keyExit(self)

    def changeSubOptions(self):
        current = self["config"].getCurrent()
        if current and len(current) > 1 and current[1] is config.plugins.iptvplayer.configMenuView:
            self._applyViewMode()
        else:
            self._keepOneStartEntry(current)
            ConfigBaseWidget.changeSubOptions(self)

    def _keepOneStartEntry(self, current):
        # the player must stay startable: when the last of plugin browser / extension list / main menu
        # is switched off, that switch goes back on and the user is told why
        cp = config.plugins.iptvplayer
        entries = (cp.showinPluginBrowser, cp.showinextensions, cp.showinMainMenu)
        if not current or len(current) < 2 or not any(current[1] is entry for entry in entries):
            return
        if any(entry.value for entry in entries):
            return
        current[1].value = True
        self["config"].invalidateCurrent()
        self.session.open(MessageBox, _("At least one of plugin browser, extension list and main menu has to stay on, otherwise E2iPlayer could no longer be started."), type=MessageBox.TYPE_INFO, timeout=8)

    def _applyViewMode(self):
        # the layout option was just switched: take effect right away, staying on that option's row
        categoryView = config.plugins.iptvplayer.configMenuView.value == "categories"
        if categoryView == self._categoryView:
            return
        self._categoryView = categoryView
        # the option lives in the first category
        self._section = 0 if categoryView else None
        self.runSetup()
        for index, item in enumerate(self.list):
            if len(item) > 1 and item[1] is config.plugins.iptvplayer.configMenuView:
                self._moveCursorTo(index)
                break

    def onSelectionChanged(self):
        currItem = self["config"].getCurrent()[1]
        okOnlyItems = [config.plugins.iptvplayer.fakePin, config.plugins.iptvplayer.fakeConfigPin, config.plugins.iptvplayer.fakeHostsList,
                       config.plugins.iptvplayer.fakExtMoviePlayerList]
        okOnlyItems += [fakeItem for fakeItem, action in self._getDeleteNowActions()]
        if currItem in okOnlyItems or self._inOverview():
            self.isOkEnabled = True
            self.isSelectable = False
            self.setOKLabel()
            # without this, moving off/onto one of these OK-only fake rows
            # never reflows/hides the MENU icon and "<>" prevnext hint,
            # since ConfigBaseWidget.onSelectionChanged() (which normally
            # does this) is skipped entirely on this branch.
            #
            # hasMenu is hardcoded False here, NOT bool(self["key_menu"].text) -
            # fakePin/fakeHostsList/fakExtMoviePlayerList are real ConfigSelection
            # objects (they need .description/.choices to exist at all),
            # so Enigma2's own core ConfigListScreen logic that writes
            # self["key_menu"].text has no idea they're meant to be
            # excluded and marks them MENU-able anyway. keyMenu() itself
            # already refuses to do anything for these rows via the
            # `self.isSelectable` guard (see its own comment in
            # configbase.py) - the icon must follow that same "no real
            # MENU action here" fact instead of the core's naive one.
            self._repositionFooterKeys(False, self.isSelectable)
        else:
            ConfigBaseWidget.onSelectionChanged(self)

    def getRuntimeOptionsValues(self):
        valTab = []
        valTab.append(config.plugins.iptvplayer.IPTVWebIterface.value)
        valTab.append(config.plugins.iptvplayer.showinPluginBrowser.value)
        valTab.append(config.plugins.iptvplayer.showinextensions.value)
        valTab.append(config.plugins.iptvplayer.showinMainMenu.value)
        valTab.append(config.plugins.iptvplayer.showinSystemMenu.value)
        valTab.append(config.plugins.iptvplayer.plugin_autostart.value)
        valTab.append(config.plugins.iptvplayer.plugin_autostart_method.value)
        valTab.append(config.plugins.iptvplayer.disable_live.value)
        valTab.append(config.plugins.iptvplayer.pluginProtectedByPin.value)
        valTab.append(config.plugins.iptvplayer.skin.value)
        valTab.append(config.plugins.iptvplayer.skinforceinternal.value)
        valTab.append(config.plugins.iptvplayer.skinforceallinternal.value)
        return valTab

    def getMessageAfterSave(self):
        if self.runtimeOptionsValues != self.getRuntimeOptionsValues():
            return _('Some settings will be applied only after GUI restart.')
        else:
            return ''

    def getMessageBeforeClose(self, afterSave):
        return ''

    def closeAfterMessage(self, arg=None):
        self.close()
        """
        if arg:
            # self.doUpdate(True)
            self.close()
        else:
            self.close()
        """

    def keyOK(self):
        curIndex = self["config"].getCurrentIndex()
        if self._inOverview():
            self._openSection(curIndex)
            return
        currItem = self["config"].list[curIndex][1]
        if isinstance(currItem, ConfigDirectory):
            def SetDirPathCallBack(curIndex, newPath):
                if None is not newPath:
                    self["config"].list[curIndex][1].value = newPath
            self.session.openWithCallback(boundFunction(SetDirPathCallBack, curIndex), IPTVDirectorySelectorWidget, currDir=currItem.value, title=_("Select directory"))
        elif config.plugins.iptvplayer.fakePin == currItem:
            self.changePin(start=True)
        elif config.plugins.iptvplayer.fakeConfigPin == currItem:
            self.changeConfigPin(start=True)
        elif config.plugins.iptvplayer.fakeHostsList == currItem:
            self.hostsList()
        elif config.plugins.iptvplayer.fakExtMoviePlayerList == currItem:
            self.extMoviePlayerList()
        else:
            for fakeItem, action in self._getDeleteNowActions():
                if fakeItem == currItem:
                    action()
                    break
            else:
                ConfigBaseWidget.keyOK(self)

    def _getDeleteNowActions(self):
        # every "Delete ... now" row and what OK does on it; built per call so the texts follow the UI language
        cp = config.plugins.iptvplayer
        return (
            (cp.fakeCookiesCacheDelete, lambda: self.confirmDeleteCacheNow(_("cookies cache"), GetCookieDir())),
            (cp.fakeJSCacheDelete, lambda: self.confirmDeleteCacheNow(_("JS cache"), GetJSCacheDir())),
            (cp.fakeSubtitlesCacheDelete, lambda: self.confirmDeleteCacheNow(_("subtitles cache"), GetSubtitlesDir())),
            (cp.fakeMovieMetaDataCacheDelete, lambda: self.confirmDeleteCacheNow(_("movie metadata cache"), GetMovieMetaDataDir())),
            (cp.fakeMoviePlayerDelete, lambda: self.confirmDeleteCacheNow(_("movie player preferences"), GetMoviePlayerPerHostDir())),
            (cp.fakeHostOrderDelete, lambda: self.confirmDeleteCacheNow(_("host order and groups"), GetHostOrderDir())),
            (cp.fakeSearchHistoryDelete, lambda: self.confirmDeleteCacheNow(_("search history"), GetSearchHistoryDir())),
            (cp.fakeIconsCacheDelete, lambda: self._askYesNo(self.deleteIconsCacheNowCallback, _("Do you really want to delete the thumbnails cache now?"))),
            (cp.fakeFavouritesDelete, lambda: self._askYesNo(self.deleteFavouritesNowCallback, _("Do you really want to delete ALL favourites and watched status now? This is real user data, not just cache, and cannot be undone."))),
            (cp.fakeAllCacheDelete, lambda: self._askYesNo(boundFunction(self.deleteCacheNowCallback, cp.CacheDir.value), _("Do you really want to delete ALL cache data now? This includes cookies, subtitles, movie metadata and thumbnails, and cannot be undone."))),
            (cp.fakeAllConfigDelete, lambda: self._askYesNo(boundFunction(self.deleteCacheNowCallback, cp.ConfigDir.value), _("Do you really want to delete ALL config data now? This is real user data, not just cache - it includes favourites, watched status, search history, movie player preferences and host order/groups, and cannot be undone."))),
        )

    def _askYesNo(self, callback, text):
        self.session.openWithCallback(callback, MessageBox, text, type=MessageBox.TYPE_YESNO, default=False)

    def confirmDeleteCacheNow(self, label, path):
        self._askYesNo(boundFunction(self.deleteCacheNowCallback, path), _("Do you really want to delete the %s now?") % label)

    def deleteCacheNowCallback(self, path, ret=False):
        if ret:
            if not IsPathSafeToWipe(path):
                printDBG('Storage: REFUSED to empty [%s] (not a dedicated cache/config folder)' % path)
                self.session.open(MessageBox, _('Refusing to empty "%s" - this does not look like a dedicated cache/config folder. Check the folder paths in the storage configuration.') % path, type=MessageBox.TYPE_ERROR, timeout=8)
                return
            conflict = self._getWipeConflict(path)
            if conflict:
                printDBG('Storage: REFUSED to empty [%s] (holds [%s])' % (path, conflict))
                self.session.open(MessageBox, _('Refusing to empty "%s" - it also holds "%s" (downloads, buffering, cache or config folder). Check the folder paths in the storage configuration.') % (path, conflict), type=MessageBox.TYPE_ERROR, timeout=8)
                return
            printDBG('Storage: emptying [%s]' % path)
            RemoveDirContents(path)

    @staticmethod
    def _getWipeConflict(path):
        # another E2iPlayer folder that emptying path would take with it ('' = none): the downloads and
        # buffering folders always, the config folder when the cache is emptied and the other way round
        cp = config.plugins.iptvplayer
        isCache = IsSameDir(path, cp.CacheDir.value)
        isConfig = IsSameDir(path, cp.ConfigDir.value)
        if isCache and isConfig:
            return cp.ConfigDir.value
        others = [cp.DownloadsDir.value, cp.bufferingPath.value]
        if not isConfig:
            others.append(cp.ConfigDir.value)
        if not isCache:
            others.append(cp.CacheDir.value)
        for other in others:
            if other and IsSameOrSubDir(other, path):
                return other
        return ''

    def deleteFavouritesNowCallback(self, ret=False):
        if ret:
            for path in (GetFavouritesDir(), GetWatchedDir()):
                self.deleteCacheNowCallback(path, True)

    def deleteIconsCacheNowCallback(self, ret=False):
        # icon batch dirs sit directly under CacheDir, RemoveDirContents() would also wipe cookies etc.
        if ret:
            RemoveAllDirsIconsFromPath(config.plugins.iptvplayer.CacheDir.value)

    def keyDefaults(self):
        def keyDefaultsConfirm(result):
            if result:
                for item in self._getAllConfigItems():
                    if len(item) > 1:
                        configItem = item[1]
                        if not isinstance(configItem, ConfigText):
                            configItem.value = configItem.default
                self.close()
        message = _("Are you sure you want to reset all settings to their default values?")
        self.session.openWithCallback(keyDefaultsConfirm, MessageBox, text=message, type=MessageBox.TYPE_YESNO)

    def keyLeft(self):
        ConfigBaseWidget.keyLeft(self)
        self._confirmExternalResolve()

    def keyRight(self):
        ConfigBaseWidget.keyRight(self)
        self._confirmExternalResolve()

    def _confirmExternalResolve(self):
        # fires only when the "Allow external link-decryption service" row was
        # just switched ON - shows an info screen, then a separate yes/no
        # confirmation, and flips the option back off unless the user confirms.
        try:
            cur = self["config"].getCurrent()
            if not cur or len(cur) < 2 or cur[1] is not config.plugins.iptvplayer.allow_external_resolve:
                return
            if not config.plugins.iptvplayer.allow_external_resolve.value:
                return

            def revert(confirmed):
                if not confirmed:
                    config.plugins.iptvplayer.allow_external_resolve.value = False
                    self.runSetup()

            def askConfirm(unused=None):
                self.session.openWithCallback(
                    revert, MessageBox,
                    text=_("Send data to enc-dec.app on every link resolve?"),
                    type=MessageBox.TYPE_YESNO, default=False)

            info = _("The 7reels / cineb resolvers 'VidEasy', 'VidCore/VidFast', "
                     "'VidLink' and 'Peachify' cannot decrypt their links on the "
                     "receiver.\n\n"
                     "With this option ON, every time you open one of them E2iPlayer "
                     "sends the site's encrypted stream token - which contains the "
                     "TMDb id of the movie or episode you are opening - to the "
                     "third-party web service enc-dec.app (operated by a private "
                     "individual). That server then sees the id and your IP address "
                     "on each play. Nothing else is transmitted, and it is only used "
                     "for these four resolvers.\n\n"
                     "Leave this OFF if you do not want that. The other resolvers "
                     "(AdRock/vidrock, VidNest, ...) are not affected.")
            self.session.openWithCallback(askConfirm, MessageBox, text=info, type=MessageBox.TYPE_INFO)
        except Exception:
            printExc()

    def getSubOptionsList(self):
        tab = [
            config.plugins.iptvplayer.buforowanie,
            config.plugins.iptvplayer.buforowanie_m3u8,
            config.plugins.iptvplayer.buforowanie_rtmp,
            config.plugins.iptvplayer.showcover,
            # config.plugins.iptvplayer.ListaGraficzna,
            config.plugins.iptvplayer.pluginProtectedByPin,
            config.plugins.iptvplayer.configProtectedByPin,
            config.plugins.iptvplayer.configOwnPin,
            config.plugins.iptvplayer.osk_type,
            config.plugins.iptvplayer.plugin_autostart,
            config.plugins.iptvplayer.favourites_use_watched_flag,
            config.plugins.iptvplayer.mark_downloaded_items,
            config.plugins.iptvplayer.mark_favourite_items,
            config.plugins.iptvplayer.meta_tmdb,
            config.plugins.iptvplayer.meta_omdb,
            config.plugins.iptvplayer.storageExpertMode,
            config.plugins.iptvplayer.hostsListType,
            config.plugins.iptvplayer.skinforceallinternal,
            config.plugins.iptvplayer.IPTVDMShowNotification,
            config.plugins.iptvplayer.debugprint,
            config.plugins.iptvplayer.debug_max_size,
            config.plugins.iptvplayer.debug_on_limit
            # config.plugins.iptvplayer.captcha_bypass_free,
            # config.plugins.iptvplayer.captcha_bypass_pay
        ]
        players = []
        players.append(config.plugins.iptvplayer.defaultMoviePlayer0)
        players.append(config.plugins.iptvplayer.alternativeMoviePlayer0)
        players.append(config.plugins.iptvplayer.defaultMoviePlayer)
        players.append(config.plugins.iptvplayer.alternativeMoviePlayer)
        tab.extend(players)
        return tab

    def changePin(self, pin=None, start=False):
        # 'PUT_OLD_PIN', 'PUT_NEW_PIN', 'CONFIRM_NEW_PIN'
        if True is start:
            self.changingPinState = 'PUT_OLD_PIN'
            self.session.openWithCallback(self.changePin, IPTVPinWidget, title=_("Enter old pin"))
        else:
            if pin is None:
                return
            if 'PUT_OLD_PIN' == self.changingPinState:
                if pin == config.plugins.iptvplayer.pin.value:
                    self.changingPinState = 'PUT_NEW_PIN'
                    self.session.openWithCallback(self.changePin, IPTVPinWidget, title=_("Enter new pin"))
                else:
                    self.session.open(MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)
            elif 'PUT_NEW_PIN' == self.changingPinState:
                self.newPin = pin
                self.changingPinState = 'CONFIRM_NEW_PIN'
                self.session.openWithCallback(self.changePin, IPTVPinWidget, title=_("Confirm new pin"))
            elif 'CONFIRM_NEW_PIN' == self.changingPinState:
                if self.newPin == pin:
                    config.plugins.iptvplayer.pin.value = pin
                    config.plugins.iptvplayer.pin.save()
                    configfile.save()
                    self.session.open(MessageBox, _("Pin has been changed."), type=MessageBox.TYPE_INFO, timeout=5)
                else:
                    self.session.open(MessageBox, _("Confirmation error."), type=MessageBox.TYPE_INFO, timeout=5)

    def changeConfigPin(self, pin=None, start=False):
        # Mirrors changePin() above but manages the separate
        # config.plugins.iptvplayer.configPincode instead of the shared
        # plugin pin - see GetConfigExpectedPin() for how the two coexist
        # at check time. Unlike changePin(), the very first own-pin set
        # skips the old-pin step (there is nothing to confirm against yet),
        # same convention hostxxx's own PIN uses (_xxxOwnPinConfigured() in
        # hosts/hostxxx.py).
        alreadySet = 4 == len(config.plugins.iptvplayer.configPincode.value) and config.plugins.iptvplayer.configOwnPin.value
        if True is start:
            if alreadySet:
                self.changingConfigPinState = 'PUT_OLD_PIN'
                self.session.openWithCallback(self.changeConfigPin, IPTVPinWidget, title=_("Enter old pin") + " - " + _("Configuration"))
            else:
                self.changingConfigPinState = 'PUT_NEW_PIN'
                self.session.openWithCallback(self.changeConfigPin, IPTVPinWidget, title=_("Enter new pin") + " - " + _("Configuration"))
        else:
            if pin is None:
                return
            if 'PUT_OLD_PIN' == self.changingConfigPinState:
                if pin == config.plugins.iptvplayer.configPincode.value:
                    self.changingConfigPinState = 'PUT_NEW_PIN'
                    self.session.openWithCallback(self.changeConfigPin, IPTVPinWidget, title=_("Enter new pin") + " - " + _("Configuration"))
                else:
                    self.session.open(MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)
            elif 'PUT_NEW_PIN' == self.changingConfigPinState:
                self.newConfigPin = pin
                self.changingConfigPinState = 'CONFIRM_NEW_PIN'
                self.session.openWithCallback(self.changeConfigPin, IPTVPinWidget, title=_("Confirm new pin") + " - " + _("Configuration"))
            elif 'CONFIRM_NEW_PIN' == self.changingConfigPinState:
                if self.newConfigPin == pin:
                    # configOwnPin is already True here - this row (like
                    # the "Use own pin" toggle it depends on) is only
                    # reachable once it's switched on, same gating as
                    # hostxxx's "Set own pin" row.
                    config.plugins.iptvplayer.configPincode.value = pin
                    config.plugins.iptvplayer.configPincode.save()
                    configfile.save()
                    self.session.open(MessageBox, _("Pin has been changed."), type=MessageBox.TYPE_INFO, timeout=5)
                else:
                    self.session.open(MessageBox, _("Confirmation error."), type=MessageBox.TYPE_INFO, timeout=5)

    def hostsList(self):
        self.session.open(ConfigHostsMenu, GetListOfHostsNames())

    def extMoviePlayerList(self):
        self.session.open(ConfigExtMoviePlayer)


def GetAvailableMoviePlayers():
    # 'mini'/'standard' are always available (built in); the external ones
    # only when their binary is actually present. Shared by GetMoviePlayer()
    # (default/alternative slot resolution) and the "Select movie player"
    # blue-key menu (lists every one of these directly, not just the two
    # configured slots)
    availablePlayers = []
    if IsExecutable("/usr/bin/exteplayer3"):  # config.plugins.iptvplayer.exteplayer3path.value):
        availablePlayers.append('exteplayer')
    if IsExecutable('/usr/bin/gstplayer') or IsExecutable('/usr/bin/gstplayer2'):
        availablePlayers.append('extgstplayer')
    availablePlayers.append('mini')
    availablePlayers.append('standard')
    return availablePlayers


def GetMoviePlayer(buffering=False, useAlternativePlayer=False):
    printDBG("GetMoviePlayer buffering[%r], useAlternativePlayer[%r]" % (buffering, useAlternativePlayer))
    # select movie player
    availablePlayers = GetAvailableMoviePlayers()

    player = None
    alternativePlayer = None

    if buffering:
        player = config.plugins.iptvplayer.defaultMoviePlayer
        alternativePlayer = config.plugins.iptvplayer.alternativeMoviePlayer
    else:
        player = config.plugins.iptvplayer.defaultMoviePlayer0
        alternativePlayer = config.plugins.iptvplayer.alternativeMoviePlayer0

    if player.value == 'auto':
        player = CFakeMoviePlayerOption(availablePlayers[0], GetMoviePlayerName(availablePlayers[0]))
    try:
        availablePlayers.remove(player.value)
    except Exception:
        printExc()

    if alternativePlayer.value == 'auto':
        alternativePlayer = CFakeMoviePlayerOption(availablePlayers[0], GetMoviePlayerName(availablePlayers[0]))
    try:
        availablePlayers.remove(alternativePlayer.value)
    except Exception:
        printExc()

    if useAlternativePlayer:
        return alternativePlayer

    return player
