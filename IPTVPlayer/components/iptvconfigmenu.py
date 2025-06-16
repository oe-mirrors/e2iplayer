# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#

###################################################
# LOCAL import
###################################################

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetSkinsList, GetHostsList, GetEnabledHostsList, \
                                                          IsExecutable, CFakeMoviePlayerOption
from Plugins.Extensions.IPTVPlayer.components.configbase import ConfigBaseWidget, ConfigIPTVFileSelection, COLORS_DEFINITONS
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

from Components.config import config, ConfigSubsection, ConfigSelection, ConfigDirectory, ConfigYesNo, ConfigOnOff, ConfigInteger, \
                              ConfigText, getConfigListEntry, configfile, ConfigNothing, NoSave
from Tools.BoundFunction import boundFunction
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer = ConfigSubsection()

config.plugins.iptvplayer.plarformfpuabi = ConfigSelection(default="", choices=[("", ""), ("hard_float", _("Hardware floating point")), ("soft_float", _("Software floating point"))])
config.plugins.iptvplayer.exteplayer3path = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.set_curr_title = ConfigYesNo(default=False)
config.plugins.iptvplayer.curr_title_file = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.showcover = ConfigYesNo(default=True)
config.plugins.iptvplayer.deleteIcons = ConfigSelection(default="3", choices=[("0", _("after closing")), ("1", _("after day")), ("3", _("after three days")), ("7", _("after a week"))])
config.plugins.iptvplayer.allowedcoverformats = ConfigSelection(default="jpeg,png", choices=[("jpeg,png,gif", _("jpeg,png,gif")), ("jpeg,png", _("jpeg,png")), ("jpeg", _("jpeg")), ("all", _("all"))])
config.plugins.iptvplayer.showinextensions = ConfigYesNo(default=True)
config.plugins.iptvplayer.hostsListType = ConfigSelection(default="G", choices=[("G", _("Graphic services selector")), ("S", _("Simple list")), ("T", _("Tree list"))])
config.plugins.iptvplayer.showinMainMenu = ConfigYesNo(default=False)
config.plugins.iptvplayer.ListaGraficzna = ConfigYesNo(default=True)
config.plugins.iptvplayer.group_hosts = ConfigYesNo(default=True)
config.plugins.iptvplayer.NaszaSciezka = ConfigDirectory(default="/hdd/movie/")  # , fixed_size = False)
config.plugins.iptvplayer.bufferingPath = ConfigDirectory(default=config.plugins.iptvplayer.NaszaSciezka.value)  # , fixed_size = False)
config.plugins.iptvplayer.buforowanie = ConfigYesNo(default=False)
config.plugins.iptvplayer.buforowanie_m3u8 = ConfigYesNo(default=True)
config.plugins.iptvplayer.buforowanie_rtmp = ConfigYesNo(default=False)
config.plugins.iptvplayer.requestedBuffSize = ConfigInteger(2, (1, 120))
config.plugins.iptvplayer.requestedAudioBuffSize = ConfigInteger(256, (1, 10240))

config.plugins.iptvplayer.IPTVDMRunAtStart = ConfigYesNo(default=False)
config.plugins.iptvplayer.IPTVDMShowAfterAdd = ConfigYesNo(default=True)
config.plugins.iptvplayer.IPTVDMMaxDownloadItem = ConfigSelection(default="1", choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")])

config.plugins.iptvplayer.sortuj = ConfigYesNo(default=True)
config.plugins.iptvplayer.remove_diabled_hosts = ConfigYesNo(default=False)
config.plugins.iptvplayer.IPTVWebIterface = ConfigYesNo(default=False)
config.plugins.iptvplayer.plugin_autostart = ConfigYesNo(default=False)
config.plugins.iptvplayer.plugin_autostart_method = ConfigSelection(default="wizard", choices=[("wizard", "wizard"), ("infobar", "infobar")])

config.plugins.iptvplayer.osk_type = ConfigSelection(default="", choices=[("", _("Auto")), ("system", _("System")), ("own", _("Own model"))])
config.plugins.iptvplayer.osk_layout = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.osk_allow_suggestions = ConfigYesNo(default=True)
config.plugins.iptvplayer.osk_default_suggestions = ConfigSelection(default="", choices=[("", _("Auto")), ("none", _("None")), ("google", "google.com"), ("filmweb", "filmweb.pl"), ("imdb", "imdb.com"), ("filmstarts", "filmstarts.de")])
config.plugins.iptvplayer.osk_background_color = ConfigSelection(default="", choices=[('', _('Default')), ('transparent', _('Transparent')), ('#000000', _('Black')), ('#80000000', _('Darkgray')), ('#cc000000', _('Lightgray'))])


def GetMoviePlayerName(player):
    map = {"auto": _("auto"), "mini": _("internal"), "standard": _("standard"), 'exteplayer': _("external eplayer3"), 'extgstplayer': _("external gstplayer")}
    return map.get(player, _('unknown'))


def ConfigPlayer(player):
    return (player, GetMoviePlayerName(player))


config.plugins.iptvplayer.defaultMoviePlayer0 = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
config.plugins.iptvplayer.alternativeMoviePlayer0 = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
config.plugins.iptvplayer.defaultMoviePlayer = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])
config.plugins.iptvplayer.alternativeMoviePlayer = ConfigSelection(default="auto", choices=[ConfigPlayer("auto"), ConfigPlayer("mini"), ConfigPlayer("standard"), ConfigPlayer('extgstplayer'), ConfigPlayer('exteplayer')])

config.plugins.iptvplayer.SciezkaCache = ConfigDirectory(default="/hdd/IPTVCache/")  # , fixed_size = False)
config.plugins.iptvplayer.NaszaTMP = ConfigDirectory(default="/tmp/")  # , fixed_size = False)
config.plugins.iptvplayer.ZablokujWMV = ConfigYesNo(default=True)

config.plugins.iptvplayer.vkcom_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.vkcom_password = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.fichiercom_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.fichiercom_password = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.iptvplayer_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.iptvplayer_password = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.useSubtitlesParserExtension = ConfigYesNo(default=True)
config.plugins.iptvplayer.opensuborg_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.opensuborg_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.napisy24pl_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.napisy24pl_password = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.debugprint = ConfigSelection(default="", choices=[("", _("No")), ("console", _("Yes, to console")),
                                                                            ("debugfile", _("Yes, to file /hdd/iptv.dbg")),
                                                                            ("/tmp/iptv.dbg", _("Yes, to file /tmp/iptv.dbg")),
                                                                            ("/home/root/logs/iptv.dbg", _("Yes, to file /home/root/logs/iptv.dbg")),
                                                                            ])

# icons
config.plugins.iptvplayer.IconsSize = ConfigSelection(default="100", choices=[("135", "135x135"), ("120", "120x120"), ("100", "100x100")])
config.plugins.iptvplayer.numOfRow = ConfigSelection(default="0", choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("0", "auto")])
config.plugins.iptvplayer.numOfCol = ConfigSelection(default="0", choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"), ("6", "6"), ("7", "7"), ("8", "8"), ("0", "auto")])

config.plugins.iptvplayer.skinforceinternal = ConfigYesNo(default=False)
config.plugins.iptvplayer.skin = ConfigSelection(default="", choices=GetSkinsList())

# Pin code
config.plugins.iptvplayer.fakePin = ConfigSelection(default="fake", choices=[("fake", "****")])
config.plugins.iptvplayer.pin = ConfigText(default="0000", fixed_size=False)
config.plugins.iptvplayer.disable_live = ConfigYesNo(default=False)
config.plugins.iptvplayer.configProtectedByPin = ConfigYesNo(default=False)
config.plugins.iptvplayer.pluginProtectedByPin = ConfigYesNo(default=False)

config.plugins.iptvplayer.httpssslcertvalidation = ConfigYesNo(default=False)

# PROXY
config.plugins.iptvplayer.proxyurl = ConfigText(default="http://user:pass@ip:port", fixed_size=False)
config.plugins.iptvplayer.german_proxyurl = ConfigText(default="http://user:pass@ip:port", fixed_size=False)
config.plugins.iptvplayer.russian_proxyurl = ConfigText(default="http://user:pass@ip:port", fixed_size=False)
config.plugins.iptvplayer.ukrainian_proxyurl = ConfigText(default="http://user:pass@ip:port", fixed_size=False)
config.plugins.iptvplayer.alternative_proxy1 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)
config.plugins.iptvplayer.alternative_proxy2 = ConfigText(default="http://user:pass@ip:port", fixed_size=False)

# config.plugins.iptvplayer.captcha_bypass_order = ConfigSelection(default="", choices=[("", _("Internal, then external")), ("free", _("Only free")), ("free_pay", _("External free, then paid")), ("pay", _("External paid"))])
# config.plugins.iptvplayer.captcha_bypass_free = ConfigSelection(default="", choices=[("", _("None")), ("myjd", "MyJDownloader")])
# config.plugins.iptvplayer.captcha_bypass_pay = ConfigSelection(default="", choices=[("", _("None")), ("2captcha.com", "2captcha.com"), ("9kw.eu", "9kw.eu")])
config.plugins.iptvplayer.captcha_bypass = ConfigSelection(default="", choices=[("", _("Auto")), ("mye2i", "MyE2i"), ("2captcha.com", "2captcha.com"), ("9kw.eu", "9kw.eu")])

config.plugins.iptvplayer.api_key_9kweu = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_2captcha = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.myjd_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.myjd_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.myjd_jdname = ConfigText(default="", fixed_size=False)

config.plugins.iptvplayer.api_key_youtube = ConfigText(default="", fixed_size=False)

# Hosts lists
config.plugins.iptvplayer.fakeHostsList = ConfigSelection(default="fake", choices=[("fake", "  ")])


# External movie player settings
config.plugins.iptvplayer.fakExtMoviePlayerList = ConfigSelection(default="fake", choices=[("fake", "  ")])

# hidden options
# config.plugins.iptvplayer.hiddenAllVersionInUpdate = ConfigYesNo(default=False)
config.plugins.iptvplayer.hidden_ext_player_def_aspect_ratio = ConfigSelection(default="-1", choices=[("-1", _("default")), ("0", _("4:3 Letterbox")), ("1", _("4:3 PanScan")), ("2", _("16:9")), ("3", _("16:9 always")), ("4", _("16:10 Letterbox")), ("5", _("16:10 PanScan")), ("6", _("16:9 Letterbox"))])

config.plugins.iptvplayer.search_history_size = ConfigInteger(50, (0, 1000000))
config.plugins.iptvplayer.autoplay_start_delay = ConfigInteger(3, (0, 9))

config.plugins.iptvplayer.watched_item_color = ConfigSelection(default="#808080", choices=COLORS_DEFINITONS)
config.plugins.iptvplayer.usepycurl = ConfigYesNo(default=False)

config.plugins.iptvplayer.prefer_hlsdl_for_pls_with_alt_media = ConfigYesNo(default=True)

###################################################

config.plugins.iptvplayer.extplayer_summary = ConfigSelection(default="yes", choices=[('auto', _('Auto')), ('yes', _('Yes')), ('no', _('No'))])
config.plugins.iptvplayer.use_clear_iframe = ConfigYesNo(default=False)
config.plugins.iptvplayer.show_iframe = ConfigYesNo(default=True)
config.plugins.iptvplayer.iframe_file = ConfigIPTVFileSelection(fileMatch=r"^.*\.mvi$", default="/usr/share/enigma2/radio.mvi")
config.plugins.iptvplayer.clear_iframe_file = ConfigIPTVFileSelection(fileMatch=r"^.*\.mvi$", default="/usr/share/enigma2/black.mvi")

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

config.plugins.iptvplayer.extplayer_infobanner_clockformat = ConfigSelection(default="", choices=[("", _("None")), ("24", _("24 hour format ")), ("12", _("12 hour format "))])

config.plugins.iptvplayer.GSTplayer_no_IFD = ConfigYesNo(default=False)
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
        enabledByDefault = hostName not in ['ipla']
        setattr(config.plugins.iptvplayer, 'host' + hostName, ConfigIPTVHostOnOff(default=enabledByDefault))
    except Exception:
        printExc(hostName)


def GetListOfHostsNames():
    global gListOfHostsNames
    return gListOfHostsNames


###################################################


class ConfigMenu(ConfigBaseWidget):

    def __init__(self, session):
        printDBG("ConfigMenu.__init__ -------------------------------")
        self.list = []
        ConfigBaseWidget.__init__(self, session)
        # remember old
        self.showcoverOld = config.plugins.iptvplayer.showcover.value
        self.SciezkaCacheOld = config.plugins.iptvplayer.SciezkaCache.value
        self.remove_diabled_hostsOld = config.plugins.iptvplayer.remove_diabled_hosts.value
        self.enabledHostsListOld = GetEnabledHostsList()
        self.runtimeOptionsValues = self.getRuntimeOptionsValues()

    def __del__(self):
        printDBG("ConfigMenu.__del__ -------------------------------")

    def __onClose(self):
        printDBG("ConfigMenu.__onClose -----------------------------")
        ConfigBaseWidget.__onClose(self)

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self.setTitle(_("E2iPlayer - settings"))

    @staticmethod
    def fillConfigList(list,):
        list.append(getConfigListEntry(_("----- BASIC CONFIGURATION -----"),))
        list.append(getConfigListEntry(_("Virtual Keyboard type"), config.plugins.iptvplayer.osk_type))
        if config.plugins.iptvplayer.osk_type.value == 'own':
            list.append(getConfigListEntry(_("    Background color"), config.plugins.iptvplayer.osk_background_color))
            list.append(getConfigListEntry(_("    Show suggestions"), config.plugins.iptvplayer.osk_allow_suggestions))
            list.append(getConfigListEntry(_("    Default suggestions provider"), config.plugins.iptvplayer.osk_default_suggestions))
        list.append(getConfigListEntry(_("Initialize web interface"), config.plugins.iptvplayer.IPTVWebIterface))
        list.append(getConfigListEntry(_("Show IPTVPlayer in extension list"), config.plugins.iptvplayer.showinextensions))
        list.append(getConfigListEntry(_("Show IPTVPlayer in main menu"), config.plugins.iptvplayer.showinMainMenu))
        list.append(getConfigListEntry(_("E2iPlayer auto start at Enigma2 start"), config.plugins.iptvplayer.plugin_autostart))
        if config.plugins.iptvplayer.plugin_autostart.value:
            list.append(getConfigListEntry(_("Auto start method"), config.plugins.iptvplayer.plugin_autostart_method))
        list.append(getConfigListEntry(_("Disable live at plugin start"), config.plugins.iptvplayer.disable_live))
        list.append(getConfigListEntry(_("Use the PyCurl for HTTP(S) requests"), config.plugins.iptvplayer.usepycurl))
        list.append(getConfigListEntry(_("https - validate SSL certificates"), config.plugins.iptvplayer.httpssslcertvalidation))
        list.append(getConfigListEntry(_("----- SERVICE CONFIGURATION -----"),))
        list.append(getConfigListEntry(_("Services configuration"), config.plugins.iptvplayer.fakeHostsList))
        list.append(getConfigListEntry(_("Remove disabled services"), config.plugins.iptvplayer.remove_diabled_hosts))
        list.append(getConfigListEntry(_("----- SECURITY CONFIGURATION -----"),))
        list.append(getConfigListEntry(_("Pin protection for plugin"), config.plugins.iptvplayer.pluginProtectedByPin))
        list.append(getConfigListEntry(_("Pin protection for configuration"), config.plugins.iptvplayer.configProtectedByPin))
        if config.plugins.iptvplayer.pluginProtectedByPin.value or config.plugins.iptvplayer.configProtectedByPin.value:
            list.append(getConfigListEntry(_("Set pin code"), config.plugins.iptvplayer.fakePin))

        list.append(getConfigListEntry(_("----- SKIN CONFIGURATION -----"),))
        list.append(getConfigListEntry(_("Skin"), config.plugins.iptvplayer.skin))
        list.append(getConfigListEntry(_("Force internal Skin"), config.plugins.iptvplayer.skinforceinternal))
        list.append(getConfigListEntry(_("Info bar clock format"), config.plugins.iptvplayer.extplayer_infobanner_clockformat))
        list.append(getConfigListEntry(_("Player Skin"), config.plugins.iptvplayer.extplayer_skin))
        list.append(getConfigListEntry(_("Display thumbnails"), config.plugins.iptvplayer.showcover))
        if config.plugins.iptvplayer.showcover.value:
            list.append(getConfigListEntry(_("    Allowed formats of thumbnails"), config.plugins.iptvplayer.allowedcoverformats))
            list.append(getConfigListEntry(_("    Remove thumbnails"), config.plugins.iptvplayer.deleteIcons))
        # list.append(getConfigListEntry("Sort the lists?", config.plugins.iptvplayer.sortuj))
        list.append(getConfigListEntry(_("Graphic services selector"), config.plugins.iptvplayer.ListaGraficzna))
        if config.plugins.iptvplayer.ListaGraficzna.value is True:
            list.append(getConfigListEntry(_("    Enable hosts groups"), config.plugins.iptvplayer.group_hosts))
            list.append(getConfigListEntry(_("    Service icon size"), config.plugins.iptvplayer.IconsSize))
            if not GRIDSUPPORT:
                list.append(getConfigListEntry(_("    Number of rows"), config.plugins.iptvplayer.numOfRow))
                list.append(getConfigListEntry(_("    Number of columns"), config.plugins.iptvplayer.numOfCol))
        list.append(getConfigListEntry(_("VFD set current title:"), config.plugins.iptvplayer.set_curr_title))
        list.append(getConfigListEntry(_("Create LCD/VFD summary screen"), config.plugins.iptvplayer.extplayer_summary))

        list.append(getConfigListEntry(_("----- PROXIES CONFIGURATION -----"),))
        list.append(getConfigListEntry(_("Alternative proxy server (1)"), config.plugins.iptvplayer.alternative_proxy1))
        list.append(getConfigListEntry(_("Alternative proxy server (2)"), config.plugins.iptvplayer.alternative_proxy2))
        list.append(getConfigListEntry(_("Polish proxy server url"), config.plugins.iptvplayer.proxyurl))
        list.append(getConfigListEntry(_("German proxy server url"), config.plugins.iptvplayer.german_proxyurl))
        list.append(getConfigListEntry(_("Russian proxy server url"), config.plugins.iptvplayer.russian_proxyurl))
        list.append(getConfigListEntry(_("Ukrainian proxy server url"), config.plugins.iptvplayer.ukrainian_proxyurl))

        list.append(getConfigListEntry(_("----- STORAGE CONFIGURATION -----"),))
        list.append(getConfigListEntry(_("Folder for cache data"), config.plugins.iptvplayer.SciezkaCache))
        list.append(getConfigListEntry(_("Folder for temporary data"), config.plugins.iptvplayer.NaszaTMP))

        list.append(getConfigListEntry(_("----- BUFFERING CONFIGURATION -----"), ))
        list.append(getConfigListEntry(_("[HTTP] buffering"), config.plugins.iptvplayer.buforowanie))
        list.append(getConfigListEntry(_("[HLS/M3U8] buffering"), config.plugins.iptvplayer.buforowanie_m3u8))
        list.append(getConfigListEntry(_("[RTMP] buffering (rtmpdump required)"), config.plugins.iptvplayer.buforowanie_rtmp))
        if config.plugins.iptvplayer.buforowanie.value or config.plugins.iptvplayer.buforowanie_m3u8.value or config.plugins.iptvplayer.buforowanie_rtmp.value:
            list.append(getConfigListEntry(_("    Video buffer size [MB]"), config.plugins.iptvplayer.requestedBuffSize))
            list.append(getConfigListEntry(_("    Audio buffer size [KB]"), config.plugins.iptvplayer.requestedAudioBuffSize))
            list.append(getConfigListEntry(_("Buffering location"), config.plugins.iptvplayer.bufferingPath))

        list.append(getConfigListEntry(_("----- DOWNLOADING CONFIGURATION -----"), ))
        list.append(getConfigListEntry(_("Downloads location"), config.plugins.iptvplayer.NaszaSciezka))
        list.append(getConfigListEntry(_("Start download manager per default"), config.plugins.iptvplayer.IPTVDMRunAtStart))
        list.append(getConfigListEntry(_("Show download manager after adding new item"), config.plugins.iptvplayer.IPTVDMShowAfterAdd))
        list.append(getConfigListEntry(_("Number of downloaded files simultaneously"), config.plugins.iptvplayer.IPTVDMMaxDownloadItem))
        list.append(getConfigListEntry(_("%s e-mail") % ('My JDownloader'), config.plugins.iptvplayer.myjd_login))
        list.append(getConfigListEntry(_("%s password") % ('My JDownloader'), config.plugins.iptvplayer.myjd_password))
        list.append(getConfigListEntry(_("%s device name") % ('My JDownloader'), config.plugins.iptvplayer.myjd_jdname))
        list.append(getConfigListEntry(_("%s API KEY") % 'http://youtube.com/', config.plugins.iptvplayer.api_key_youtube))

        list.append(getConfigListEntry(_("----- CAPTCHA CONFIGURATION -----"), ))
        list.append(getConfigListEntry(_("Default captcha bypass"), config.plugins.iptvplayer.captcha_bypass))
        # list.append(getConfigListEntry(_("Captcha solver order"), config.plugins.iptvplayer.captcha_bypass_order))
        # list.append(getConfigListEntry(_("Captcha bypass free service"), config.plugins.iptvplayer.captcha_bypass_free))
        # list.append(getConfigListEntry(_("Captcha bypass paid service"), config.plugins.iptvplayer.captcha_bypass_pay))
        # if config.plugins.iptvplayer.captcha_bypass_pay.value == "9kw.eu":
        list.append(getConfigListEntry(_("%s API KEY") % 'https://9kw.eu/', config.plugins.iptvplayer.api_key_9kweu))
        # if config.plugins.iptvplayer.captcha_bypass_pay.value == "2captcha.com":
        list.append(getConfigListEntry(_("%s API KEY") % 'http://2captcha.com/', config.plugins.iptvplayer.api_key_2captcha))

        list.append(getConfigListEntry(_("----- SUBTITLES CONFIGURATION -----"), ))
        list.append(getConfigListEntry(_("Use subtitles parser extension if available"), config.plugins.iptvplayer.useSubtitlesParserExtension))
        list.append(getConfigListEntry("http://opensubtitles.org/ " + _("login"), config.plugins.iptvplayer.opensuborg_login))
        list.append(getConfigListEntry("http://opensubtitles.org/ " + _("password"), config.plugins.iptvplayer.opensuborg_password))
        list.append(getConfigListEntry("http://napisy24.pl/ " + _("login"), config.plugins.iptvplayer.napisy24pl_login))
        list.append(getConfigListEntry("http://napisy24.pl/ " + _("password"), config.plugins.iptvplayer.napisy24pl_password))
        list.append(getConfigListEntry("http://vk.com/ " + _("login"), config.plugins.iptvplayer.vkcom_login))
        list.append(getConfigListEntry("http://vk.com/ " + _("password"), config.plugins.iptvplayer.vkcom_password))
        list.append(getConfigListEntry("http://1fichier.com/ " + _("e-mail"), config.plugins.iptvplayer.fichiercom_login))
        list.append(getConfigListEntry("http://1fichier.com/ " + _("password"), config.plugins.iptvplayer.fichiercom_password))

        list.append(getConfigListEntry(_("----- PLAYERS & PLAYBACK CONFIGURATION -----"), ))
        list.append(getConfigListEntry(_("Autoplay start delay"), config.plugins.iptvplayer.autoplay_start_delay))
        list.append(getConfigListEntry(_("Block wmv files"), config.plugins.iptvplayer.ZablokujWMV))
        players = []
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
        list.append(getConfigListEntry(_("The default aspect ratio for the external player"), config.plugins.iptvplayer.hidden_ext_player_def_aspect_ratio))

        list.append(getConfigListEntry(_("----- OTHER SETTINGS -----"), ))
        list.append(getConfigListEntry(_("The number of items in the search history"), config.plugins.iptvplayer.search_history_size))
        list.append(getConfigListEntry(_("Write current title to file:"), config.plugins.iptvplayer.curr_title_file))
        list.append(getConfigListEntry(_("MIPS Floating Point Architecture"), config.plugins.iptvplayer.plarformfpuabi))
        list.append(getConfigListEntry(_("Prefer hlsld for playlist with alt. media"), config.plugins.iptvplayer.prefer_hlsdl_for_pls_with_alt_media))
        list.append(getConfigListEntry(_("Debug logs"), config.plugins.iptvplayer.debugprint))
        # list.append(getConfigListEntry(_("Hosts List Type-NOT FINISHED"), config.plugins.iptvplayer.hostsListType))

    def runSetup(self):
        self.list = []
        ConfigMenu.fillConfigList(self.list)
        ConfigBaseWidget.runSetup(self)

    def onSelectionChanged(self):
        currItem = self["config"].getCurrent()[1]
        if currItem in [config.plugins.iptvplayer.fakePin, config.plugins.iptvplayer.fakeHostsList, config.plugins.iptvplayer.fakExtMoviePlayerList]:
            self.isOkEnabled = True
            self.isSelectable = False
            self.setOKLabel()
        else:
            ConfigBaseWidget.onSelectionChanged(self)

    def save(self):
        ConfigBaseWidget.save(self)
        if self.showcoverOld != config.plugins.iptvplayer.showcover.value or \
            self.SciezkaCacheOld != config.plugins.iptvplayer.SciezkaCache.value:
            pass
            # plugin must be restarted if we wont to this options take effect

    def getRuntimeOptionsValues(self):
        valTab = []
        valTab.append(config.plugins.iptvplayer.skin.value)
        return valTab

    def getMessageAfterSave(self):
        if self.runtimeOptionsValues != self.getRuntimeOptionsValues():
            return _('Some settings will be applied only after GUI restart.')
        else:
            return ''

    def getMessageBeforeClose(self, afterSave):
        return ''

    def performCloseWithMessage(self, afterSave=True):
        self.close()

    def closeAfterMessage(self, arg=None):
        if arg:
            # self.doUpdate(True)
            self.close()
        else:
            self.close()

    def keyOK(self):
        curIndex = self["config"].getCurrentIndex()
        currItem = self["config"].list[curIndex][1]
        if isinstance(currItem, ConfigDirectory):
            def SetDirPathCallBack(curIndex, newPath):
                if None is not newPath:
                    self["config"].list[curIndex][1].value = newPath
            self.session.openWithCallback(boundFunction(SetDirPathCallBack, curIndex), IPTVDirectorySelectorWidget, currDir=currItem.value, title=_("Select directory"))
        elif config.plugins.iptvplayer.fakePin == currItem:
            self.changePin(start=True)
        elif config.plugins.iptvplayer.fakeHostsList == currItem:
            self.hostsList()
        elif config.plugins.iptvplayer.fakExtMoviePlayerList == currItem:
            self.extMoviePlayerList()
        else:
            ConfigBaseWidget.keyOK(self)

    def getSubOptionsList(self):
        tab = [
            config.plugins.iptvplayer.buforowanie,
            config.plugins.iptvplayer.buforowanie_m3u8,
            config.plugins.iptvplayer.buforowanie_rtmp,
            config.plugins.iptvplayer.showcover,
            config.plugins.iptvplayer.ListaGraficzna,
            config.plugins.iptvplayer.pluginProtectedByPin,
            config.plugins.iptvplayer.configProtectedByPin,
            config.plugins.iptvplayer.osk_type,
            config.plugins.iptvplayer.plugin_autostart
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

    def hostsList(self):
        self.session.open(ConfigHostsMenu, GetListOfHostsNames())

    def extMoviePlayerList(self):
        self.session.open(ConfigExtMoviePlayer)


def GetMoviePlayer(buffering=False, useAlternativePlayer=False):
    printDBG("GetMoviePlayer buffering[%r], useAlternativePlayer[%r]" % (buffering, useAlternativePlayer))
    # select movie player

    availablePlayers = []
    if IsExecutable("/usr/bin/exteplayer3"):  # config.plugins.iptvplayer.exteplayer3path.value):
        availablePlayers.append('exteplayer')
    if IsExecutable('/usr/bin/gstplayer'):
        availablePlayers.append('extgstplayer')
    availablePlayers.append('mini')
    availablePlayers.append('standard')

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
