# -*- coding: utf-8 -*-
# PIN protection per host: every host can be protected by the player PIN or by its own PIN.
# The settings are created on first use (config.plugins.iptvplayer.pinhost*_<host>), so a host
# needs no code for it: IHost.isProtectedByPinCode()/getPinCode() read them, the host settings
# screen shows them (GetHostPinConfigList), and the right PIN unlocks the host until E2iPlayer
# is closed (also for its items in the favourites) - unless config host_pin_remember is off.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetHostTitle
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, configfile, getConfigListEntry, ConfigSelection, ConfigText, ConfigYesNo
from Screens.MessageBox import MessageBox
import re
###################################################

HOST_PIN_ACTION = 'host_pin'

# the PIN settings hostxxx had before: protection (on by default there), own pin yes/no, own pin
_LEGACY_SETTINGS = {'xxx': ('xxxwymagajpin', 'xxxownpin', 'xxxpincode', True)}

_unlockedHosts = set()


def _storedValue(name):
    try:
        return config.plugins.iptvplayer.content.stored_values.get(name)
    except Exception:
        return None


def _storedBool(value):
    # the values Enigma2's ConfigBoolean accepts as True
    return str(value).lower() in ('1', 'enable', 'enabled', 'on', 'true', 'yes')


def _legacyDefaults(hostName):
    protect, ownPin, pinCode = False, False, ''
    legacy = _LEGACY_SETTINGS.get(hostName)
    if legacy:
        stored = _storedValue(legacy[0])
        protect = legacy[3] if stored is None else _storedBool(stored)
        if _storedBool(_storedValue(legacy[1])):
            # an own pin equal to the old default "0000" was never written to the settings file
            code = _storedValue(legacy[2]) or '0000'
            if 4 == len(code):
                ownPin, pinCode = True, code
    return protect, ownPin, pinCode


def _isKnownHost(hostName):
    # only hosts of the host list get settings (not e.g. the favourite of a removed host)
    return bool(hostName) and hasattr(config.plugins.iptvplayer, 'host' + hostName)


def _settings(hostName):
    # (protected, own pin, pin code, OK-only action row) of the host, created on first use
    name = 'pinhost_' + hostName
    if not hasattr(config.plugins.iptvplayer, name):
        protect, ownPin, pinCode = _legacyDefaults(hostName)
        setattr(config.plugins.iptvplayer, name, ConfigYesNo(default=protect))
        setattr(config.plugins.iptvplayer, 'pinhostown_' + hostName, ConfigYesNo(default=ownPin))
        setattr(config.plugins.iptvplayer, 'pinhostcode_' + hostName, ConfigText(default=pinCode, fixed_size=False))
        setattr(config.plugins.iptvplayer, 'pinhostaction_' + hostName, ConfigSelection(default="fake", choices=[("fake", "  ")]))
    return (getattr(config.plugins.iptvplayer, name), getattr(config.plugins.iptvplayer, 'pinhostown_' + hostName),
            getattr(config.plugins.iptvplayer, 'pinhostcode_' + hostName), getattr(config.plugins.iptvplayer, 'pinhostaction_' + hostName))


def HostNameOf(hostObj):
    # "Plugins.Extensions.IPTVPlayer.hosts.hostyoutube" -> "youtube"
    module = getattr(type(hostObj), '__module__', '') or ''
    name = module.rsplit('.', 1)[-1]
    return name[4:] if name.startswith('host') else ''


def GetHostDisplayTitle(hostName):
    # hosts named by their address: "https://www.site.example/" -> "site.example"
    try:
        title = re.sub(r'^https?://(www\.)?', '', str(GetHostTitle(hostName) or '').strip()).rstrip('/')
    except Exception:
        printExc()
        title = ''
    return title or hostName


def IsHostPinProtected(hostName):
    if not _isKnownHost(hostName):
        return False
    try:
        return _settings(hostName)[0].value
    except Exception:
        printExc()
        return False


def _ownPinSet(hostName):
    settings = _settings(hostName)
    return settings[1].value and 4 == len(settings[2].value)


def GetHostPinCode(hostName):
    # the host's own PIN, '' = the player PIN
    try:
        if _isKnownHost(hostName) and _ownPinSet(hostName):
            return _settings(hostName)[2].value
    except Exception:
        printExc()
    return ''


def GetExpectedHostPin(hostName):
    return GetHostPinCode(hostName) or config.plugins.iptvplayer.pin.value


def IsHostUnlocked(hostName):
    return hostName in _unlockedHosts


def SetHostUnlocked(hostName):
    if hostName:
        _unlockedHosts.add(hostName)


def ClearUnlockedHosts():
    _unlockedHosts.clear()


def HostNeedsPin(hostName):
    return IsHostPinProtected(hostName) and not IsHostUnlocked(hostName)


def _rememberPin():
    try:
        return config.plugins.iptvplayer.host_pin_remember.value
    except Exception:
        return True


def AskHostPin(session, hostName, onUnlocked, onWrong=None, onCancel=None):
    # asks for the host's PIN; the right one unlocks the host until E2iPlayer is closed - or, with
    # "Remember a host's pin" off, only for onUnlocked() (the next opening asks again)
    from Plugins.Extensions.IPTVPlayer.components.iptvpin import IPTVPinWidget

    def checked(pin=None):
        if pin is None:
            if onCancel:
                onCancel()
        elif pin == GetExpectedHostPin(hostName):
            SetHostUnlocked(hostName)
            try:
                onUnlocked()
            finally:
                if not _rememberPin():
                    _unlockedHosts.discard(hostName)
        else:
            session.openWithCallback(lambda *args: onWrong() if onWrong else None, MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)

    session.openWithCallback(checked, IPTVPinWidget, title=_("Enter pin") + " - " + GetHostDisplayTitle(hostName))


def GetHostPinConfigList(hostName):
    settings = _settings(hostName)
    protect, ownPin, action = settings[0], settings[1], settings[3]
    optionList = [getConfigListEntry(_("Pin protection for this host"), protect)]
    if protect.value:
        optionList.append(getConfigListEntry("    " + _("Use own pin instead of the player pin"), ownPin))
        if ownPin.value:
            actionEntry = getConfigListEntry("    " + (_("Change own pin") if _ownPinSet(hostName) else _("Set own pin")), action)
            actionEntry[1].iptv_host_action = HOST_PIN_ACTION
            optionList.append(actionEntry)
    return optionList


def HandleHostPinAction(session, hostName, callback=None):
    # the "Set/Change own pin" row: old pin (when one is set) -> new pin -> confirm
    from Plugins.Extensions.IPTVPlayer.components.iptvpin import IPTVPinWidget
    ownPin, pinCode = _settings(hostName)[1:3]
    titleSuffix = " - " + GetHostDisplayTitle(hostName)
    state = {'newPin': None}

    def finish():
        if callable(callback):
            try:
                callback()
            except Exception:
                printExc()

    def askNew():
        session.openWithCallback(confirmNew, IPTVPinWidget, title=_("Enter new pin") + titleSuffix)

    def confirmNew(pin=None):
        if pin is None:
            finish()
            return
        state['newPin'] = pin
        session.openWithCallback(saveNew, IPTVPinWidget, title=_("Confirm new pin") + titleSuffix)

    def saveNew(pin=None):
        if pin is not None and pin == state['newPin']:
            pinCode.value = pin
            pinCode.save()
            ownPin.value = True
            ownPin.save()
            configfile.save()
            printDBG("HandleHostPinAction own pin of host [%s] changed" % hostName)
            session.open(MessageBox, _("Pin has been changed."), type=MessageBox.TYPE_INFO, timeout=5)
        else:
            session.open(MessageBox, _("Confirmation error."), type=MessageBox.TYPE_INFO, timeout=5)
        finish()

    def checkOld(pin=None):
        if pin is not None and pin == pinCode.value:
            askNew()
        else:
            if pin is not None:
                session.open(MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)
            finish()

    if _ownPinSet(hostName):
        session.openWithCallback(checkOld, IPTVPinWidget, title=_("Enter old pin") + titleSuffix)
    else:
        askNew()
