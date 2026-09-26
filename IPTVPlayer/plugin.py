# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.components.iptvplayerwidget import E2iPlayerWidget
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu, GetConfigExpectedPin, IsPluginBrowserEntryShown
from Plugins.Extensions.IPTVPlayer.components.iptvpin import IPTVPinWidget
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

from enigma import getDesktop
from Screens.Screen import Screen
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Tools.BoundFunction import boundFunction
from Components.config import config


def Plugins(**kwargs):
    screenwidth = getDesktop(0).size().width()
    iconFile = "icons/%s/iptvlogo.png" % ("FHD" if screenwidth and screenwidth == 1920 else "HD")
    desc = _("Watch Videos Online")
    list = []
    if config.plugins.iptvplayer.plugin_autostart.value:
        if config.plugins.iptvplayer.plugin_autostart_method.value == 'wizard':
            list.append(PluginDescriptor(name=(("E2iPlayer")), description=desc, where=[PluginDescriptor.WHERE_WIZARD], fnc=(9, pluginAutostart), needsRestart=False))
        elif config.plugins.iptvplayer.plugin_autostart_method.value == 'infobar':
            list.append(PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc=pluginAutostartSetup))

    if IsPluginBrowserEntryShown():  # on unless another way to start the player is on and this one was switched off
        list.append(PluginDescriptor(name=(("E2iPlayer")), description=desc, where=[PluginDescriptor.WHERE_PLUGINMENU], icon=iconFile, fnc=main))
    list.append(PluginDescriptor(name=(("E2iPlayer")), description=desc, where=PluginDescriptor.WHERE_MENU, fnc=startIPTVfromMenu))
    if config.plugins.iptvplayer.showinextensions.value:
        list.append(PluginDescriptor(name=(("E2iPlayer")), description=desc, where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main))
    if config.plugins.iptvplayer.IPTVWebIterface.value:
        try:
            list.append(PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart, needsRestart=False))  # activating IPTV web interface
        except Exception:
            print("IPTVplayer Exception appending PluginDescriptor.WHERE_SESSIONSTART descriptor.")
    return list


######################################################
# Autostart from InfoBar - trick
######################################################
gInfoBar__init__ = None


def InfoBar__init__wrapper(self, *args, **kwargs):
    gInfoBar__init__(self, *args, **kwargs)
    self.onShow.append(doPluginAutostart)


def pluginAutostartSetup(reason, **kwargs):
    global gInfoBar__init__
    if reason == 0 and gInfoBar__init__ is None:
        from Screens.InfoBar import InfoBar
        gInfoBar__init__ = InfoBar.__init__
        InfoBar.__init__ = InfoBar__init__wrapper


def doPluginAutostart():
    from Screens.InfoBar import InfoBar
    InfoBar.instance.onShow.remove(doPluginAutostart)
    runMain(InfoBar.instance.session)
######################################################

####################################################
# Plugin configuration
####################################################


def startIPTVfromMenu(menuid, **kwargs):
    if menuid == "system":
        if config.plugins.iptvplayer.showinSystemMenu.value is True:
            return [(_("Configure %s") % 'E2iPlayer', mainSetup, "iptv_config", None)]
        return []
    elif menuid == "mainmenu" and config.plugins.iptvplayer.showinMainMenu.value is True:
        return [("E2iPlayer", main, "iptv_main", None)]
    else:
        return []


def mainSetup(session, **kwargs):
    if config.plugins.iptvplayer.configProtectedByPin.value:
        session.openWithCallback(boundFunction(pinCallback, session, runSetup, GetConfigExpectedPin()), IPTVPinWidget, title=_("Enter pin") + " - " + _("Configuration"))
    else:
        runSetup(session)


def runSetup(session):
    session.open(ConfigMenu)


def main(session, **kwargs):
    if config.plugins.iptvplayer.pluginProtectedByPin.value:
        session.openWithCallback(boundFunction(pinCallback, session, runMain, ''), IPTVPinWidget, title=_("Enter pin") + " - " + _("E2iPlayer"))
    else:
        runMain(session)


class pluginAutostart(Screen):
    def __init__(self, session):
        self.session = session
        Screen.__init__(self, session)
        self.onShow.append(self.onStart)

    def onStart(self):
        self.onShow.remove(self.onStart)
        runMain(self.session, self.iptvDoRunMain)

    def iptvDoRunMain(self, session):
        session.openWithCallback(self.iptvDoClose, E2iPlayerWidget)

    def iptvDoClose(self, **kwargs):
        self.close()


def doRunMain(session):
    session.open(E2iPlayerWidget)


def runMain(session, nextFunction=doRunMain):
    # clear the debug log(s) here so every entry path (incl. the wizard
    # autostart) behaves the same; ClearDebugLogsAtStart() itself honors
    # config.plugins.iptvplayer.debug_clear_on_start (default: on)
    cleared = False
    try:
        from Plugins.Extensions.IPTVPlayer.tools.iptvtools import ClearDebugLogsAtStart
        cleared = ClearDebugLogsAtStart()
    except Exception:
        pass
    # fire the binary probe once and drop the full system snapshot near
    # the top of the (now fresh) debug log
    try:
        from Plugins.Extensions.IPTVPlayer.components.iptvplayerinfoview import LogSystemInfoAtStartup
        LogSystemInfoAtStartup(force=cleared)
    except Exception:
        pass
    nextFunction(session)


def pinCallback(session, callbackFun, expectedPin, pin=None):
    # expectedPin lets the Configuration gate check against its own,
    # separately-configured pin (GetConfigExpectedPin()) instead of the
    # shared plugin one - same '' == "use the shared pin" convention as
    # checkPin() in iptvplayerwidget.py.
    if None is pin:
        return
    if 4 != len(expectedPin):
        expectedPin = config.plugins.iptvplayer.pin.value
    if pin != expectedPin:
        session.open(MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)
        return
    callbackFun(session)


def sessionstart(reason, **kwargs):
    if reason == 0 and 'session' in kwargs:
        try:
            from Plugins.Extensions.IPTVPlayer.web import settings as webSettings
            webSettings.session = kwargs['session']
            import Plugins.Extensions.IPTVPlayer.web.initiator  # noqa: F401
        except Exception as e:
            print("EXCEPTION initiating IPTVplayer WebComponent:", str(e))
