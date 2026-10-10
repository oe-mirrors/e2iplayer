# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#
# The config.plugins.iptvplayer options and the helpers which only read them.
# plugin.py loads this module at enigma2 start, so it must stay free of the
# screens and of the host framework (ihost, pCommon, urlparser...) - those are
# imported by iptvconfigmenu.py / iptvplayerwidget.py when the user opens them.

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc, GetSkinsList, GetHostsList
from Plugins.Extensions.IPTVPlayer.__init__ import _
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigDirectory, ConfigYesNo, ConfigOnOff, ConfigInteger, \
                              ConfigText, ConfigSelectionNumber
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
###################################################


COLORS_DEFINITONS = [("#000000", _("black")), ("#C0C0C0", _("silver")), ("#808080", _("gray")), ("#FFFFFF", _("white")), ("#800000", _("maroon")), ("#FF0000", _("red")), ("#800080", _("purple")), ("#FF00FF", _("fuchsia")),
                     ("#008000", _("green")), ("#00FF00", _("lime")), ("#808000", _("olive")), ("#FFFF00", _("yellow")), ("#000080", _("navy")), ("#0000FF", _("blue")), ("#008080", _("teal")), ("#00FFFF", _("aqua"))]


class ConfigIPTVFileSelection(ConfigDirectory):
    def __init__(self, ignoreCase=True, fileMatch=None, default="", visible_width=60):
        self.fileMatch = fileMatch
        self.ignoreCase = ignoreCase
        ConfigDirectory.__init__(self, default, visible_width)


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer = ConfigSubsection()

config.plugins.iptvplayer.exteplayer3path = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.set_curr_title = ConfigYesNo(default=False)
config.plugins.iptvplayer.curr_title_file = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.showcover = ConfigYesNo(default=True)
# negative = never (RemoveOldDirsIcons only deletes for values >= 0)
config.plugins.iptvplayer.deleteIcons = ConfigSelection(default="3", choices=[("0", _("after closing")), ("1", _("after day")), ("3", _("after three days")), ("7", _("after a week")), ("-1", _("never"))])
# config.plugins.iptvplayer.allowedcoverformats = ConfigSelection(default="jpeg,png", choices=[("jpeg,png,gif", _("jpeg,png,gif")), ("jpeg,png", _("jpeg,png")), ("jpeg", _("jpeg")), ("all", _("all"))])
config.plugins.iptvplayer.showinextensions = ConfigYesNo(default=True)
# the entry in Enigma2's plugin browser (default on = as it always was)
config.plugins.iptvplayer.showinPluginBrowser = ConfigYesNo(default=True)
# "T" (tree list) is intentionally not offered here - never implemented,
# would silently behave like "G" if selected
config.plugins.iptvplayer.hostsListType = ConfigSelection(default="G", choices=[("G", _("Graphic services selector")), ("S", _("List view")), ("P", _("Simple list"))])
config.plugins.iptvplayer.showinMainMenu = ConfigYesNo(default=False)
# the "Configure E2iPlayer" entry in Enigma2's system menu (default on = as it always was)
config.plugins.iptvplayer.showinSystemMenu = ConfigYesNo(default=True)
# config.plugins.iptvplayer.ListaGraficzna = ConfigYesNo(default=True)
config.plugins.iptvplayer.group_hosts = ConfigYesNo(default=True)
# layout of the settings screen itself: a list of categories that each open their own rows (default,
# see ConfigMenu) or the one long list it always was before
config.plugins.iptvplayer.configMenuView = ConfigSelection(default="categories", choices=[("list", _("Long list")), ("categories", _("Categories"))])
# legacy attributes are kept only to seed the renamed options (the settings-file key is the attribute name)
config.plugins.iptvplayer.NaszaSciezka = ConfigDirectory(default="/hdd/movie/")  # , fixed_size = False)
config.plugins.iptvplayer.DownloadsDir = ConfigDirectory(default=config.plugins.iptvplayer.NaszaSciezka.value)  # , fixed_size = False)
config.plugins.iptvplayer.bufferingPath = ConfigDirectory(default=config.plugins.iptvplayer.DownloadsDir.value)  # , fixed_size = False)
# not shown: the folder CacheDir / bufferingPath had before a start without its storage rerouted it (see IPTVPlayerWidget)
config.plugins.iptvplayer.CacheDirWanted = ConfigText(default="")
config.plugins.iptvplayer.bufferingPathWanted = ConfigText(default="")
config.plugins.iptvplayer.buforowanie = ConfigYesNo(default=False)
config.plugins.iptvplayer.buforowanie_m3u8 = ConfigYesNo(default=True)
config.plugins.iptvplayer.buforowanie_rtmp = ConfigYesNo(default=False)
# how far behind the live edge a buffered HLS live stream starts (hlsdl -s); "default" keeps hlsdl's own 2 minutes
config.plugins.iptvplayer.hlsdlLiveStartOffset = ConfigSelection(default="default", choices=[("default", _("Default (2 minutes)")), ("60", _("1 minute")), ("30", _("30 seconds")), ("15", _("15 seconds")), ("5", _("5 seconds")), ("0", _("At the live edge"))])
config.plugins.iptvplayer.requestedBuffSize = ConfigInteger(2, (1, 120))
config.plugins.iptvplayer.requestedAudioBuffSize = ConfigInteger(256, (1, 10240))

config.plugins.iptvplayer.IPTVDMRunAtStart = ConfigYesNo(default=False)
config.plugins.iptvplayer.IPTVDMShowAfterAdd = ConfigYesNo(default=True)
config.plugins.iptvplayer.IPTVDMMaxDownloadItem = ConfigSelection(default="1", choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"), ("10", "10"), ("20", "20"), ("30", "30"), ("40", "40"), ("50", "50")])
config.plugins.iptvplayer.IPTVDMShowNotification = ConfigYesNo(default=True)
# program for plain file downloads in the download manager; curl falls back
# to wget when the box has no curl binary
config.plugins.iptvplayer.http_downloader = ConfigSelection(default="wget", choices=[("wget", "wget"), ("curl", "curl")])
# container of DASH (MPD) downloads, which ffmpeg muxes; a host may still set its own (ff_out_container)
config.plugins.iptvplayer.dash_out_container = ConfigSelection(default="matroska", choices=[("matroska", "MKV"), ("mp4", "MP4"), ("mpegts", "TS")])
# same seconds-choices pattern as extplayer_infobar_timeout above - 5s
# matches the fixed duration IPTVDMNotification.showNotify() used before
# this was configurable
config.plugins.iptvplayer.IPTVDMNotificationDuration = ConfigSelection(default="5", choices=[
    ("1", "1 " + _("second")), ("2", "2 " + _("seconds")), ("3", "3 " + _("seconds")),
    ("4", "4 " + _("seconds")), ("5", "5 " + _("seconds")), ("6", "6 " + _("seconds")), ("7", "7 " + _("seconds")),
    ("8", "8 " + _("seconds")), ("9", "9 " + _("seconds")), ("10", "10 " + _("seconds"))
])

config.plugins.iptvplayer.sortuj = ConfigYesNo(default=True)
config.plugins.iptvplayer.IPTVWebIterface = ConfigYesNo(default=False)
config.plugins.iptvplayer.plugin_autostart = ConfigYesNo(default=False)
config.plugins.iptvplayer.plugin_autostart_method = ConfigSelection(default="wizard", choices=[("wizard", "wizard"), ("infobar", "infobar")])

config.plugins.iptvplayer.osk_type = ConfigSelection(default="", choices=[("", _("Auto")), ("system", _("System")), ("own", _("Own model"))])
config.plugins.iptvplayer.osk_layout = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.osk_allow_suggestions = ConfigYesNo(default=True)
config.plugins.iptvplayer.osk_allow_search_history = ConfigYesNo(default=True)
config.plugins.iptvplayer.osk_remember_last_search = ConfigYesNo(default=True)
config.plugins.iptvplayer.osk_default_suggestions = ConfigSelection(default="", choices=[("", _("Auto")), ("none", _("None")), ("google", "google.com"), ("bing", "bing.com"), ("duckduckgo", "duckduckgo.com"), ("filmweb", "filmweb.pl"), ("imdb", "imdb.com")])
config.plugins.iptvplayer.osk_allow_host_suggestions = ConfigYesNo(default=True)
config.plugins.iptvplayer.osk_background_color = ConfigSelection(default="", choices=[('', _('Default')), ('transparent', _('Transparent')), ('#000000', _('Black')), ('#80000000', _('Darkgray')), ('#cc000000', _('Lightgray'))])
# the tightest element (the HD/SD input line: 26pt base in a fixed 36px-tall
# row) is already close to its limit, so the positive end is kept modest to
# avoid clipping instead of matching NewVirtualKeyBoard's wider 0-30 range
config.plugins.iptvplayer.osk_font_size_offset = ConfigSelectionNumber(min=-6, max=6, stepwidth=1, default=0, wraparound=False)
config.plugins.iptvplayer.osk_searchfield_align = ConfigSelection(default="left", choices=[("left", _("Left")), ("right", _("Right"))])
config.plugins.iptvplayer.osk_show_flags = ConfigYesNo(default=True)
# digits-only keypad for page numbers and number settings - off = full keyboard / row input as before
config.plugins.iptvplayer.osk_numpad = ConfigYesNo(default=True)


def GetMoviePlayerName(player):
    map = {"auto": _("auto"), "mini": _("internal"), "standard": _("standard"), 'exteplayer': _("external eplayer3"), 'extgstplayer': _("external gstplayer")}
    return map.get(player, _('unknown'))


def ConfigPlayer(player):
    return (player, GetMoviePlayerName(player))


config.plugins.iptvplayer.defaultMoviePlayer0 = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
config.plugins.iptvplayer.alternativeMoviePlayer0 = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
config.plugins.iptvplayer.defaultMoviePlayer = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
config.plugins.iptvplayer.alternativeMoviePlayer = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
# "standard" keeps the blue-key "Select movie player" picker showing just
# the 4 configured default/alternative slots (+ Auto), like before
# GetAvailableMoviePlayers() started listing every player directly -
# "extended" opts into that full list instead
config.plugins.iptvplayer.moviePlayerPickerMode = ConfigSelection(default="standard", choices=[("standard", _("Standard")), ("extended", _("Extended"))])

config.plugins.iptvplayer.SciezkaCache = ConfigDirectory(default="/hdd/IPTVCache/")  # , fixed_size = False)
config.plugins.iptvplayer.CacheDir = ConfigDirectory(default=config.plugins.iptvplayer.SciezkaCache.value)  # , fixed_size = False)
config.plugins.iptvplayer.NaszaTMP = ConfigDirectory(default="/tmp/")  # , fixed_size = False)
config.plugins.iptvplayer.TmpDir = ConfigDirectory(default=config.plugins.iptvplayer.NaszaTMP.value)  # , fixed_size = False)
# real user data (favourites, history, host order, ...), kept apart from the disposable CacheDir
config.plugins.iptvplayer.ConfigDir = ConfigDirectory(default="/etc/enigma2/IPTVPlayer/")  # , fixed_size = False)
config.plugins.iptvplayer.storageExpertMode = ConfigYesNo(default=False)

# 0 = never; the fake*Delete entries are action triggers handled in keyOK()
config.plugins.iptvplayer.cookiesCacheDeleteAfterDays = ConfigSelectionNumber(min=0, max=365, stepwidth=1, default=0, wraparound=False)
config.plugins.iptvplayer.fakeCookiesCacheDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.jsCacheDeleteAfterDays = ConfigSelectionNumber(min=0, max=365, stepwidth=1, default=0, wraparound=False)
config.plugins.iptvplayer.fakeJSCacheDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.subtitlesCacheDeleteAfterDays = ConfigSelectionNumber(min=0, max=365, stepwidth=1, default=0, wraparound=False)
config.plugins.iptvplayer.fakeSubtitlesCacheDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.movieMetaDataCacheDeleteAfterDays = ConfigSelectionNumber(min=0, max=365, stepwidth=1, default=0, wraparound=False)
config.plugins.iptvplayer.fakeMovieMetaDataCacheDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeMoviePlayerDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeHostOrderDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeIconsCacheDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeSearchHistoryDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeFavouritesDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeAllCacheDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])
config.plugins.iptvplayer.fakeAllConfigDelete = ConfigSelection(default="fake", choices=[("fake", _("Delete now"))])

config.plugins.iptvplayer.ZablokujWMV = ConfigYesNo(default=True)

config.plugins.iptvplayer.vkcom_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.vkcom_password = ConfigSecret(default="", fixed_size=False)

config.plugins.iptvplayer.fichiercom_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.fichiercom_password = ConfigSecret(default="", fixed_size=False)

config.plugins.iptvplayer.iptvplayer_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.iptvplayer_password = ConfigSecret(default="", fixed_size=False)

config.plugins.iptvplayer.useSubtitlesParserExtension = ConfigYesNo(default=True)
config.plugins.iptvplayer.subsourceapi = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.subdlapi = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.wyzieapi = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.opensuborg_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.opensuborg_password = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.opensubcom_apikey = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.opensubcom_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.opensubcom_password = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.napisy24pl_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.napisy24pl_password = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.titulky_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.titulky_password = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.titlovi_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.titlovi_password = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.prijevodi_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.prijevodi_password = ConfigSecret(default="", fixed_size=False)

config.plugins.iptvplayer.debugprint = ConfigSelection(default="", choices=[("", _("No")), ("console", _("Yes, to console")),
                                                                            ("debugfile", _("Yes, to file /hdd/iptv.dbg")),
                                                                            ("/tmp/iptv.dbg", _("Yes, to file /tmp/iptv.dbg")),
                                                                            ("/home/root/logs/iptv.dbg", _("Yes, to file /home/root/logs/iptv.dbg")),
                                                                            ])
config.plugins.iptvplayer.debug_clear_on_start = ConfigYesNo(default=True)
config.plugins.iptvplayer.debug_max_size = ConfigSelection(default="0", choices=[
    ("0", _("unlimited")), ("2", "2 MB"), ("5", "5 MB"), ("10", "10 MB"),
    ("20", "20 MB"), ("50", "50 MB"), ("100", "100 MB")])
config.plugins.iptvplayer.debug_on_limit = ConfigSelection(default="truncate", choices=[
    ("truncate", _("truncate the file")),
    ("rotate", _("rotate (keep the old one as iptv-<date>.dbg)"))])
config.plugins.iptvplayer.debug_rotate_keep = ConfigSelection(default="3", choices=[
    ("1", "1"), ("2", "2"), ("3", "3"), ("5", "5"), ("10", "10")])
config.plugins.iptvplayer.debug_keep_ffmpeg_cmd = ConfigYesNo(default=True)
config.plugins.iptvplayer.debug_keep_js_scripts = ConfigYesNo(default=True)

# icons
config.plugins.iptvplayer.IconsSize = ConfigSelection(default="100", choices=[("100", "100x100"), ("120", "120x120"), ("135", "135x135")])
config.plugins.iptvplayer.numOfRow = ConfigSelection(default="0", choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("0", "auto")])
config.plugins.iptvplayer.numOfCol = ConfigSelection(default="0", choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"), ("6", "6"), ("7", "7"), ("8", "8"), ("0", "auto")])

config.plugins.iptvplayer.skinforceinternal = ConfigYesNo(default=False)
# "all screens" variant of skinforceinternal: also drives openChoiceBox()
# (on = our IPTVChoiceBoxWidget, off = native Enigma2 ChoiceBox)
config.plugins.iptvplayer.skinforceallinternal = ConfigYesNo(default=False)
config.plugins.iptvplayer.skin = ConfigSelection(default="", choices=GetSkinsList())
config.plugins.iptvplayer.use_colors = ConfigYesNo(default=True)
# clock/date in the app's own chrome header (E2iPlayerWidget,
# PlayerSelectorWidget, IPTVFavouritesMainWidget) - not to be confused
# with extplayer_infobanner_clockformat below, which is the clock inside
# the video PLAYER's on-screen info banner during playback
config.plugins.iptvplayer.show_header_clock = ConfigYesNo(default=True)

# Pin code
config.plugins.iptvplayer.fakePin = ConfigSelection(default="fake", choices=[("fake", "****")])
config.plugins.iptvplayer.pin = ConfigText(default="0000", fixed_size=False)
config.plugins.iptvplayer.disable_live = ConfigYesNo(default=False)
config.plugins.iptvplayer.configProtectedByPin = ConfigYesNo(default=False)
config.plugins.iptvplayer.pluginProtectedByPin = ConfigYesNo(default=False)
# Own, separate pin for the configuration screens instead of sharing the
# plugin-start pin above - same "own pin instead of the shared one" pattern
# as the PIN of every host (components/iptvhostpin.py).
config.plugins.iptvplayer.configOwnPin = ConfigYesNo(default=False)
config.plugins.iptvplayer.fakeConfigPin = ConfigSelection(default="fake", choices=[("fake", "****")])
config.plugins.iptvplayer.configPincode = ConfigText(default="0000", fixed_size=False)
# a PIN protected host (iptvhostpin.py): its right PIN counts until E2iPlayer is closed, or it is asked every time
config.plugins.iptvplayer.host_pin_remember = ConfigYesNo(default=True)

config.plugins.iptvplayer.httpssslcertvalidation = ConfigYesNo(default=False)

# PROXY - the default is a placeholder example the user overwrites; a proxy
# URL is legitimately http as often as https, so S5332 does not apply here
config.plugins.iptvplayer.alternative_proxy1 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)  # NOSONAR
config.plugins.iptvplayer.alternative_proxy2 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)  # NOSONAR
config.plugins.iptvplayer.alternative_proxy3 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)  # NOSONAR
config.plugins.iptvplayer.alternative_proxy4 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)  # NOSONAR
config.plugins.iptvplayer.alternative_proxy5 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)  # NOSONAR


def GetAlternativeProxyList():
    # (slot id, label, config) of every alternative proxy - the slot id is what a host's
    # "Use proxy server:" option stores; kept as literals so the labels stay translatable
    cp = config.plugins.iptvplayer
    return [("proxy_1", _("Alternative proxy server (1)"), cp.alternative_proxy1),
            ("proxy_2", _("Alternative proxy server (2)"), cp.alternative_proxy2),
            ("proxy_3", _("Alternative proxy server (3)"), cp.alternative_proxy3),
            ("proxy_4", _("Alternative proxy server (4)"), cp.alternative_proxy4),
            ("proxy_5", _("Alternative proxy server (5)"), cp.alternative_proxy5)]


def GetAlternativeProxyChoices():
    # choices for a host's "Use proxy server:" ConfigSelection
    return [("None", _("None"))] + [(slot, label) for slot, label, cfg in GetAlternativeProxyList()]


def GetAlternativeProxyUrl(slot):
    # the address of the chosen slot, '' for "None" or an unknown slot
    for currSlot, label, cfg in GetAlternativeProxyList():
        if currSlot == slot:
            return cfg.value
    return ''


# config.plugins.iptvplayer.captcha_bypass_order = ConfigSelection(default="", choices=[("", _("Internal, then external")), ("free", _("Only free")), ("free_pay", _("External free, then paid")), ("pay", _("External paid"))])
# config.plugins.iptvplayer.captcha_bypass_free = ConfigSelection(default="", choices=[("", _("None")), ("myjd", "MyJDownloader")])
# config.plugins.iptvplayer.captcha_bypass_pay = ConfigSelection(default="", choices=[("", _("None")), ("2captcha.com", "2captcha.com"), ("9kw.eu", "9kw.eu")])
config.plugins.iptvplayer.captcha_bypass = ConfigSelection(default="", choices=[("", _("Auto")), ("mye2i", "MyE2i"), ("2captcha.com", "2captcha.com"), ("9kw.eu", "9kw.eu"), ("deathbycaptcha.com", "DeathByCaptcha")])

# MyE2i: on = the address typed by hand needs a six-digit code (shown in the window title)
# and the QR code carries a one-time key, so nobody else in the network can hand results
# to the receiver; off = the plain address opens the page directly (the original behaviour)
config.plugins.iptvplayer.mye2i_security = ConfigYesNo(default=False)
# MyE2i: the browser the start page offers to open itself in on an Android phone (an
# intent:// link, see libs/mye2i_launcher.py) - the camera app opens the QR code in the
# default browser, mostly Chrome without extensions; "custom" = own launcher URI with {url} / {address}
config.plugins.iptvplayer.mye2i_browser = ConfigSelection(default="", choices=[("", _("Default browser")), ("kiwi", "Kiwi Browser"), ("yandex", "Yandex Browser"), ("edge", "Microsoft Edge"), ("edge_canary", "Microsoft Edge Canary"), ("edge_beta", "Microsoft Edge Beta"), ("edge_dev", "Microsoft Edge Dev"), ("custom", _("Own launcher URI"))])
config.plugins.iptvplayer.mye2i_launcher_uri = ConfigText(default="", fixed_size=False)
# MyE2i: close the start page (the box's page with the button) once the result reached the box;
# the tab with the captcha always closes itself
config.plugins.iptvplayer.mye2i_close_start_page = ConfigYesNo(default=False)

config.plugins.iptvplayer.api_key_9kweu = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_2captcha = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.deathbycaptcha_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.deathbycaptcha_password = ConfigSecret(default="", fixed_size=False)

config.plugins.iptvplayer.myjd_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.myjd_password = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.myjd_jdname = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.api_key_youtube = ConfigSecret(default="", fixed_size=False)

# Hosts lists
config.plugins.iptvplayer.fakeHostsList = ConfigSelection(default="fake", choices=[("fake", "  ")])


# External movie player settings
config.plugins.iptvplayer.fakExtMoviePlayerList = ConfigSelection(default="fake", choices=[("fake", "  ")])

# torrent playback through a local TorrServer (libs/torrserver.py) - the user installs the binary;
# off by default because a torrent client also sends data to other peers unless upload is disabled
config.plugins.iptvplayer.torrserver_enabled = ConfigYesNo(default=False)
# empty = search $PATH and the usual folders; a folder or the full path of the binary (OK in the
# configuration opens a file browser, the web interface takes it as text)
config.plugins.iptvplayer.torrserver_path = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.torrserver_port = ConfigInteger(8090, (1024, 65535))
config.plugins.iptvplayer.torrserver_cache = ConfigSelection(default="64", choices=[("32", "32 MB"), ("64", "64 MB"), ("128", "128 MB"), ("256", "256 MB"), ("512", "512 MB")])
config.plugins.iptvplayer.torrserver_preload = ConfigSelection(default="50", choices=[("0", _("Off")), ("25", "25%"), ("50", "50%"), ("75", "75%"), ("100", "100%")])
config.plugins.iptvplayer.torrserver_upload = ConfigYesNo(default=False)
config.plugins.iptvplayer.torrserver_stop_on_exit = ConfigYesNo(default=True)
# TorrServer's own web interface (http://<receiver>:<port>) from other devices of the home network; off =
# bound to 127.0.0.1, only E2iPlayer reaches it (TorrServer's web interface has no password by default)
config.plugins.iptvplayer.torrserver_lan = ConfigYesNo(default=False)
# cache in RAM (default) or in a folder on HDD/USB - TorrServer then keeps the pieces in <folder>/TorrServer
config.plugins.iptvplayer.torrserver_cache_location = ConfigSelection(default="ram", choices=[("ram", _("RAM")), ("disk", _("Folder on HDD / USB"))])
config.plugins.iptvplayer.torrserver_cache_dir = ConfigDirectory(default="/media/hdd/")
config.plugins.iptvplayer.torrserver_disk_cache = ConfigSelection(default="2048", choices=[("1024", "1 GB"), ("2048", "2 GB"), ("4096", "4 GB"), ("8192", "8 GB"), ("16384", "16 GB"), ("32768", "32 GB")])
config.plugins.iptvplayer.torrserver_remove_cache = ConfigYesNo(default=True)
# TorrServer's own settings (BTSets) - values as TorrServer takes them: rates in KB/s, timeout in seconds
config.plugins.iptvplayer.torrserver_connections = ConfigSelection(default="25", choices=[("10", "10"), ("25", "25"), ("50", "50"), ("100", "100"), ("200", "200")])
config.plugins.iptvplayer.torrserver_dl_limit = ConfigSelection(default="0", choices=[("0", _("unlimited")), ("512", "512 KB/s"), ("1024", "1 MB/s"), ("2048", "2 MB/s"), ("5120", "5 MB/s"), ("10240", "10 MB/s")])
config.plugins.iptvplayer.torrserver_ul_limit = ConfigSelection(default="512", choices=[("0", _("unlimited")), ("128", "128 KB/s"), ("256", "256 KB/s"), ("512", "512 KB/s"), ("1024", "1 MB/s"), ("2048", "2 MB/s")])
config.plugins.iptvplayer.torrserver_readahead = ConfigSelection(default="95", choices=[("50", "50%"), ("75", "75%"), ("95", "95%"), ("100", "100%")])
config.plugins.iptvplayer.torrserver_timeout = ConfigSelection(default="30", choices=[("30", "30 s"), ("60", "60 s"), ("120", "2 min"), ("300", "5 min")])
config.plugins.iptvplayer.torrserver_encrypt = ConfigYesNo(default=False)
config.plugins.iptvplayer.torrserver_dlna = ConfigYesNo(default=False)

# hidden options
# config.plugins.iptvplayer.hiddenAllVersionInUpdate = ConfigYesNo(default=False)

config.plugins.iptvplayer.search_history_size = ConfigInteger(50, (0, 1000000))
config.plugins.iptvplayer.enableT9MainList = ConfigYesNo(default=True)
config.plugins.iptvplayer.rememberHistorySelection = ConfigYesNo(default=True)
config.plugins.iptvplayer.autoplay_start_delay = ConfigInteger(3, (0, 9))

config.plugins.iptvplayer.favourites_use_watched_flag = ConfigYesNo(default=True)
config.plugins.iptvplayer.watched_item_color = ConfigSelection(default="#808080", choices=COLORS_DEFINITONS)
config.plugins.iptvplayer.started_item_color = ConfigSelection(default="#FFFF00", choices=COLORS_DEFINITONS)
# downloaded / favourite items of a host list: colour of the title and the small marker at the end of the
# row; switched off = neither colour nor marker (same idea as the watched flag)
config.plugins.iptvplayer.mark_downloaded_items = ConfigYesNo(default=True)
config.plugins.iptvplayer.downloaded_item_color = ConfigSelection(default="#00FF00", choices=COLORS_DEFINITONS)
config.plugins.iptvplayer.mark_favourite_items = ConfigYesNo(default=True)
config.plugins.iptvplayer.favourite_item_color = ConfigSelection(default="#00FFFF", choices=COLORS_DEFINITONS)
# movie/series details on the info screen of hosts which support it (libs/moviemeta.py), asked in
# the order TMDb, IMDb, TVmaze (series), Cinemeta, OMDb; TMDb and OMDb need the user's own free API
# key, the others none; TMDb and IMDb texts come in meta_language where they have them
config.plugins.iptvplayer.meta_tmdb = ConfigYesNo(default=True)
config.plugins.iptvplayer.meta_imdb = ConfigYesNo(default=True)
config.plugins.iptvplayer.meta_tvmaze = ConfigYesNo(default=True)
config.plugins.iptvplayer.meta_cinemeta = ConfigYesNo(default=True)
config.plugins.iptvplayer.meta_omdb = ConfigYesNo(default=False)
config.plugins.iptvplayer.meta_language = ConfigSelection(default="auto", choices=[("auto", _("Auto")), ("ar", _("Arabic")), ("cs", _("Czech")), ("de", _("German")), ("el", _("Greek")), ("en", _("English")), ("es", _("Spanish")), ("fr", _("French")), ("hu", _("Hungarian")), ("it", _("Italian")), ("nl", _("Dutch")), ("pl", _("Polish")), ("pt", _("Portuguese")), ("ru", _("Russian")), ("tr", _("Turkish")), ("uk", _("Ukrainian"))])
config.plugins.iptvplayer.meta_tmdb_apikey = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.meta_omdb_apikey = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.sidecar_enabled = ConfigYesNo(default=True)
config.plugins.iptvplayer.normalize_media_names = ConfigYesNo(default=True)
# OFF by default. The resolvers VidCore / VidUp / VidFast cannot decrypt
# their links on the box - they send the site's encrypted stream token
# (which carries the TMDb id of what is being played) to the third-party
# web service enc-dec.app (VidEasy, VidLink and Peachify decrypt on the
# box since 09.10.2026). The settings screen makes the user confirm twice before
# this can be turned on (see ConfigMenu._confirmExternalResolve).
config.plugins.iptvplayer.allow_external_resolve = ConfigYesNo(default=False)


def IsPluginBrowserEntryShown():
    # The plugin browser, the extension list (blue button) and the main menu are the three places the
    # player itself can be started from. The browser entry stays on whenever it would otherwise be the
    # last way in (also if the settings file was edited by hand), so switching everything off can never
    # lock the player out.
    cp = config.plugins.iptvplayer
    return cp.showinPluginBrowser.value or not (cp.showinextensions.value or cp.showinMainMenu.value)


def IsExternalResolveAllowed():
    # asked by parserVIDCORE (vidcore / vidup / vidfast) before it contacts
    # enc-dec.app, and by the hosts that offer those links
    return config.plugins.iptvplayer.allow_external_resolve.value


def IsSidecarEnabled():
    # single central place hosts ask whether to create sidecar .txt/.jpg files,
    # instead of each host keeping its own copy of this config option
    return config.plugins.iptvplayer.sidecar_enabled.value


def GetConfigExpectedPin():
    # '' means "no own pin configured" - checkPin() in iptvplayerwidget.py
    # (and pinCallback() in plugin.py) already fall back to the shared
    # config.plugins.iptvplayer.pin in that case, same convention as the
    # host PINs (iptvhostpin.GetHostPinCode()).
    if config.plugins.iptvplayer.configOwnPin.value and 4 == len(config.plugins.iptvplayer.configPincode.value):
        return config.plugins.iptvplayer.configPincode.value
    return ''


def IsMediaNamingNormalized():
    # shared toggle for every host that produces media-server friendly item
    # titles ("Show - SxxExx - Title" / "Title (Year)" / "Show - Title
    # (YYYY-MM-DD)") instead of the site's raw label - currently the mediathek
    # hosts (ARD/ZDF/ARTE/ORF/SRG), serienstream.to and hdfilme. The download
    # filename is derived from the item title, so this normalises that too.
    return config.plugins.iptvplayer.normalize_media_names.value


config.plugins.iptvplayer.usepycurl = ConfigYesNo(default=False)

###################################################

config.plugins.iptvplayer.extplayer_summary = ConfigSelection(default="yes", choices=[('auto', _('Auto')), ('yes', _('Yes')), ('no', _('No'))])
config.plugins.iptvplayer.use_clear_iframe = ConfigYesNo(default=False)
config.plugins.iptvplayer.show_iframe = ConfigYesNo(default=True)
config.plugins.iptvplayer.iframe_file = ConfigIPTVFileSelection(fileMatch=r"^.*\.mvi$", default="/usr/share/enigma2/radio.mvi")
config.plugins.iptvplayer.clear_iframe_file = ConfigIPTVFileSelection(fileMatch=r"^.*\.mvi$", default="/usr/share/enigma2/black.mvi")
# screensaver (iptvscreensaver.py: moving logo/cover, title and clock on black) after this many seconds without a key:
# audio = audio-only playback in the external player; menu = every E2iPlayer screen except the players, where
# "hide" only hides the E2iPlayer windows while live TV runs behind them (the black screensaver without live TV)
config.plugins.iptvplayer.screensaver_audio = ConfigSelection(default="60", choices=[("0", _("Off")), ("30", _("30 seconds")), ("60", _("1 minute")), ("120", "2 " + _("minutes")), ("300", "5 " + _("minutes"))])
config.plugins.iptvplayer.screensaver_menu = ConfigSelection(default="300", choices=[("0", _("Off")), ("60", _("1 minute")), ("120", "2 " + _("minutes")), ("300", "5 " + _("minutes")), ("600", "10 " + _("minutes")), ("900", "15 " + _("minutes"))])
config.plugins.iptvplayer.screensaver_menu_mode = ConfigSelection(default="hide", choices=[("hide", _("Hide the menu (live TV visible)")), ("black", _("Black screensaver"))])

config.plugins.iptvplayer.remember_last_position = ConfigYesNo(default=False)
config.plugins.iptvplayer.remember_last_position_time = ConfigInteger(0, (0, 99))
config.plugins.iptvplayer.fakeExtePlayer3 = ConfigSelection(default="fake", choices=[("fake", " ")])
config.plugins.iptvplayer.rambuffer_sizemb_network_proto = ConfigInteger(0, (0, 999))
config.plugins.iptvplayer.rambuffer_sizemb_files = ConfigInteger(0, (0, 999))
config.plugins.iptvplayer.aac_software_decode = ConfigYesNo(default=False)
config.plugins.iptvplayer.ac3_software_decode = ConfigYesNo(default=False)
config.plugins.iptvplayer.eac3_software_decode = ConfigYesNo(default=False)
config.plugins.iptvplayer.dts_software_decode = ConfigYesNo(default=False)
config.plugins.iptvplayer.wma_software_decode = ConfigYesNo(default=True)
config.plugins.iptvplayer.mp3_software_decode = ConfigYesNo(default=False)
config.plugins.iptvplayer.stereo_software_decode = ConfigYesNo(default=False)
config.plugins.iptvplayer.software_decode_as = ConfigSelection(default="pcm", choices=[("pcm", "PCM"), ("lpcm", "LPCM")])
config.plugins.iptvplayer.aac_mix = ConfigSelection(default=None, choices=[(None, _("from E2 settings"))])
config.plugins.iptvplayer.ac3_mix = ConfigSelection(default=None, choices=[(None, _("from E2 settings"))])

config.plugins.iptvplayer.extplayer_infobar_timeout = ConfigSelection(default="5", choices=[
    ("1", "1 " + _("second")), ("2", "2 " + _("seconds")), ("3", "3 " + _("seconds")),
    ("4", "4 " + _("seconds")), ("5", "5 " + _("seconds")), ("6", "6 " + _("seconds")), ("7", "7 " + _("seconds")),
    ("8", "8 " + _("seconds")), ("9", "9 " + _("seconds")), ("10", "10 " + _("seconds"))
])
config.plugins.iptvplayer.extplayer_aspect = ConfigSelection(default=None, choices=[(None, _("from E2 settings"))])
config.plugins.iptvplayer.extplayer_policy = ConfigSelection(default=None, choices=[(None, _("from E2 settings"))])
config.plugins.iptvplayer.extplayer_policy2 = ConfigSelection(default=None, choices=[(None, _("from E2 settings"))])

config.plugins.iptvplayer.extplayer_subtitle_auto_enable = ConfigYesNo(default=True)
config.plugins.iptvplayer.extplayer_subtitle_font = ConfigSelection(default="Regular", choices=[("Regular", "Regular")])
config.plugins.iptvplayer.extplayer_subtitle_font_size = ConfigInteger(40, (20, 90))
config.plugins.iptvplayer.extplayer_subtitle_font_color = ConfigSelection(default="#FFFFFF", choices=COLORS_DEFINITONS)
config.plugins.iptvplayer.extplayer_subtitle_wrapping_enabled = ConfigYesNo(default=False)
config.plugins.iptvplayer.extplayer_subtitle_line_height = ConfigInteger(40, (20, 999))
config.plugins.iptvplayer.extplayer_subtitle_line_spacing = ConfigInteger(4, (0, 99))
config.plugins.iptvplayer.extplayer_subtitle_background = ConfigSelection(default="#000000", choices=[('transparent', _('Transparent')), ('#000000', _('Black')), ('#80000000', _('Darkgray')), ('#cc000000', _('Lightgray'))])

config.plugins.iptvplayer.extplayer_subtitle_border_color = ConfigSelection(default="#000000", choices=COLORS_DEFINITONS)
config.plugins.iptvplayer.extplayer_subtitle_shadow_color = ConfigSelection(default="#000000", choices=COLORS_DEFINITONS)

config.plugins.iptvplayer.extplayer_subtitle_border_enabled = ConfigYesNo(default=True)
config.plugins.iptvplayer.extplayer_subtitle_shadow_enabled = ConfigYesNo(default=False)

config.plugins.iptvplayer.extplayer_subtitle_border_width = ConfigInteger(3, (1, 6))
config.plugins.iptvplayer.extplayer_subtitle_shadow_xoffset = ConfigInteger(3, (-6, 6))
config.plugins.iptvplayer.extplayer_subtitle_shadow_yoffset = ConfigInteger(3, (-6, 6))
config.plugins.iptvplayer.extplayer_subtitle_pos = ConfigInteger(50, (0, 400))
config.plugins.iptvplayer.extplayer_subtitle_box_valign = ConfigSelection(default="bottom", choices=[("bottom", _("bottom")), ("center", _("center")), ("top", _("top"))])
config.plugins.iptvplayer.extplayer_subtitle_box_height = ConfigInteger(240, (50, 400))

config.plugins.iptvplayer.extplayer_infobanner_clockformat = ConfigSelection(default="", choices=[("", _("None")), ("24", _("24 hour format")), ("12", _("12 hour format"))])

config.plugins.iptvplayer.extplayer_skin = ConfigSelection(default="default", choices=[("default", _("default")), ("black", _("black")), ("red", _("red")), ("blue", _("blue")), ("green", _("green")), ("black-white", _("black&white")), ("cobalt", _("cobalt")), ("jersey", _("jersey")), ("navy", _("navy")), ("line", _("line"))])


########################################################
# Generate list of hosts options for Enabling/Disabling
########################################################

class ConfigIPTVHostOnOff(ConfigOnOff):
    def __init__(self, default=False):
        ConfigOnOff.__init__(self, default=default)


gListOfHostsNames = GetHostsList()
for hostName in gListOfHostsNames:
    try:
        # as default all hosts are enabled
        setattr(config.plugins.iptvplayer, 'host' + hostName, ConfigIPTVHostOnOff(default=True))
    except Exception:
        printExc(hostName)


def GetListOfHostsNames():
    return gListOfHostsNames
