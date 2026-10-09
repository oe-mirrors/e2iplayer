# -*- coding: utf-8 -*-
#
#  IPTV Tools
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib2_urlopen, urllib2_Request, urllib2_URLError, urllib2_HTTPError, urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import strDecode, ensure_str, ensure_binary
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config
from Tools.Directories import resolveFilename, fileExists, SCOPE_PLUGINS, SCOPE_CONFIG
from enigma import eConsoleAppContainer
from Components.Language import language
# Tools.Notifications (there is no Screens.Notifications); optional, a missing module must not stop the plugin from loading
try:
    from Tools.Notifications import AddPopup
except Exception:
    AddPopup = None
from Screens.MessageBox import MessageBox
from base64 import b64decode, b64encode, urlsafe_b64decode, urlsafe_b64encode
from time import time
from urllib.request import urlopen
import traceback
import re
import sys
import os
import shutil
import stat
import codecs
import io
import datetime
import threading
from functools import cmp_to_key
import socket


def UsePyCurl():
    return config.plugins.iptvplayer.usepycurl.value


def GetIconsHash():
    iconsHashFile = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/hash.txt')
    sts, data = ReadTextFile(iconsHashFile)
    if sts:
        return data.strip()
    else:
        return ''


def SetIconsHash(value):
    iconsHashFile = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/hash.txt')
    return WriteTextFile(iconsHashFile, value)


def GetGraphicsHash():
    graphicsHashFile = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/hash.txt')
    sts, data = ReadTextFile(graphicsHashFile)
    if sts:
        return data.strip()
    else:
        return ''


def SetGraphicsHash(value):
    graphicsHashFile = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/hash.txt')
    return WriteTextFile(graphicsHashFile, value)

###################################################


def DaysInMonth(dt):
    return (datetime.date(dt.year + (dt.month // 12), (dt.month % 12) + 1, 1) - dt).days + dt.day - 1


def NextMonth(dt):
    return (dt.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)


def PrevMonth(dt):
    return (dt.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)


def NextDay(dt):
    return (dt + datetime.timedelta(days=1))


def PrevDay(dt):
    return (dt - datetime.timedelta(days=1))

###################################################


def _b64Pad(t):
    t = ensure_str(t).strip()
    return t + '=' * (-len(t) % 4)


def b64Decode(t, binary=False):
    r = b64decode(_b64Pad(t))
    return r if binary else ensure_str(r)


def b64Encode(b, strip=False):
    r = ensure_str(b64encode(ensure_binary(b)))
    if strip:
        r = r.rstrip('=')
    return r


def b64urlEncode(b, strip=False):
    r = ensure_str(urlsafe_b64encode(ensure_binary(b)))
    if strip:
        r = r.rstrip('=')
    return r


def b64urlDecode(t, binary=False):
    r = urlsafe_b64decode(_b64Pad(t))
    return r if binary else ensure_str(r)


def GetNice(pid=None):
    nice = 0
    if None is pid:
        pid = 'self'
    filePath = '/proc/%s/stat' % pid
    try:
        with open(filePath, 'r') as f:
            data = f.read()
            # field 19 is nice (field 20 is num_threads); comm (field 2) may contain
            # spaces, so count from the closing ')' where field 3 (state) starts
            data = data.rsplit(')', 1)[1].split()[16]
            nice = int(data)
    except Exception:
        printExc()
    return nice


def E2PrioFix(cmd, factor=2):
    if '/duk' not in cmd:  # and config.plugins.iptvplayer.plarform.value in ('mipsel', 'armv7', 'armv5t'):
        return 'nice -n %d %s' % (GetNice() + factor, cmd)
    else:
        return cmd


def GetDefaultLang(full=False):
    if full:
        try:
            defaultLanguage = language.getActiveLanguage()
        except Exception:
            printExc()
            defaultLanguage = 'en_EN'
    else:
        try:
            defaultLanguage = language.getActiveLanguage().split('_')[0]
        except Exception:
            printExc()
            defaultLanguage = 'en'
    return defaultLanguage


def GetPolishSubEncoding(filePath):
    encoding = 'utf-8'
    # Method provided by @areq: http://forum.dvhk.to/showpost.php?p=5367956&postcount=5331
    try:
        # the raw bytes are counted - reading as text (UTF-8 on the box) failed for CP1250/ISO files
        with open(filePath, 'rb') as f:
            sub = bytearray(f.read())
        iso = 0
        for i in (161, 166, 172, 177, 182, 188):
            iso += sub.count(i)
        win = 0
        for i in (140, 143, 156, 159, 165, 185):
            win += sub.count(i)
        utf = 0
        for i in (195, 196, 197):
            utf += sub.count(i)
        if win > utf and win > iso:
            encoding = "CP1250"
        elif utf > iso and utf > win:
            encoding = "utf-8"
        else:
            encoding = "iso-8859-2"
        printDBG("IPTVExtMoviePlayer _getEncoding iso[%d] win[%d ] utf[%d] -> [%s]" % (iso, win, utf, encoding))
    except Exception:
        printExc()
    return encoding


def MapUcharEncoding(encoding):
    ENCODING_MAP = {'X-MAC-CYRILLIC': "MAC-CYRILLIC", "ASCII": "UTF-8"}
    printDBG("MapUcharEncoding in encoding[%s]" % encoding)
    try:
        encoding = ENCODING_MAP.get(encoding.strip().upper(), encoding.strip())
    except Exception:
        printExc()
    printDBG("MapUcharEncoding out encoding[%s]" % encoding)
    return encoding


class eConnectCallbackObj:
    OBJ_ID = 0
    OBJ_NUM = 0

    def __init__(self, obj=None, connectHandler=None):
        eConnectCallbackObj.OBJ_ID += 1
        eConnectCallbackObj.OBJ_NUM += 1
        self.objID = eConnectCallbackObj.OBJ_ID
        printDBG("eConnectCallbackObj.__init__ objID[%d] OBJ_NUM[%d]" % (self.objID, eConnectCallbackObj.OBJ_NUM))
        self.connectHandler = connectHandler
        self.obj = obj

    def __del__(self):
        eConnectCallbackObj.OBJ_NUM -= 1
        printDBG("eConnectCallbackObj.__del__ objID[%d] OBJ_NUM[%d] " % (self.objID, eConnectCallbackObj.OBJ_NUM))
        try:
            if 'connect' not in dir(self.obj):
                if 'get' in dir(self.obj):
                    self.obj.get().remove(self.connectHandler)
                else:
                    self.obj.remove(self.connectHandler)
            else:
                del self.connectHandler
        except Exception:
            printExc()
        self.connectHandler = None
        self.obj = None


def eConnectCallback(obj, callbackFun, withExcept=False):
    try:
        if 'connect' in dir(obj):
            return eConnectCallbackObj(obj, obj.connect(callbackFun))
        else:
            if 'get' in dir(obj):
                obj.get().append(callbackFun)
            else:
                obj.append(callbackFun)
            return eConnectCallbackObj(obj, callbackFun)
    except Exception:
        printExc("eConnectCallback")
    return eConnectCallbackObj()


class iptv_system:
    '''
    Calling os.system is not recommended, it may fail due to lack of memory,
    please use iptv_system instead, this should be used as follow:
    self.handle = iptv_system("cmd", callBackFun)
    there is need to have reference to the obj created by iptv_system,
    without reference to return obj behavior is undefined

    iptv_system must be used only inside MainThread context, please see
    iptv_execute class from asynccall module which is dedicated to be
    used inside other threads
    '''

    def __init__(self, cmd, callBackFun=None):
        printDBG("iptv_system.__init__ cmd [%s]" % cmd)
        self.callBackFun = callBackFun
        self.cmd = cmd

        self.console = eConsoleAppContainer()
        if None is not self.callBackFun:
            self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
            self.console_stdoutAvail_conn = eConnectCallback(self.console.stdoutAvail, self._dataAvail)
            self.outData = ""
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

    def terminate(self, doCallBackFun=False):
        self.kill(doCallBackFun)

    def kill(self, doCallBackFun=False):
        if None is not self.console:
            if None is not self.callBackFun:
                self.console_appClosed_conn = None
                self.console_stdoutAvail_conn = None
            else:
                doCallBackFun = False
            self.console.sendCtrlC()
            self.console = None
            if doCallBackFun:
                self.callBackFun(-1, self.outData)
                self.callBackFun = None

    def _dataAvail(self, data):
        if None is not data:
            self.outData += strDecode(data)

    def _cmdFinished(self, code):
        printDBG("iptv_system._cmdFinished cmd[%s] code[%r]" % (self.cmd, code))
        self.console_appClosed_conn = None
        self.console_stdoutAvail_conn = None
        self.console = None
        self.callBackFun(code, self.outData)
        self.callBackFun = None

    def __del__(self):
        printDBG("iptv_system.__del__ cmd[%s]" % self.cmd)


def IsHttpsCertValidationEnabled():
    return config.plugins.iptvplayer.httpssslcertvalidation.value


def GetAvailableIconSize(checkAll=True):
    iconSizes = [config.plugins.iptvplayer.IconsSize.value]
    if checkAll:
        iconSizes.extend(['135', '120', '100'])
    confirmedIconSize = 0
    for size in iconSizes:
        try:
            file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/marker/marker{0}.png').format(int(size) + 45)
            if fileExists(file):
                confirmedIconSize = int(size)
                break
        except Exception:
            printExc()
    return confirmedIconSize

#############################################################
# returns the directory path where specified resources are
# stored, in the future, it can be changed in the config
#############################################################


def GetLogoDir(file=''):
    return resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/logos/') + file


def GetPyScriptCmd(name):
    cmd = ''
    baseName = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/scripts/') + name
    if fileExists(baseName + '.py'):
        baseName += '.py'
    elif fileExists(baseName + '.pyc'):
        baseName += '.pyc'
    if baseName != '':
        for item in ['python']:
            pyPath = Which(item)
            if '' != pyPath:
                cmd = '%s %s' % (pyPath, baseName)
                break
    return cmd


def GetJSScriptFile(file):
    return resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/jsscripts/') + file


gE2iPlayerTempCookieDir = None


def SetTmpCookieDir():
    global gE2iPlayerTempCookieDir
    gE2iPlayerTempCookieDir = '/tmp/e2iplayer_cookies/'
    mkdirs(gE2iPlayerTempCookieDir)


def ClearTmpCookieDir():
    global gE2iPlayerTempCookieDir
    if gE2iPlayerTempCookieDir is not None:
        try:
            for fileName in os.listdir(gE2iPlayerTempCookieDir):
                rm(os.path.join(gE2iPlayerTempCookieDir, fileName))
        except Exception:
            printExc()

    gE2iPlayerTempCookieDir = None


def TestTmpCookieDir():
    path = GetCookieDir(forceFromConfig=True)
    if not os.path.isdir(path):
        mkdirs(path, True)
    with open(path + ".rw_test", 'w') as f:
        f.write("test")


# paths already warned about (Get*Dir() runs on every request)
gWarnedUnwritableDirs = set()


def _warnIfDirNotCreatable(path, message):
    if os.path.isdir(path) or path in gWarnedUnwritableDirs:
        return
    gWarnedUnwritableDirs.add(path)
    try:
        # lazy import: asynccall imports this module (circular)
        import Plugins.Extensions.IPTVPlayer.components.asynccall as asynccall

        # first argument is the session DelegateToMainThread passes in (unused)
        def showPopup(session=None):
            if AddPopup is None:
                printDBG('Storage: no popup available, warning only logged: ' + (message % path))
                return
            AddPopup(message % path, type=MessageBox.TYPE_ERROR, timeout=10)

        if asynccall.IsMainThread():
            showPopup()
        elif asynccall.gMainFunctionsQueueTab[0] is not None:
            # may run on a worker thread: GUI calls must go through the main thread
            asynccall.DelegateToMainThread(showPopup)()
        # no GUI session (headless web interface): nothing to do
    except Exception:
        printExc()


def _warnIfCacheDirNotCreatable(path):
    _warnIfDirNotCreatable(path, _('Cache folder "%s" could not be created. Some data (cookies, subtitles, ...) may not be saved.'))


def _warnIfConfigDirNotCreatable(path):
    _warnIfDirNotCreatable(path, _('Config folder "%s" could not be created. Some data (host order, search history, favourites, movie player preferences, ...) may not be saved.'))


def GetCookieDir(file='', forceFromConfig=False):
    if gE2iPlayerTempCookieDir is None or forceFromConfig:
        cookieDir = os.path.join(config.plugins.iptvplayer.CacheDir.value, 'cookies/')
    else:
        cookieDir = gE2iPlayerTempCookieDir
    try:
        if not os.path.isdir(cookieDir):
            mkdirs(cookieDir)
            _warnIfCacheDirNotCreatable(cookieDir)
    except Exception:
        printExc()
    return cookieDir + file


###########################
gE2iPlayerTempJSCache = None


def SetTmpJSCacheDir():
    global gE2iPlayerTempJSCache
    gE2iPlayerTempJSCache = '/tmp/e2iplayer_js_cache/'
    mkdirs(gE2iPlayerTempJSCache)


def ClearTmpJSCacheDir():
    global gE2iPlayerTempJSCache
    if gE2iPlayerTempJSCache is not None:
        try:
            for fileName in os.listdir(gE2iPlayerTempJSCache):  # file is native p2 function renamed for clarity
                rm(os.path.join(gE2iPlayerTempJSCache, fileName))
        except Exception:
            printExc()
    gE2iPlayerTempJSCache = None


def TestTmpJSCacheDir():
    path = GetJSCacheDir(forceFromConfig=True)
    if not os.path.isdir(path):
        mkdirs(path, True)
    with open(path + ".rw_test", 'w') as f:
        f.write("test")


def GetJSCacheDir(fileName='', forceFromConfig=False):
    if gE2iPlayerTempJSCache is None or forceFromConfig:
        cookieDir = os.path.join(config.plugins.iptvplayer.CacheDir.value, 'JSCache/')
    else:
        cookieDir = gE2iPlayerTempJSCache
    try:
        if not os.path.isdir(cookieDir):
            mkdirs(cookieDir)
            _warnIfCacheDirNotCreatable(cookieDir)
    except Exception:
        printExc()
    return os.path.join(cookieDir, fileName)
##############################


def GetTmpDir(fileName=''):
    path = config.plugins.iptvplayer.TmpDir.value
    path = path.replace('//', '/')
    mkdirs(path)
    return os.path.join(path, fileName)


# def GetE2iPlayerRootfsDir(fileName=''):
#    return os.path.join('/iptvplayer_rootfs', fileName)


def GetE2iPlayerVKLayoutDir(fileName=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/vk/'), fileName)


def CreateTmpFile(filename, data=''):
    sts = False
    filePath = GetTmpDir(filename)
    try:
        with open(filePath, 'w') as f:
            f.write(data)
            sts = True
    except Exception:
        printExc()
    return sts, filePath


def GetCacheSubDir(dirName, fileName=''):
    path = os.path.join(config.plugins.iptvplayer.CacheDir.value, dirName)
    if not os.path.isdir(path):
        mkdirs(path)
        _warnIfCacheDirNotCreatable(path)
    return os.path.join(path, fileName)


# Guards the one-time migrations (CacheDir -> ConfigDir, /etc/enigma2 -> ConfigDir/hostorder); every critical section re-checks under it.
# No popup while it is held: from a worker thread the popup waits for the main thread, which may be waiting for this lock.
_storageMigrationLock = threading.Lock()

# destinations whose migration failed this session: retried on the next start, not on every call
gFailedStorageMigrations = set()


def _syncDirInto(src, dst):
    # makes dst a copy of src, copying only files that are missing or differ (size/mtime, copy2 keeps the mtime):
    # a copy cut short (box switched off) goes on from where it stopped instead of starting again. Symlinked folders
    # are not followed and only regular files are copied (a FIFO would block the copy for good). Returns the file count.
    count = 0
    srcFiles = set()
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        dstRoot = dst if rel == '.' else os.path.join(dst, rel)
        if not os.path.isdir(dstRoot):
            os.makedirs(dstRoot)
        for name in files:
            srcFile = os.path.join(root, name)
            if not os.path.isfile(srcFile):
                continue
            dstFile = os.path.join(dstRoot, name)
            srcFiles.add(os.path.normpath(dstFile))
            count += 1
            try:
                srcStat, dstStat = os.stat(srcFile), os.stat(dstFile)
                if srcStat.st_size == dstStat.st_size and int(srcStat.st_mtime) == int(dstStat.st_mtime):
                    continue
            except OSError:
                pass
            shutil.copy2(srcFile, dstFile)
    # files deleted from src since an earlier, cut short copy must not come back
    for root, _dirs, files in os.walk(dst):
        for name in files:
            dstFile = os.path.join(root, name)
            if os.path.normpath(dstFile) not in srcFiles:
                os.remove(dstFile)
    return count


def _dirSize(path):
    # bytes the regular files below path take, each rounded up to whole 4 KiB blocks (thousands of tiny watched markers)
    size = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                size += (os.stat(os.path.join(root, name)).st_size // 4096 + 1) * 4096
            except OSError:
                pass
    return size


def _checkFreeSpaceForCopy(src, tmpPath):
    # the copy goes to the flash (/etc/enigma2): never fill it up, enigma2 could not save its settings anymore
    st = os.statvfs(config.plugins.iptvplayer.ConfigDir.value)
    free = st.f_bavail * st.f_frsize
    needed = _dirSize(src) - (_dirSize(tmpPath) if os.path.isdir(tmpPath) else 0)
    if needed + 8 * 1024 * 1024 > free:
        raise IOError('not enough free space in [%s]: %d KiB needed, %d KiB free' % (config.plugins.iptvplayer.ConfigDir.value, needed // 1024, free // 1024))


def _copyDirInBackground(path, oldPath, label):
    # copies oldPath to <path>.migrating, the copy is switched to at the next start (_getMigratedDir). Until then this
    # session keeps using oldPath everywhere: lists, helpers and hosts keep the folder they got for the whole session,
    # switching while the plugin runs would make them write to a deleted folder. A copy cut short (box switched off)
    # is continued at the next start; a failed one is deleted again, it must not keep space on the flash.
    tmpPath = path + '.migrating'
    donePath = tmpPath + '.complete'
    failed = False
    try:
        printDBG('%s: copying [%s] -> [%s] in the background ...' % (label, oldPath, tmpPath))
        mkdirs(config.plugins.iptvplayer.ConfigDir.value)
        _checkFreeSpaceForCopy(oldPath, tmpPath)
        count = _syncDirInto(oldPath, tmpPath)
        with open(donePath, 'w') as f:
            f.write(oldPath)
        printDBG('%s: copied [%s] -> [%s] (%d files), used from the next start on' % (label, oldPath, tmpPath, count))
    except Exception:
        printExc()
        failed = True
        rmtree(tmpPath, ignore_errors=True)
        rm(donePath)
        printDBG('%s: copy FAILED [%s] -> [%s], data stays in the old folder, retried at the next start' % (label, oldPath, tmpPath))
    with _storageMigrationLock:
        del gRunningStorageMigrations[path]
        if failed:
            gFailedStorageMigrations.add(path)
        else:
            gCopiedStorageMigrations[path] = oldPath


def _switchToCopiedDir(path, oldPath, label):
    # under the lock, before anyone got a folder for path this session: takes over what changed in oldPath since the
    # background copy of an earlier session (only those files are copied, quick), renames the copy to path and moves
    # oldPath aside to be deleted in the background. Returns False when it did not work, oldPath is used then.
    tmpPath = path + '.migrating'
    try:
        count = _syncDirInto(oldPath, tmpPath)
        if os.path.isdir(path):
            # holds no file (checked before), the rename needs the name free
            rmtree(path)
        os.rename(tmpPath, path)
    except Exception:
        printExc()
        # copied again in the background at the next start, the copy must not keep space on the flash meanwhile
        rmtree(tmpPath, ignore_errors=True)
        rm(tmpPath + '.complete')
        printDBG('%s: switch FAILED [%s] -> [%s], data stays in the old folder until the next start' % (label, oldPath, path))
        return False
    rm(tmpPath + '.complete')
    printDBG('%s: migrated [%s] -> [%s] (%d files)' % (label, oldPath, path, count))
    # unique name: one left behind by a switched off box is deleted by StartStorageMigrations(), not here under the lock
    retiredPath = '%s.migrated.%d' % (oldPath, int(time() * 1000))
    try:
        os.rename(oldPath, retiredPath)
        _startThread(rmtree, retiredPath, True)
    except Exception:
        printExc()
        rmtree(oldPath, ignore_errors=True)
    return True


def _startThread(target, *args):
    thread = threading.Thread(target=target, args=args, name='E2iStorageMigration')
    thread.daemon = True
    thread.start()


# destinations checked this session (Get*Dir() runs on every request, the check below walks the folders)
gCheckedStorageMigrations = set()

# destination -> old folder: copy running in the background right now / copied this session (switched to at the next
# start); in both cases the old folder is used for the rest of the session
gRunningStorageMigrations = {}
gCopiedStorageMigrations = {}


def _dirHasFiles(path):
    for _root, _dirs, files in os.walk(path):
        if files:
            return True
    return False


def _findDirToMigrate(path, oldPaths):
    # the old folder whose data still has to move to path, None when there is nothing to move. A destination without
    # a single file counts as missing: a start without the old storage (HDD not mounted yet, CacheDir rerouted) created
    # it empty, and from then on it hid the data left behind in the old folder (e.g. all favourites gone after the update)
    if os.path.isdir(path) and _dirHasFiles(path):
        return None
    realPath = os.path.realpath(path)
    for oldPath in oldPaths:
        if os.path.isdir(oldPath) and os.path.realpath(oldPath) != realPath and _dirHasFiles(oldPath):
            return oldPath
    return None


def _readCopiedFrom(donePath):
    # the folder a finished background copy was made from, '' when there is no finished copy
    try:
        with open(donePath) as f:
            return f.read().strip()
    except Exception:
        return ''


def _getMigratedDir(path, oldPaths, label, copy):
    # path, or the old folder while its data is not moved yet. copy: the old folder is on another file system (cache
    # on the HDD -> flash), the copy runs in the background and is switched to at the next start (_copyDirInBackground);
    # copying it in the GUI thread hung the box for minutes. Otherwise a plain rename, done right away.
    if path in gCheckedStorageMigrations and os.path.isdir(path):
        return path
    useOldPath = None
    with _storageMigrationLock:
        useOldPath = gRunningStorageMigrations.get(path) or gCopiedStorageMigrations.get(path)
        if useOldPath is not None:
            return useOldPath
        tmpPath = path + '.migrating'
        donePath = tmpPath + '.complete'
        oldPath = _findDirToMigrate(path, oldPaths)
        if oldPath is None:
            if os.path.isdir(path) and _dirHasFiles(path):
                # left over (box switched off right after a switch, or another copy won), not needed: free the flash
                if os.path.exists(tmpPath):
                    rmtree(tmpPath, ignore_errors=True)
                rm(donePath)
            elif os.path.isdir(tmpPath) and _readCopiedFrom(donePath):
                srcPath = _readCopiedFrom(donePath)
                if os.path.isdir(srcPath):
                    # still there but emptied since ("Delete favourites", ...): the copy must not bring it back
                    rmtree(tmpPath, ignore_errors=True)
                    rm(donePath)
                elif os.path.isdir(os.path.dirname(srcPath)):
                    # gone with the cache ("Delete all cache files", another image sharing the HDD moved it already):
                    # the complete copy of it is used. Not while the storage it was on is missing (HDD not mounted
                    # yet), the copy would then hide what was changed there after it was made
                    try:
                        if os.path.isdir(path):
                            rmtree(path)
                        os.rename(tmpPath, path)
                        rm(donePath)
                        printDBG('%s: old folder gone, its copy [%s] is used' % (label, tmpPath))
                    except Exception:
                        printExc()
            if not os.path.isdir(path):
                mkdirs(path)
            if os.path.isdir(path):
                gCheckedStorageMigrations.add(path)
        elif path in gFailedStorageMigrations:
            useOldPath = oldPath
        elif not copy:
            try:
                mkdirs(config.plugins.iptvplayer.ConfigDir.value)
                if os.path.isdir(path):
                    # holds no file (checked above), the rename needs the name free
                    rmtree(path)
                os.rename(oldPath, path)
                printDBG('%s: migrated [%s] -> [%s]' % (label, oldPath, path))
                gCheckedStorageMigrations.add(path)
            except Exception:
                printExc()
                gFailedStorageMigrations.add(path)
                printDBG('%s: migration FAILED [%s] -> [%s], data stays in the old folder until the next start' % (label, oldPath, path))
                useOldPath = oldPath
        elif os.path.isfile(donePath) and os.path.isdir(tmpPath):
            if _switchToCopiedDir(path, oldPath, label):
                gCheckedStorageMigrations.add(path)
            else:
                gFailedStorageMigrations.add(path)
                useOldPath = oldPath
        else:
            rm(donePath)
            gRunningStorageMigrations[path] = oldPath
            _startThread(_copyDirInBackground, path, oldPath, label)
            useOldPath = oldPath
    if useOldPath is not None:
        return useOldPath
    if not os.path.isdir(path):
        _warnIfConfigDirNotCreatable(path)
    return path


def StartStorageMigrations():
    # at plugin start, in a worker thread (looking into the old folders may wait for the HDD to spin up): switches to
    # the copies made in the last session before the first list asks for a folder, starts the copies still needed,
    # deletes old folders a switched off box left behind
    def _migrate():
        for getDir in (GetHostOrderDir, GetSearchHistoryDir, GetMoviePlayerPerHostDir, GetFavouritesDir, GetWatchedDir):
            try:
                getDir()
            except Exception:
                printExc()
        for cacheDir in set(os.path.dirname(oldPath) for oldPath in _configSubDirOldPaths('')):
            try:
                names = os.listdir(cacheDir) if os.path.isdir(cacheDir) else []
            except Exception:
                names = []
            for name in names:
                if name.split('.migrated.')[0] in ('hostorder', 'SearchHistory', 'MoviePlayer', 'IPTVFavourites', 'hostxxx') and \
                        '.migrated.' in name and os.path.isdir(os.path.join(cacheDir, name)):
                    rmtree(os.path.join(cacheDir, name), ignore_errors=True)
    _startThread(_migrate)


def _configSubDirOldPaths(dirName):
    # besides the current CacheDir also the one it was rerouted from and the default one: a CacheDir rerouted
    # before CacheDirWanted existed lost its old path
    return [os.path.join(cacheDir, dirName) for cacheDir in (config.plugins.iptvplayer.CacheDir.value,
                                                             config.plugins.iptvplayer.CacheDirWanted.value,
                                                             config.plugins.iptvplayer.SciezkaCache.default) if cacheDir]


def GetConfigSubDir(dirName, fileName=''):
    # used to live under CacheDir: move once, so "Delete all cache files" cannot wipe it
    path = os.path.join(config.plugins.iptvplayer.ConfigDir.value, dirName)
    return os.path.join(_getMigratedDir(path, _configSubDirOldPaths(dirName), 'GetConfigSubDir', True), fileName)


def GetSearchHistoryDir(fileName=''):
    return GetConfigSubDir('SearchHistory', fileName)


def GetFavouritesDir(fileName=''):
    return GetConfigSubDir('IPTVFavourites', fileName)


def GetWatchedDir(fileName=''):
    # watched/started markers (<host>/.<hash>.iptvhash) live next to IPTVFavourites; carried over from
    # <CacheDir>/IPTVFavourites/IPTVWatched and <ConfigDir>/IPTVFavourites/IPTVWatched (a plain rename)
    path = os.path.join(config.plugins.iptvplayer.ConfigDir.value, 'IPTVWatched')
    if path not in gCheckedStorageMigrations or not os.path.isdir(path):
        # outside the lock: takes and releases it itself (a plain Lock is not reentrant)
        favDir = GetFavouritesDir('')
        oldPath = os.path.join(favDir, 'IPTVWatched')
        if not IsSameDir(favDir, os.path.join(config.plugins.iptvplayer.ConfigDir.value, 'IPTVFavourites')):
            # the favourites are still used from the old folder (copied in the background, or moving them failed):
            # the markers stay there with them and are carried over together (a rename to the flash would fail anyway)
            return os.path.join(oldPath, fileName)
        path = _getMigratedDir(path, [oldPath], 'GetWatchedDir', False)
    return os.path.join(path, fileName)


def GetDownloadedDir(fileName=''):
    # "downloaded" markers (<host>/.<hash>.iptvdl) of the items downloaded from a host list - user data, so in the config folder
    return os.path.join(config.plugins.iptvplayer.ConfigDir.value, 'IPTVDownloaded', fileName)


def GetSubtitlesDir(fileName=''):
    return GetCacheSubDir('Subtitles', fileName)


def GetMovieMetaDataDir(fileName=''):
    return GetCacheSubDir('MovieMetaData', fileName)


def GetMoviePlayerPerHostDir(fileName=''):
    return GetConfigSubDir('MoviePlayer', fileName)


def GetHostOrderDir(fileName=''):
    return GetConfigSubDir('hostorder', fileName)


def GetMigratedHostOrderFile(fileName):
    # host group/order files used to sit directly in /etc/enigma2/. Moved once via temp file + rename;
    # on failure the old file keeps being used (the new path would show an empty list).
    # GetHostOrderDir() takes the lock itself and has released it by now.
    newPath = GetHostOrderDir(fileName)
    if not os.path.exists(newPath):
        oldPath = GetConfigDir(fileName)
        if os.path.exists(oldPath) and os.path.realpath(oldPath) != os.path.realpath(newPath):
            with _storageMigrationLock:
                if not os.path.exists(newPath) and newPath not in gFailedStorageMigrations:
                    tmpPath = newPath + '.tmp'
                    try:
                        with open(oldPath, 'rb') as src:
                            data = src.read()
                        with open(tmpPath, 'wb') as dst:
                            dst.write(data)
                        os.rename(tmpPath, newPath)
                        os.remove(oldPath)
                        printDBG('GetMigratedHostOrderFile: migrated [%s] -> [%s]' % (oldPath, newPath))
                    except Exception:
                        printExc()
                        gFailedStorageMigrations.add(newPath)
                        printDBG('GetMigratedHostOrderFile: migration FAILED [%s] -> [%s], keeping the old file in use' % (oldPath, newPath))
                        try:
                            os.remove(tmpPath)
                        except Exception:
                            pass
                if not os.path.exists(newPath) and os.path.exists(oldPath):
                    return oldPath
    return newPath


def GetIPTVDMImgDir(fileName=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/'), fileName)


def GetIconDir(fileName=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/'), fileName)


def GetPluginDir(fileName=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/'), fileName)


def GetExtensionsDir(fileName=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/'), fileName)


def GetSkinsDir(path=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/skins/'), path)


def GetPlayerSkinDir(path=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/playerskins/'), path)


def GetConfigDir(path=''):
    return resolveFilename(SCOPE_CONFIG, path)


def IsExecutable(fpath):
    try:
        if '' != Which(fpath):
            return True
    except Exception:
        printExc()
    return False


def GetGstPlayerPath():
    # gstplayer2 (oe-mirrors/iptvplayer-bin-components, also used by
    # ServiceApp) has all of mx3L's fixes but a getopt command line;
    # /usr/bin/gstplayer is the 2017 build with positional arguments
    if IsExecutable('/usr/bin/gstplayer2'):
        return '/usr/bin/gstplayer2'
    return '/usr/bin/gstplayer'


# gstplayer opens a file that is still downloading via ifd:// when it gets a
# download timeout > 0; that URI handler comes from this GStreamer plugin
GST_IFDSRC_PATHS = ['/usr/lib/gstreamer-1.0/libgstifdsrc.so', '/usr/lib64/gstreamer-1.0/libgstifdsrc.so']
# GStreamer >= 1.14 finds a plugin only by gst_plugin_<file name>_get_desc
# (gst_plugin_desc is static now); gst-ifdsrc builds declared as "plugin"
# export gst_plugin_plugin_get_desc and get blacklisted
GST_IFDSRC_SYMBOLS = (b'gst_plugin_ifdsrc_get_desc', b'gst_plugin_desc\x00')
gstIfdSrcCache = (None, None)


def GetGstIfdSrc():
    # (path, usable), path is '' when the plugin is not installed; the result
    # is kept until the library is installed, removed or replaced
    global gstIfdSrcCache
    key, state = None, ('', False)
    for path in GST_IFDSRC_PATHS:
        try:
            st = os.stat(path)
        except Exception:
            continue
        key = (path, st.st_mtime, st.st_size)
        break
    if key == gstIfdSrcCache[0] and gstIfdSrcCache[1] is not None:
        return gstIfdSrcCache[1]
    if key:
        try:
            with open(key[0], 'rb') as f:
                data = f.read()
            state = (key[0], any(symbol in data for symbol in GST_IFDSRC_SYMBOLS))
        except Exception:
            state = (key[0], False)
        printDBG("gstplayer: %s usable[%s]" % state)
    gstIfdSrcCache = (key, state)
    return state


def Which(program):
    try:
        def is_exe(fpath):
            return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            # pathTab = ['/iptvplayer_rootfs/bin', '/iptvplayer_rootfs/usr/bin', '/iptvplayer_rootfs/sbin', '/iptvplayer_rootfs/usr/sbin']
            pathTab = []
            pathTab.extend(os.environ["PATH"].split(os.pathsep))
            for path in pathTab:
                path = path.strip('"')
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file
    except Exception:
        printExc()
    return ''
#############################################################
# class used to auto-select one link when video has several
# links with different qualities
#############################################################


class CSelOneLink():

    def __init__(self, listOfLinks, getQualiyFun, maxRes):
        self.listOfLinks = listOfLinks
        self.getQualiyFun = getQualiyFun
        self.maxRes = maxRes

    def _cmpLinks(self, item1, item2):
        val1 = self.getQualiyFun(item1)
        val2 = self.getQualiyFun(item2)

        if val1 is None or val2 is None:
            printDBG('iptvtools.CSelOneLink()_cmpLinks <host>__getLinkQuality() returned None value(s) which is an error(val1=%s, val2=%s)\n\t CORRECT <host>!!!' % (str(val1), str(val2)))
            ret = 0
        elif val1 < val2:
            ret = -1
        elif val1 > val2:
            ret = 1
        else:
            ret = 0
        return ret

    def _cmpLinksBest(self, item1, item2):
        return -1 * self._cmpLinks(item1, item2)

    def getBestSortedList(self):
        printDBG('getBestSortedList')
        sortList = self.listOfLinks[::-1]
        sortList.sort(key=cmp_to_key(self._cmpLinksBest))
        retList = []
        tmpList = []
        for item in sortList:
            linkRes = self.getQualiyFun(item)
            if linkRes <= self.maxRes:
                retList.append(item)
            else:
                tmpList.insert(0, item)
        retList.extend(tmpList)
        return retList

    def getSortedLinks(self, defaultFirst=True):
        printDBG('getSortedLinks defaultFirst[%r]' % defaultFirst)
        sortList = self.listOfLinks[::-1]
        sortList.sort(key=cmp_to_key(self._cmpLinks))
        if len(self.listOfLinks) < 2 or None is self.maxRes:
            return self.listOfLinks

        if defaultFirst:
            # split links to two groups
            # first gorup will meet maxRes
            # second group not
            group1 = []
            group2 = []
            for idx in range(len(self.listOfLinks)):
                if self.getQualiyFun(self.listOfLinks[idx]) <= self.maxRes:
                    group1.append(self.listOfLinks[idx])
                else:
                    group2.append(self.listOfLinks[idx])
            group1.sort(key=cmp_to_key(self._cmpLinks))
            group2.sort(key=cmp_to_key(self._cmpLinks))
            group1.reverse()
            group1.extend(group2)
            return group1

        defIdx = -1
        for idx in range(len(sortList)):
            linkRes = self.getQualiyFun(sortList[idx])
            printDBG("=============== getOneLink [%r] res[%r] maxRes[%r]" % (sortList[idx], linkRes, self.maxRes))
            if linkRes <= self.maxRes:
                defIdx = idx
                printDBG('getOneLink use format %d/%d' % (linkRes, self.maxRes))

        if defaultFirst and -1 < defIdx:
            item = sortList[defIdx]
            del sortList[defIdx]
            sortList.insert(0, item)
        return sortList

    def getOneLink(self):
        printDBG('getOneLink start')
        tab = self.getSortedLinks()
        if len(tab) == 0:
            return tab
        return [tab[0]]
# end CSelOneLink

#############################################################
# prints debugs on screen or to the file
#############################################################
# debugs


def getDebugMode():
    DBG = ''
    try:
        from Components.config import config
        DBG = config.plugins.iptvplayer.debugprint.value
    except Exception:
        file = open(resolveFilename(SCOPE_CONFIG, "settings"))
        for line in file:
            if line.startswith('config.plugins.iptvplayer.debugprint='):
                DBG = line.split("=")[1].strip()
                break
    return DBG


# the three file paths the debug-log config UI offers
DEBUG_LOG_PATHS = ('/hdd/iptv.dbg', '/tmp/iptv.dbg', '/home/root/logs/iptv.dbg')


def GetDebugLogPath():
    """The resolved debug file path, or '' when logging is off / to console."""
    DBG = getDebugMode()
    if not DBG or DBG == 'console':
        return ''
    return '/hdd/iptv.dbg' if DBG == 'debugfile' else DBG


def _debugCfg(name, default):
    try:
        return getattr(config.plugins.iptvplayer, name).value
    except Exception:
        return default


def KeepDebugArtifact(configName):
    """True when debug logging is enabled AND the given per-artifact
    'keep debug files' toggle (config.plugins.iptvplayer.<configName>) is on.
    Used by call sites that leave a helper file (e.g. an .iptv.cmd, a
    temporary JS script) on disk for troubleshooting instead of deleting it
    right away."""
    if getDebugMode() == '':
        return False
    return _debugCfg(configName, True)


def _rotatedGlob(path):
    base, ext = os.path.splitext(path)
    try:
        import glob
        return sorted(glob.glob(base + '-*' + ext))
    except Exception:
        return []


def ClearDebugLogsAtStart():
    """Called from plugin start. Deletes the active debug file plus every
    preset path plus their rotated <base>-<date><ext> siblings - unless the
    user turned 'clear at start' off (default on = the old behaviour).
    Returns True when it actually removed something."""
    if not _debugCfg('debug_clear_on_start', True):
        return False
    targets = set(DEBUG_LOG_PATHS)
    cur = GetDebugLogPath()
    if cur:
        targets.add(cur)
    removed = False
    for path in targets:
        for f in [path] + _rotatedGlob(path):
            try:
                if os.path.exists(f):
                    os.remove(f)
                    removed = True
            except Exception:
                pass
    return removed


_g_dbg_calls = 0


def _enforceDebugLogLimit(path):
    try:
        maxMB = int(_debugCfg('debug_max_size', '0') or '0')
    except Exception:
        maxMB = 0
    if maxMB <= 0:
        return
    try:
        if os.path.getsize(path) < maxMB * 1024 * 1024:
            return
    except Exception:
        return
    try:
        if _debugCfg('debug_on_limit', 'truncate') == 'rotate':
            base, ext = os.path.splitext(path)
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            os.rename(path, '%s-%s%s' % (base, stamp, ext))
            try:
                keep = int(_debugCfg('debug_rotate_keep', '3') or '3')
            except Exception:
                keep = 3
            old = _rotatedGlob(path)
            for f in (old[:-keep] if keep > 0 else old):
                try:
                    os.remove(f)
                except Exception:
                    pass
        else:
            with open(path, 'w'):
                pass
    except Exception:
        pass


# Credentials a host knows (an IPTV account's password, a portal's MAC) that also end up in lines the host does
# not write itself - stream urls like /live/<user>/<password>/1.m3u8 in the downloader / player lines. A host
# registers them once, printDBG then masks them in every line (only as a whole word, so a short password does
# not mask parts of other words). Users post their debug log.
_g_log_secrets = set()
_g_log_secrets_re = [None]


def registerLogSecret(*values):
    changed = False
    for value in values:
        try:
            value = ensure_str(value).strip() if value else ''
        except Exception:
            continue
        if len(value) < 3 or value in _g_log_secrets:
            continue
        for form in set([value, value.lower(), value.upper(), urllib_quote(value, safe='')]):
            _g_log_secrets.add(form)
        changed = True
    if changed:
        # longest first, so "user%40x" is masked before "user"
        alternatives = '|'.join(re.escape(s) for s in sorted(_g_log_secrets, key=len, reverse=True))
        _g_log_secrets_re[0] = re.compile(r'(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])' % alternatives)


def maskLogSecrets(text):
    regex = _g_log_secrets_re[0]
    if regex is None:
        return text
    try:
        return regex.sub('***', text if isinstance(text, str) else str(text))
    except Exception:
        return text


def printDBG(DBGtxt, writeMode='a'):
    global _g_dbg_calls
    DBG = getDebugMode()
    if DBG == '':
        return
    DBGtxt = maskLogSecrets(DBGtxt)
    if DBG == 'console':
        print(DBGtxt)
    else:
        if DBG == 'debugfile':
            DBGfile = '/hdd/iptv.dbg'  # backward compatibility
        else:
            DBGfile = DBG
        _g_dbg_calls += 1
        if _g_dbg_calls % 250 == 0:
            _enforceDebugLogLimit(DBGfile)
        try:
            with open(DBGfile, writeMode) as f:
                f.write(str(DBGtxt) + '\n')
        except Exception:
            print("======================EXC printDBG======================")
            print("printDBG(I): %s" % traceback.format_exc())
            print("========================================================")
            try:
                msg = '%s' % traceback.format_exc()
                with open(DBGfile, writeMode) as f:
                    f.write(str(DBGtxt) + '\n')
            except Exception:
                print("======================EXC printDBG======================")
                print("printDBG(II): %s" % traceback.format_exc())
                print("========================================================")


#####################################################
# get host list based on files in /hosts folder
#####################################################
g_cacheHostsFromList = None
g_cacheHostsFromFolder = None
g_cachePluginFolder = None


def __isHostNameValid(hostName):
    BLOCKED_MARKER = '_blocked_'
    if len(hostName) > 4 and BLOCKED_MARKER not in hostName and hostName.startswith("host"):
        return True
    return False


def getHostsPath(fileName=''):
    return os.path.join(resolveFilename(SCOPE_PLUGINS), 'Extensions/IPTVPlayer/hosts/', fileName)


def GetHostsFromList(useCache=True):
    global g_cacheHostsFromList
    if useCache and g_cacheHostsFromList is not None and len(g_cacheHostsFromList) > 0:
        printDBG('iptvtools.GetHostsFromList returns cached list (%s)' % str(g_cacheHostsFromList))
        return list(g_cacheHostsFromList)

    lhosts = []

    try:
        unique_names = set()
        for f in os.listdir(getHostsPath()):
            if f.endswith((".py", ".pyc")):
                name = os.path.splitext(f)[0]
                if len(name) > 4 and "_blocked_" not in name and name.startswith("host"):
                    unique_names.add(name[4:])

        for filename in unique_names:
            printDBG('getHostsList add host from list hostName: "%s"' % filename)
            lhosts.append(filename)

    except OSError:
        printExc()

    g_cacheHostsFromList = lhosts
    printDBG(str(g_cacheHostsFromList))
    return lhosts


def GetHostsFromFolder(useCache=True):
    global g_cacheHostsFromFolder
    if useCache and g_cacheHostsFromFolder is not None and len(g_cacheHostsFromFolder) > 0:
        printDBG('iptvtools.GetHostsFromFolder returns cached list (%s)' % str(g_cacheHostsFromFolder))
        return g_cacheHostsFromFolder

    lhosts = []
    try:
        fileList = os.listdir(getHostsPath())
        printDBG('\t len(fileList)=%s' % len(fileList))
        for wholeFileName in fileList:
            # separate file name and file extension
            fileName, fileExt = os.path.splitext(wholeFileName)
            nameLen = len(fileName)
            if fileExt in ['.pyo', '.pyc', '.py'] and nameLen > 4 and __isHostNameValid(fileName):
                if fileName[4:] not in lhosts:
                    lhosts.append(fileName[4:])
                    printDBG('getHostsList add host with fileName: "%s"' % fileName[4:])
        printDBG('iptvtools.getHostsList end')
        lhosts.sort()
    except Exception:
        printDBG('iptvtools.GetHostsList EXCEPTION')

    g_cacheHostsFromFolder = lhosts
    return lhosts


def GetHostsList(fromList=True, fromHostFolder=True, useCache=True):
    lhosts = []
    if fromHostFolder:
        printDBG('iptvtools.getHostsList(fromHostFolder)')
        lhosts = GetHostsFromFolder(useCache)

    # when new option to remove not enabled host is enabled
    # on list should be also host which are not normally in
    # the folder, so we will read first predefined list
    if fromList:
        printDBG('iptvtools.getHostsList(fromList)')
        tmp = GetHostsFromList(useCache)
        for host in tmp:
            if host not in lhosts:
                lhosts.append(host)

    return lhosts


def GetEnabledHostsList():
    hostsList = GetHostsList(fromList=True, fromHostFolder=True)
    enabledHostsList = []
    for hostName in hostsList:
        if IsHostEnabled(hostName):
            enabledHostsList.append(hostName)
    return enabledHostsList


def SortHostsList(hostsList):
    hostsList = list(hostsList)
    hostsOrderList = GetHostsOrderList()
    sortedList = []
    for item in hostsOrderList:
        if item in hostsList:
            sortedList.append(item)
            hostsList.remove(item)
    sortedList.extend(hostsList)
    return sortedList


def SaveHostsOrderList(list, fileName="iptvplayerhostsorder"):
    printDBG('SaveHostsOrderList begin')
    fname = GetMigratedHostOrderFile(fileName)
    try:
        f = open(fname, 'w')
        for item in list:
            f.write(item + '\n')
        f.close()
    except Exception:
        printExc()


def GetHostsOrderList(fileName="iptvplayerhostsorder"):
    printDBG('GetHostsOrderList begin')
    fname = GetMigratedHostOrderFile(fileName)
    list = []
    try:
        if fileExists(fname):
            with open(fname, 'r') as f:
                content = f.readlines()
            for item in content:
                item = item.strip()
                if len(item):
                    list.append(item)
        else:
            printDBG('GetHostsOrderList file[%s] not exists' % fname)
    except Exception:
        printExc()
    return list


def GetSkinsList():
    printDBG('getSkinsList begin')
    skins = []
    SKINS_PATH = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/skins/')
    fileList = os.listdir(SKINS_PATH)
    for filename in fileList:
        skins.append((filename, filename))
    skins.sort()
    skins.insert(0, ("", _("Default")))
    printDBG('getSkinsList end')
    return skins


def IsHostEnabled(hostName):
    hostEnabled = False
    try:
        if getattr(config.plugins.iptvplayer, 'host' + hostName).value:
            hostEnabled = True
    except Exception:
        hostEnabled = False
    return hostEnabled


# host titles for the lists, read from the host file instead of importing it:
# almost every host has "def gettytul(): return '<fixed text>'" (or _('<text>')),
# so showing a group no longer loads all its hosts - only the one opened
_HOST_TITLE_DEF_RE = re.compile(r'^def\s+gettytul\s*\(\s*\)\s*:\s*(?:#.*)?$')
# (the lines are rstrip()ed before they are matched)
_HOST_TITLE_RETURN_RE = re.compile(r'''^\s+return\s+(_\(\s*)?([rRuU]?(?:'[^'\\]*(?:\\.[^'\\]*)*'|"[^"\\]*(?:\\.[^"\\]*)*"))\s*(\)\s*)?(?:#.*)?$''')
_HOST_TITLE_DOC_RE = re.compile(r'''^\s+[rRuU]?("""|\'\'\'|"|').*\1$''')
_HOST_TITLE_CACHE = {}


def _readHostTitleFromFile(path):
    # -> the fixed title of the host file's gettytul(), or None when it is not
    # a single "return <string>" (then the caller imports the host as before)
    from ast import literal_eval
    with io.open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if _HOST_TITLE_DEF_RE.match(line.rstrip()):
                break
        else:
            return None
        title = None
        docSkipped = False
        for line in f:
            line = line.rstrip()
            if line.strip() == '' or line.lstrip().startswith('#'):
                continue
            if title is None:
                if not docSkipped and not line.lstrip().startswith('return') and _HOST_TITLE_DOC_RE.match(line):
                    # one-line docstring
                    docSkipped = True
                    continue
                match = _HOST_TITLE_RETURN_RE.match(line)
                if not match or bool(match.group(1)) != bool(match.group(3)):
                    return None
                title = literal_eval(match.group(2))
                if not isinstance(title, str):
                    title = ensure_str(title)
                if match.group(1):
                    title = _(title)
                continue
            # anything indented after the return means more body -> not a fixed title
            return title if not line[0].isspace() else None
        return title


def GetHostTitle(hostName):
    # gettytul() of a host without loading the host; None when the host is
    # broken (only noticed if its title needs the import). Installs with
    # only .pyc/.pyo files have nothing to read -> import as before.
    path = getHostsPath('host%s.py' % hostName)
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except Exception:
        key = None
    cached = _HOST_TITLE_CACHE.get(hostName)
    if cached and cached[0] == key:
        return cached[1]
    title = None
    if key is not None:
        try:
            title = _readHostTitleFromFile(path)
        except Exception:
            printExc()
    if title is None:
        try:
            module = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], 0)
            title = module.gettytul()
        except Exception:
            printExc('get host name exception for host "%s"' % hostName)
            return None
    _HOST_TITLE_CACHE[hostName] = (key, title)
    return title

##############################################################
# check if we have enough free space
# if required == None return free space instead of comparing
# default unit = MB
##############################################################


def FreeSpace(katalog, requiredSpace, unitDiv=1024 * 1024):
    try:
        s = os.statvfs(katalog)
        freeSpace = s.f_bfree * s.f_frsize  # all free space
        if 512 > (freeSpace / (1024 * 1024)):
            freeSpace = s.f_bavail * s.f_frsize
        freeSpace = freeSpace / unitDiv
    except Exception:
        printExc()
        freeSpace = -1
    printDBG("FreeSpace freeSpace[%s] requiredSpace[%s] unitDiv[%s]" % (freeSpace, requiredSpace, unitDiv))
    if None is requiredSpace:
        return freeSpace
    else:
        if freeSpace >= requiredSpace:
            return True
        else:
            return False


def IsValidFileName(name, NAME_MAX=255):
    prohibited_characters = ['/', "\000", '\\', ':', '*', '<', '>', '|', '"']
    if isinstance(name, str) and (1 <= len(name) <= NAME_MAX):
        for it in name:
            if it in prohibited_characters:
                return False
        return True
    return False


def RemoveDisallowedFilenameChars(name, replacment='.'):
    prohibited_characters = ['/', "\000", '\\', ':', '*', '<', '>', '|', '"']
    for item in prohibited_characters:
        name = name.replace(item, replacment).replace(replacment + replacment, replacment)
    return name


def touch(fname, times=None):
    try:
        with open(fname, 'a'):
            os.utime(fname, times)
        return True
    except Exception:
        printExc()
        return False


def mkdir(newdir):
    """ Wrapper for the os.mkdir function
        returns status instead of raising exception
    """
    try:
        os.mkdir(newdir)
        sts = True
        msg = _('Folder "%s" has been created.') % newdir
    except Exception:
        sts = False
        msg = _('Folder "%s" can not be created.') % newdir
        printExc()
    return sts, msg


def mkdirs(newdir, raiseException=False):
    """ Create a directory and all parent folders.
        Features:
        - parent directories will be created
        - if directory already exists, then do nothing
        - if there is another filsystem object with the same name, raise an exception
    """
    printDBG('mkdirs: "%s"' % newdir)
    try:
        if os.path.isdir(newdir):
            pass
        elif os.path.isfile(newdir):
            raise OSError("cannot create directory, file already exists: '%s'" % newdir)
        else:
            head, tail = os.path.split(newdir)
            if head and not os.path.isdir(head) and not os.path.ismount(head) and not os.path.islink(head):
                mkdirs(head)
            if tail:
                os.mkdir(newdir)
        return True
    except Exception as e:
        printDBG('Exception mkdirs["%s"]' % e)
        if raiseException:
            raise e
    return False


def IsSameDir(pathA, pathB):
    # "/x/cache" vs "/x/cache/" or a symlinked spelling must compare equal
    try:
        return os.path.realpath(pathA) == os.path.realpath(pathB)
    except Exception:
        return pathA == pathB


def IsSameOrSubDir(path, parent):
    # path is parent itself or lies somewhere below it (resolved, so symlinked spellings count too)
    try:
        path = os.path.join(os.path.realpath(path), '')
        parent = os.path.join(os.path.realpath(parent), '')
    except Exception:
        return False
    return path.startswith(parent)


_RAM_FS_TYPES = ('tmpfs', 'ramfs', 'devtmpfs')


def _GetFsTypeFromMounts(resolvedPath, mountsText):
    # fs type of the longest matching mount point; for equal mount points the later entry wins
    bestMountPoint = ''
    fsType = ''
    for line in mountsText.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        mountPoint = parts[1].replace('\\040', ' ')  # /proc/mounts escapes blanks
        if resolvedPath == mountPoint or resolvedPath.startswith(mountPoint.rstrip('/') + '/'):
            if len(mountPoint) >= len(bestMountPoint):
                bestMountPoint = mountPoint
                fsType = parts[2]
    return fsType


def _IsDiskBlockDevice(dev):
    # the block device behind a device number is a disk (sda1, nvme0n1p1: HDD, SSD, USB stick), not the box's
    # flash (mmcblk*, mtd*; ubifs has no block device at all)
    try:
        name = os.path.basename(os.path.realpath('/sys/dev/block/%d:%d' % (os.major(dev), os.minor(dev))))
    except Exception:
        return False
    return name.startswith(('sd', 'nvme', 'hd'))


def IsRealStoragePresent(path):
    # nearest existing ancestor on another device than "/" (an empty mount-point folder on flash is not storage)
    check = path.rstrip('/') or '/'
    while not os.path.isdir(check):
        parent = os.path.dirname(check)
        if parent == check:
            break
        check = parent
    try:
        rootDev = os.stat('/').st_dev
        # the device of "/" is the box's flash - unless the image itself runs from a disk (NeoBoot, USB boot)
        if os.stat(check).st_dev == rootDev and not _IsDiskBlockDevice(rootDev):
            return False
    except Exception:
        return False
    # another device is not enough: some images mount a tiny tmpfs on /media (RAM, gone after reboot)
    try:
        with open('/proc/mounts') as f:
            fsType = _GetFsTypeFromMounts(os.path.realpath(check), f.read())
    except Exception:
        fsType = ''  # cannot tell -> keep the device-number verdict
    return fsType not in _RAM_FS_TYPES


def IsPathWritable(path):
    # used once the user has chosen a path: no "separate storage" requirement
    try:
        return os.path.isdir(path) and os.access(path, os.W_OK)
    except Exception:
        return False


def rm(fullname):
    try:
        if os.path.exists(fullname):
            os.remove(fullname)
        return True
    except Exception:
        printExc()
    return False


def rmtree(path, ignore_errors=False, onerror=None):
    """Recursively delete a directory tree.
    If ignore_errors is set, errors are ignored; otherwise, if onerror
    is set, it is called to handle the error with arguments (func,
    path, exc_info) where func is os.listdir, os.remove, or os.rmdir;
    path is the argument to that function that caused it to fail; and
    exc_info is a tuple returned by sys.exc_info(). If ignore_errors
    is false and onerror is None, an exception is raised.
    """
    if ignore_errors:
        def onerror(*args):
            pass
    elif onerror is None:
        def onerror(*args):
            raise
    try:
        if os.path.islink(path):
            # symlinks to directories are forbidden, see bug #1669
            raise OSError("Cannot call rmtree on a symbolic link")
    except OSError:
        onerror(os.path.islink, path)
        # can't continue even if onerror hook returns
        return
    names = []
    try:
        names = os.listdir(path)
    except os.error as err:
        onerror(os.listdir, path)
    for name in names:
        fullname = os.path.join(path, name)
        try:
            mode = os.lstat(fullname).st_mode
        except os.error:
            mode = 0
        if stat.S_ISDIR(mode):
            rmtree(fullname, ignore_errors, onerror)
        else:
            try:
                os.remove(fullname)
            except os.error as err:
                onerror(os.remove, fullname)
    try:
        os.rmdir(path)
    except os.error:
        onerror(os.rmdir, path)


def CleanOldFilesInDir(path, days):
    # days <= 0 = never; empty subdirectories are left
    try:
        days = int(days)
    except Exception:
        days = 0
    if days <= 0:
        return
    cutoff = time() - days * 86400
    try:
        for root, dirs, files in os.walk(path):
            for fileName in files:
                filePath = os.path.join(root, fileName)
                try:
                    if os.path.getmtime(filePath) < cutoff:
                        os.remove(filePath)
                except Exception:
                    printExc()
    except Exception:
        printExc()


def IsPathSafeToWipe(path):
    # backstop for the "delete everything" actions: refuse "/", mount points, system and home dirs.
    # Checked as typed AND resolved: on OE images /tmp is a symlink to /var/volatile/tmp.
    try:
        spellings = (os.path.normpath(path).rstrip('/'), os.path.realpath(path).rstrip('/'))
    except Exception:
        return False
    for spelling in spellings:
        if not spelling:                       # "/"
            return False
        if spelling.count('/') < 2:            # any top-level folder (/tmp, /media, /usr, ...)
            return False
        if spelling in ('/etc/enigma2', '/usr/lib', '/usr/bin', '/usr/share', '/var/tmp', '/var/volatile', '/var/volatile/tmp', '/home/root'):
            return False
        try:
            if os.path.ismount(spelling):
                return False
        except Exception:
            return False
    return True


def RemoveDirContents(path):
    try:
        for name in os.listdir(path):
            fullname = os.path.join(path, name)
            if os.path.isdir(fullname) and not os.path.islink(fullname):
                rmtree(fullname, ignore_errors=True)
            else:
                rm(fullname)
    except Exception:
        printExc()


def GetFileSize(filepath):
    try:
        return os.stat(filepath).st_size
    except Exception:
        return -1


def DownloadFile(url, filePath):
    printDBG('DownloadFile [%s] from [%s]' % (filePath, url))
    try:
        downloadFile = urlopen(url)
        output = open(filePath, 'wb')
        output.write(downloadFile.read())
        output.close()
        try:
            iptv_system('sync')
        except Exception:
            printExc('DownloadFile sync exception')
        return True
    except Exception:
        try:
            if os.path.exists(filePath):
                os.remove(filePath)
            return False
        except Exception:
            printExc()
            return False

########################################################
#                     For icon manager
########################################################


def GetLastDirNameFromPath(path):
    path = os.path.normcase(path)
    if path[-1] == '/':
        path = path[:-1]
    dirName = path.split('/')[-1]
    return dirName


def GetIconDirBaseName():
    # no leading dot: dot folders are hidden in file managers and Samba shares
    return 'iptvplayer_icons_'


def GetLegacyIconDirBaseName():
    return '.iptvplayer_icons_'


def GetIconsDirPrefix(dirName):
    # folders with the old ".iptvplayer_icons_" prefix are handled like new ones
    for prefix in (GetIconDirBaseName(), GetLegacyIconDirBaseName()):
        if dirName.startswith(prefix):
            return prefix
    return None


def CheckIconName(name):
    # check if name is correct
    if 36 == len(name) and '.jpg' == name[-4:]:
        try:
            tmp = int(name[:-4], 16)
            return True
        except Exception:
            pass
    return False


def GetNewIconsDirName():
    return "%s%f" % (GetIconDirBaseName(), float(time()))


def CheckIconsDirName(path):
    dirName = GetLastDirNameFromPath(path)
    baseName = GetIconsDirPrefix(dirName)
    if baseName is not None:
        try:
            test = float(dirName[len(baseName):])
            return True
        except Exception:
            pass
    return False


def GetIconsDirs(basePath):
    iconsDirs = []
    try:
        list = os.listdir(basePath)
        for item in list:
            currPath = os.path.join(basePath, item)
            if os.path.isdir(currPath) and not os.path.islink(currPath) and CheckIconsDirName(item):
                iconsDirs.append(item)
    except Exception:
        printExc()
    return iconsDirs


def GetIconsFilesFromDir(basePath):
    iconsFiles = []
    if CheckIconsDirName(basePath):
        try:
            list = os.listdir(basePath)
            for item in list:
                currPath = os.path.join(basePath, item)
                if os.path.isfile(currPath) and not os.path.islink(currPath) and CheckIconName(item):
                    iconsFiles.append(item)
        except Exception:
            printExc()

    return iconsFiles


def GetCreationIconsDirTime(fullPath):
    try:
        dirName = GetLastDirNameFromPath(fullPath)
        baseName = GetIconsDirPrefix(dirName)
        return float(dirName[len(baseName):])
    except Exception:
        return None


def GetCreateIconsDirDeltaDateInDays(fullPath):
    ret = -1
    createTime = GetCreationIconsDirTime(fullPath)
    if None is not createTime:
        try:
            currTime = datetime.datetime.now()
            modTime = datetime.datetime.fromtimestamp(createTime)
            deltaTime = currTime - modTime
            ret = deltaTime.days
        except Exception:
            printExc()
    return ret


def RemoveIconsDirByPath(path):
    printDBG("RemoveIconsDirByPath[%s]" % path)
    RemoveAllFilesIconsFromPath(path)
    try:
        os.rmdir(path)
    except Exception:
        printExc('RemoveIconsDirByPath dir[%s] is not empty' % path)


def RemoveOldDirsIcons(path, deltaInDays='7'):
    deltaInDays = int(deltaInDays)
    try:
        iconsDirs = GetIconsDirs(path)
        for item in iconsDirs:
            currDir = os.path.join(path, item)
            delta = GetCreateIconsDirDeltaDateInDays(currDir)  # we will check only directory date
            if delta >= 0 and deltaInDays >= 0 and delta >= deltaInDays:
                RemoveIconsDirByPath(currDir)
    except Exception:
        printExc()


def RemoveAllFilesIconsFromPath(path):
    printDBG("RemoveAllFilesIconsFromPath")
    try:
        list = os.listdir(path)
        for item in list:
            filePath = os.path.join(path, item)
            if CheckIconName(item) and os.path.isfile(filePath):
                printDBG('RemoveAllFilesIconsFromPath img: ' + filePath)
                try:
                    os.remove(filePath)
                except Exception:
                    printDBG("ERROR while removing file %s" % filePath)
    except Exception:
        printExc('ERROR: in RemoveAllFilesIconsFromPath')


def RemoveAllDirsIconsFromPath(path, old=False):
    if old:
        RemoveAllFilesIconsFromPath(path)
    else:
        try:
            iconsDirs = GetIconsDirs(path)
            for item in iconsDirs:
                currDir = os.path.join(path, item)
                RemoveIconsDirByPath(currDir)
        except Exception:
            printExc()


def formatBytes(bytes, precision=2):
    import math
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    bytes = max(bytes, 0)
    if bytes:
        pow = math.log(bytes)
    else:
        pow = 0
    pow = math.floor(pow / math.log(1024))
    pow = min(pow, len(units) - 1)
    bytes /= math.pow(1024, pow)
    return ("%s%s" % (str(round(bytes, precision)), units[int(pow)]))


def remove_html_markup(s, replacement=''):
    tag = False
    quote = False
    out = ""
    for c in s:
        if c == '<' and not quote:
            tag = True
        elif c == '>' and not quote:
            tag = False
            out += replacement
        elif (c == '"' or c == "'") and tag:
            quote = not quote
        elif not tag:
            out = out + c
    return re.sub(r'&\w+;', ' ', out)


# per-host toggle for whether reusing a history entry bumps it back to the
# top. Stored as a tiny ".mru" sidecar next to the history file itself, not
# through the Components.config tree, so it stays host-scoped without a
# static per-host config entry. Shared by CSearchHistoryHelper (which knows
# its own PATH_FILE) and SearchHistoryEditor (which only ever gets a plain
# historyFile path) so both sides read/write the exact same file/format.
def getReorderOnReuseEnabled(path):
    try:
        flagFile = path + '.mru'
        if os.path.isfile(flagFile):
            with io.open(flagFile, 'r', encoding='utf-8', errors='ignore', newline='') as f:
                return f.read().strip() != '0'
    except Exception:
        printExc('getReorderOnReuseEnabled EXCEPTION')
    return True


def setReorderOnReuseEnabled(path, enabled):
    try:
        flagFile = path + '.mru'
        with io.open(flagFile, 'w', encoding='utf-8', errors='replace', newline='') as f:
            f.write(u'1' if enabled else u'0')
        return True
    except Exception:
        printExc('setReorderOnReuseEnabled EXCEPTION')
        return False


# T9 numeric-keypad "jump to entry starting with this letter" search, used
# by both the search-history list (iptvplayerwidget.py) and the search
# history editor (searchhistoryeditor.py) to jump within their own list of
# entries. Wraps around the list starting just after currentIdx. getTitle(idx)
# returns the raw title for entry idx; returns -1 if nothing matches.
def findT9JumpIndex(total, currentIdx, letter, getTitle):
    if total <= 0:
        return -1
    if currentIdx is None or currentIdx < 0:
        currentIdx = -1
    letter = letter.lower()
    for offset in range(1, total + 1):
        title = getTitle((currentIdx + offset) % total)
        try:
            title = title.lower()
        except Exception:
            title = str(title).lower()
        if title.startswith(letter):
            return (currentIdx + offset) % total
    return -1


class CSearchHistoryHelper():
    TYPE_SEP = '|--TYPE--|'

    def __init__(self, name, storeTypes=False):
        self.length = None
        printDBG('CSearchHistoryHelper.__init__')
        self.storeTypes = storeTypes
        try:
            printDBG('CSearchHistoryHelper.__init__ name = "%s"' % name)
            self.PATH_FILE = GetSearchHistoryDir(name + ".txt")
        except Exception:
            printExc('CSearchHistoryHelper.__init__ EXCEPTION')

    def doRemove(self):
        printDBG('CSearchHistoryHelper.doRemove file = "%s"' % self.PATH_FILE)
        self.length = 0
        msg = 1, _('Unable to comply. Search History is empty.')
        try:
            if os.path.isfile(self.PATH_FILE):
                os.remove(self.PATH_FILE)
                msg = 0, _('Search History successfully deleted.')
        except Exception:
            pass
        return msg

    def getLength(self):
        if self.length is None:
            self.length = 0
            if os.path.isfile(self.PATH_FILE):
                try:
                    with io.open(self.PATH_FILE, 'r', encoding='utf-8', errors='ignore', newline='') as file:
                        self.length = sum(1 for _line in file)
                except Exception:
                    pass

        if self.length:
            return _("Number of items in search history: %d") % self.length
        else:
            return _("Search History is empty.")

    def getHistoryList(self):
        printDBG('CSearchHistoryHelper.getHistoryList from file = "%s"' % self.PATH_FILE)
        historyList = []

        if os.path.isfile(self.PATH_FILE):
            try:
                file = io.open(self.PATH_FILE, 'r', encoding='utf-8', errors='ignore', newline='')
                for line in file:
                    value = line.replace('\n', '').strip()
                    if len(value) > 0:
                        try:
                            historyList.insert(0, ensure_str(value))
                        except Exception:
                            printExc()
                file.close()
            except Exception:
                printExc()
                return []
        else:
            return []

        orgLen = len(historyList)
        # remove duplicates
        # last 50 searches patterns are stored
        historyList = historyList[:config.plugins.iptvplayer.search_history_size.value]
        uniqHistoryList = []
        for i in historyList:
            if i not in uniqHistoryList:
                uniqHistoryList.append(i)
        historyList = uniqHistoryList

        # strip file if it has to big overhead
        if orgLen - len(historyList) > 50:
            self._saveHistoryList(historyList)

        # now type also can be stored
        #################################
        newList = []
        for histItem in historyList:
            fields = histItem.split(self.TYPE_SEP)
            if 2 == len(fields):
                newList.append({'pattern': fields[0], 'type': fields[1]})
            elif self.storeTypes:
                newList.append({'pattern': fields[0]})

        if len(newList) > 0:
            return newList
        #################################

        return historyList

    def addHistoryItem(self, itemValue, itemType=None):
        printDBG('CSearchHistoryHelper.addHistoryItem to file = "%s"' % self.PATH_FILE)
        try:
            if config.plugins.iptvplayer.search_history_size.value > 0:
                value = itemValue
                if None is not itemType:
                    value = value + self.TYPE_SEP + itemType
                # re-adding an already-present entry should just bump it back
                # to the most recent position instead of piling up duplicate
                # lines (file is oldest-first, one entry per line, same as
                # getHistoryList() reads it)
                lines = []
                if os.path.isfile(self.PATH_FILE):
                    file = io.open(self.PATH_FILE, 'r', encoding='utf-8', errors='ignore', newline='')
                    for line in file:
                        existing = line.replace('\n', '').strip()
                        if len(existing) > 0 and existing != value:
                            lines.append(existing)
                    file.close()
                lines.append(value)
                file = io.open(self.PATH_FILE, 'w', encoding='utf-8', errors='replace', newline='')
                for line in lines:
                    file.write(line + '\n')
                file.close()
                printDBG('Added pattern: "%s"' % itemValue)
                self.length = len(lines)
        except Exception:
            printExc('CSearchHistoryHelper.addHistoryItem EXCEPTION')

    # per-host toggle: reusing an entry from the history list normally bumps
    # it back to the top (see addHistoryItem above). Some hosts benefit more
    # from a stable, alphabetically-jumpable list (T9 jump in the search
    # history), so this can be switched off per host from SearchHistoryEditor.
    # Stored as a tiny sidecar next to the history file itself, not through
    # the Components.config tree, so it stays host-scoped without needing a
    # static per-host config entry declared anywhere.
    def isReorderOnReuseEnabled(self):
        return getReorderOnReuseEnabled(self.PATH_FILE)

    def _saveHistoryList(self, list):
        printDBG('CSearchHistoryHelper._saveHistoryList to file = "%s"' % self.PATH_FILE)
        try:
            l = len(list)
            with open(self.PATH_FILE, 'w', encoding="UTF-8") as fd:
                for i in range(l):
                    fd.write(list[l - 1 - i] + '\n')
            self.length = l
        except Exception:
            printExc('CSearchHistoryHelper._saveHistoryList EXCEPTION')

    @staticmethod
    def saveLastPattern(pattern):
        filePath = GetSearchHistoryDir("pattern")
        return WriteTextFile(filePath, pattern.replace('\n', '').replace('\r', ''))

    @staticmethod
    def loadLastPattern():
        filePath = GetSearchHistoryDir("pattern")
        if os.path.isdir(filePath):
            try:
                os.rmdir(filePath)
            except Exception:
                printExc('CSearchHistoryHelper.loadLastPattern EXCEPTION')
        return ReadTextFile(filePath)
# end CSearchHistoryHelper


def ReadTextFile(filePath, encode='utf-8', errors='ignore'):
    sts, ret = False, ''
    if os.path.isfile(filePath):
        try:
            file = io.open(filePath, 'r', encoding=encode, errors=errors, newline='')
            ret = file.read().encode(encode, errors)
            file.close()
            if ret.startswith(codecs.BOM_UTF8):
                ret = ret[3:]
            sts = True
            ret = strDecode(ret, errors)
        except Exception:
            if 'SearchHistory/' in filePath:
                printExc('WARNING')
            else:
                printExc()

    return sts, ret


def WriteTextFile(filePath, text, encode='utf-8', errors='ignore'):
    sts = False
    try:
        toSave = text  # if type('') == type(text) else text.decode('utf-8', errors)
        file = io.open(filePath, 'w', encoding=encode, errors=errors, newline='')
        file.write(toSave)
        file.close()
        sts = True
    except Exception:
        printExc()
    return sts


class CFakeMoviePlayerOption():
    def __init__(self, value, text):
        self.value = value
        self.text = text

    def getText(self):
        return self.text


class CMoviePlayerPerHost():
    def __init__(self, hostName):
        self.filePath = GetMoviePlayerPerHostDir(hostName + '.json')
        self.activePlayer = {}  # {buffering:True/False, 'player':''}
        self.load()

    def __del__(self):
        self.save()

    def load(self):
        from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
        sts, ret = False, ''
        try:
            if not os.path.isfile(self.filePath):
                sts = True
            else:
                file = io.open(self.filePath, 'r', encoding='utf-8', errors='ignore', newline='')
                ret = ensure_str(file.read(), encoding='utf-8', errors='ignore')
                file.close()
                activePlayer = {}
                ret = json_loads(ret)
                activePlayer['buffering'] = ret['buffering']
                activePlayer['player'] = CFakeMoviePlayerOption(ret['player']['value'], ret['player']['text'])
                self.activePlayer = activePlayer
                sts = True
        except Exception:
            printExc()
        return sts, ret

    def save(self):
        from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
        sts = False
        try:
            if {} == self.activePlayer and os.path.isfile(self.filePath):
                os.remove(self.filePath)
            elif self.activePlayer.get('buffering', None) is None:
                printDBG('WARNING: buffering NOT set')
            else:
                data = {}
                data['buffering'] = self.activePlayer['buffering']
                data['player'] = {'value': self.activePlayer['player'].value, 'text': self.activePlayer['player'].getText()}
                data = json_dumps(ensure_str(data))
                with io.open(self.filePath, 'w', encoding='utf-8', errors='replace', newline='') as file:
                    file.write(data)
                sts = True
        except Exception:
            printExc()
        return sts

    def get(self, key, defval):
        return self.activePlayer.get(key, defval)

    def set(self, activePlayer):
        self.activePlayer = activePlayer
        self.save()


def byteify(input, noneReplacement=None, baseTypesAsString=False):
    """
    if isinstance(input, dict):
        return dict([(byteify(key, noneReplacement, baseTypesAsString), byteify(value, noneReplacement, baseTypesAsString)) for key, value in input.items()])
    elif isinstance(input, list):
        return [byteify(element, noneReplacement, baseTypesAsString) for element in input]
    elif isinstance(input, str):
        return input.encode('utf-8')
    elif input == None and noneReplacement != None:
        return noneReplacement
    elif baseTypesAsString:
        return str(input)
    else:
    """
    return input


LASTExcMSG = ''


def clearExcMSG():
    global LASTExcMSG
    LASTExcMSG = ''


def getExcMSG(clearExcMSG=True):
    global LASTExcMSG
    retMSG = LASTExcMSG
    if clearExcMSG:
        LASTExcMSG = ''
    return retMSG


def printExc(msg='', WarnOnly=False):
    global LASTExcMSG
    isWarning = False
    printDBG("===============================================")
    if WarnOnly:
        printDBG("                    WARNING")
        isWarning = True
    elif msg.startswith('WARNING'):
        printDBG("                    WARNING")
        msg = msg[7:]
        isWarning = True
    elif msg.startswith('EXCEPTION'):
        printDBG("                    EXCEPTION")
        msg = msg[9:]
    else:
        printDBG("                   EXCEPTION")
    printDBG("===============================================")
    exc_formatted = traceback.format_exc()
    if msg == '' or msg == 'WARNING':
        msg = '\n%s' % exc_formatted
    else:
        msg = msg + ': \n%s' % exc_formatted
    printDBG(msg)
    printDBG("===============================================")
    try:
        retMSG = exc_formatted.splitlines()[-1]
    except Exception:
        retMSG = ''
    if not isWarning:
        LASTExcMSG = retMSG
    return retMSG  # returns the error description to possibly use in main code. E.g. inform about failed login


def GetIPTVPlayerVersion():
    try:
        from Plugins.Extensions.IPTVPlayer.version import IPTV_VERSION
    except Exception:
        IPTV_VERSION = "XX.YY.ZZ"
    return IPTV_VERSION


def GetIPTVPlayerComitStamp():
    try:
        from Plugins.Extensions.IPTVPlayer.version import COMMIT_STAMP
    except Exception:
        COMMIT_STAMP = ""
    return COMMIT_STAMP


def GetShortPythonVersion():
    return "%d.%d" % (sys.version_info[0], sys.version_info[1])


def GetImageName():
    """The image's PRETTY_NAME from /etc/os-release, or '' if unavailable."""
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    return line.split('=', 1)[1].strip().strip('"')
    except Exception:
        pass
    return ''


def GetShortSystemInfo():
    """A one-line image/box/python string for the top of the debug log."""
    box = ''
    try:
        import boxbranding
        box = boxbranding.getBoxType()
    except Exception:
        pass
    return "image[%s] box[%s] python[%s]" % (GetImageName() or '?', box or '?', GetShortPythonVersion())


def GetVersionNum(ver):
    if ver == '':
        return 0
    try:
        if None is re.match(r"[0-9]+\.[0-9][0-9]\.[0-9][0-9]\.[0-9][0-9]", ver):
            raise Exception("Wrong version!")
        return int(ver.replace('.', ''))
    except Exception:
        printExc('Version[%r]' % ver)
        return 0


# the optional native _subparser.so is checked once per session (it is called for every subtitle
# load), the config switch still on every call
_subParserExtensionState = []


def IsSubtitlesParserExtensionCanBeUsed():
    try:
        if not config.plugins.iptvplayer.useSubtitlesParserExtension.value:
            return False
    except Exception:
        return False
    if not _subParserExtensionState:
        available = False
        try:
            from Plugins.Extensions.IPTVPlayer.libs.iptvsubparser import _subparser as subparser
            available = '' != subparser.version()
            printDBG('Subtitles Parser Extension available' if available else 'Subtitles Parser Extension has no version - using the Python parser')
        except ImportError:
            printDBG('Subtitles Parser Extension not installed - using the Python parser')
        except Exception:
            printExc('WARNING - Subtitles Parser Extension NOT available')
        _subParserExtensionState.append(available)
    return _subParserExtensionState[0]


def IsBrokenDriver(filePath):
    # workaround for broken DVB driver mbtwinplus:
    # root@mbtwinplus:~# cat /proc/stb/video/policy2
    # Segmentation fault
    try:
        if 'video/policy' in filePath and not fileExists('/proc/stb/video/aspect_choices'):
            with open('/etc/hostname', 'r') as f:
                data = f.read().strip()
            if 'mbtwinplus' in data:
                return True
    except Exception:
        printExc()
    return False


def GetE2OptionsFromFile(filePath):
    options = []
    if IsBrokenDriver(filePath):
        return []
    try:
        if fileExists(filePath):
            with open(filePath, 'r') as f:
                data = f.read().strip()
                data = data.split(' ')
                for item in data:
                    opt = item.strip()
                    if '' != opt:
                        options.append(opt)
        else:
            printDBG('GetE2OptionsFromFile file[%s] not exists' % filePath)
    except Exception:
        printExc()
    return options


def SetE2OptionByFile(filePath, value):
    if IsBrokenDriver(filePath):
        return False
    sts = False
    try:
        with open(filePath, 'w') as f:
            data = f.write(value)
            sts = True
    except Exception:
        printExc()
    return sts


def GetE2VideoAspectChoices():
    tab = GetE2OptionsFromFile('/proc/stb/video/aspect_choices')
    # workaround for some STB
    # reported here: https://gitlab.com/iptvplayer-for-e2/iptvplayer-for-e2/issues/30
    staticTab = ["4:3", "16:9", "any"]
    if len(tab) < 2 and GetE2VideoAspect() in staticTab:
        tab = staticTab
    return tab


def GetE2VideoAspect():
    options = GetE2OptionsFromFile('/proc/stb/video/aspect')
    if 1 == len(options):
        return options[0]
    return None


def SetE2VideoAspect(value):
    return SetE2OptionByFile('/proc/stb/video/aspect', value)


def GetE2VideoPolicyChoices(num=''):
    return GetE2OptionsFromFile('/proc/stb/video/policy%s_choices' % num)


def GetE2VideoPolicy(num=''):
    options = GetE2OptionsFromFile('/proc/stb/video/policy' + num)
    if 1 == len(options):
        return options[0]
    return None


def SetE2VideoPolicy(value, num=''):
    return SetE2OptionByFile('/proc/stb/video/policy' + num, value)


def GetE2AudioCodecMixChoices(codec):
    return GetE2OptionsFromFile('/proc/stb/audio/%s_choices' % codec)


def GetE2AudioCodecMixOption(codec):
    options = GetE2OptionsFromFile('/proc/stb/audio/%s' % codec)
    if 1 == len(options):
        return options[0]
    return None


def SetE2AudioCodecMixOption(codec, value):
    return SetE2OptionByFile('/proc/stb/audio/%s' % codec, value)

# videomode


def GetE2VideoModeChoices():
    # return 'pal ntsc 480i 576i 480p 576p 720p50 720p 1080i50 1080i 1080p24 1080p25 1080p30 720p24 720p25 720p30 1080p50 1080p'.split(' ')
    return GetE2OptionsFromFile('/proc/stb/video/videomode_choices')


def GetE2VideoMode():
    # return '1080p50'
    options = GetE2OptionsFromFile('/proc/stb/video/videomode')
    if 1 == len(options):
        return options[0]
    return None


def SetE2VideoMode(value):
    return SetE2OptionByFile('/proc/stb/video/videomode', value)


def ReadUint16(tmp, le=True):
    if le:
        return tmp[1] << 8 | tmp[0]
    else:
        return tmp[0] << 8 | tmp[1]


def ReadUint32(tmp, le=True):
    if le:
        return tmp[3] << 24 | tmp[2] << 16 | tmp[1] << 8 | tmp[0]
    else:
        return tmp[0] << 24 | tmp[1] << 16 | tmp[2] << 8 | tmp[3]


def ReadGnuMIPSABIFP(elfFileName):
    SHT_GNU_ATTRIBUTES = 0x6ffffff5
    SHT_MIPS_ABIFLAGS = 0x7000002a
    Tag_GNU_MIPS_ABI_FP = 4
    Val_GNU_MIPS_ABI_FP_ANY = 0
    Val_GNU_MIPS_ABI_FP_DOUBLE = 1
    Val_GNU_MIPS_ABI_FP_SINGLE = 2
    Val_GNU_MIPS_ABI_FP_SOFT = 3
    Val_GNU_MIPS_ABI_FP_OLD_64 = 4
    Val_GNU_MIPS_ABI_FP_XX = 5
    Val_GNU_MIPS_ABI_FP_64 = 6
    Val_GNU_MIPS_ABI_FP_64A = 7
    Val_GNU_MIPS_ABI_FP_NAN2008 = 8

    def _readLeb128(data, start, end):
        result = 0
        numRead = 0
        shift = 0
        byte = 0

        while start < end:
            byte = data[start]
            numRead += 1

            result |= (byte & 0x7f) << shift

            shift += 7
            if byte < 0x80:
                break
        return numRead, result

    def _getStr(stsTable, idx):
        val = ''
        while stsTable[idx] != '\0':
            val += stsTable[idx]
            idx += 1
        return val

    Val_HAS_MIPS_ABI_FLAGS = False
    Val_GNU_MIPS_ABI_FP = -1
    try:
        with open(elfFileName, "rb") as file:
            # e_shoff - Start of section headers
            file.seek(32)
            shoff = ReadUint32(file.read(4))

            # e_shentsize - Size of section headers
            file.seek(46)
            shentsize = ReadUint16(file.read(2))

            # e_shnum -  Number of section headers
            shnum = ReadUint16(file.read(2))

            # e_shstrndx - Section header string table index
            shstrndx = ReadUint16(file.read(2))

            # read .shstrtab section header
            headerOffset = shoff + shstrndx * shentsize

            file.seek(headerOffset + 16)
            offset = ReadUint32(file.read(4))
            size = ReadUint32(file.read(4))

            file.seek(offset)
            secNameStrTable = file.read(size)

            for idx in range(shnum):
                offset = shoff + idx * shentsize
                file.seek(offset)
                sh_name = ReadUint32(file.read(4))
                sh_type = ReadUint32(file.read(4))
                if sh_type == SHT_GNU_ATTRIBUTES:
                    file.seek(offset + 16)
                    sh_offset = ReadUint32(file.read(4))
                    sh_size = ReadUint32(file.read(4))
                    file.seek(sh_offset)
                    contents = file.read(sh_size)
                    p = 0
                    if contents.startswith('A'):
                        p += 1
                        sectionLen = sh_size - 1
                        while sectionLen > 0:
                            attrLen = ReadUint32(contents[p:])
                            p += 4

                            if attrLen > sectionLen:
                                attrLen = sectionLen
                            elif attrLen < 5:
                                break
                            sectionLen -= attrLen
                            attrLen -= 4
                            attrName = _getStr(contents, p)

                            p += len(attrName) + 1
                            attrLen -= len(attrName) + 1

                            while attrLen > 0 and p < len(contents):
                                if attrLen < 6:
                                    sectionLen = 0
                                    break
                                tag = contents[p]
                                p += 1
                                size = ReadUint32(contents[p:])
                                if size > attrLen:
                                    size = attrLen
                                if size < 6:
                                    sectionLen = 0
                                    break

                                attrLen -= size
                                end = p + size - 1
                                p += 4

                                if tag == 1 and attrName == "gnu":  # File Attributes
                                    while p < end:
                                        # display_gnu_attribute
                                        numRead, tag = _readLeb128(contents, p, end)
                                        p += numRead
                                        if tag == Tag_GNU_MIPS_ABI_FP:
                                            numRead, val = _readLeb128(contents, p, end)
                                            p += numRead
                                            Val_GNU_MIPS_ABI_FP = val
                                            break
                                elif p < end:
                                    p = end
                                else:
                                    attrLen = 0
                elif sh_type == SHT_MIPS_ABIFLAGS:
                    Val_HAS_MIPS_ABI_FLAGS = True
    except Exception:
        printExc()
    return Val_HAS_MIPS_ABI_FLAGS, Val_GNU_MIPS_ABI_FP


def MergeDicts(*dict_args):
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def is_port_in_use(pIP, pPORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    res = sock.connect_ex((pIP, pPORT))
    sock.close()
    return res == 0


def hasCDM():
    try:
        from pywidevinecdm.checkCDMvalidity import testDevice
        return testDevice()
    except Exception:
        return False


def readCFG(cfgName, defVal=''):
    for myPath in ['/etc/enigma2/IPTVplayer_defaults/', '/hdd/IPTVplayer_defaults/']:
        if os.path.exists(myPath):
            cfgPath = os.path.join(myPath, cfgName)
            if os.path.exists(cfgPath):
                with open(cfgPath, 'r') as f:
                    retVal = f.readline().strip()
                if retVal == 'True':
                    retVal = True
                elif retVal == 'False':
                    retVal = False
                return retVal
            else:
                with open('/etc/enigma2/settings', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('config.plugins.iptvplayer.%s=' % cfgName):
                            defVal = line.split('=')[1]
                            with open(cfgPath, 'w') as fOut:
                                fOut.write(defVal)
    return defVal


def checkWebSiteStatus(URL, HEADERS=None, TIMEOUT=1):
    global LASTExcMSG
    if HEADERS is None:
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Accept-Charset': 'utf-8',
            'Content-Type': 'text/html; charset=utf-8'
    }
    req = urllib2_Request(URL, headers=HEADERS)
    try:
        response = urllib2_urlopen(req, timeout=TIMEOUT)
    except urllib2_HTTPError as e:
        LASTExcMSG = str(e)
        return (False, "Website returned error", str(e.code))
    except urllib2_URLError as e:
        LASTExcMSG = str(e)
        return (False, 'Website NOT available', str(e.reason))
    except socket.timeout as e:
        LASTExcMSG = str(e)
        return (False, 'Website overloaded and dont respond timely', str('Timeout %ss' % TIMEOUT))
    except Exception as e:
        LASTExcMSG = str(e)
        return (False, 'EXCEPTION', str(e))
    else:
        return (True, '', None)


def E2ColoR(color):
    COLORS_DEFINITIONS = {
        "black": "\\c00000000",
        "silver": "\\c00C0C0C0",
        "gray": "\\c00808080",
        "white": "\\c00FFFFFF",
        "maroon": "\\c00800000",
        "red": "\\c00FA8072",  # Soft red
        "purple": "\\c00800080",
        "fuchsia": "\\c00FF00FF",
        "aqua": "\\c0000FFFF",
        "teal": "\\c00008080",
        "blue": "\\c000000FF",
        "green": "\\c00008000",
        "lime": "\\c0030FF30",  # Vivid lime green
        "olive": "\\c00808000",
        "yellow": "\\c00FFFF30",  # Vivid yellow
        "navy": "\\c00000080",  # Dark blue
        "violet": "\\c00EE82EE",
        "dodgerblue": "\\c001E90FF",
        "lightcoral": "\\c00F08080",
        "lightred": "\\c00FF7950",
        "gold": "\\c00FFD700",
        "orange": "\\c00FFA500",
        "skyblue": "\\c0087CEEB",
        "coral": "\\c00FF7F50",
        "khaki": "\\c00F0E68C",
        "crimson": "\\c00DC143C",
        "cyan": "\\c0000FFFF"
    }
    try:
        return COLORS_DEFINITIONS.get(color, '') if config.plugins.iptvplayer.use_colors.value else ''
    except AttributeError:
        return ''


COLOR_CODE_RE = re.compile(r'\\c[0-9a-fA-F]{8}')


def StripColorCodes(text):
    # the \cAARRGGBB codes of E2ColoR, for places that need the plain text (searches, file names)
    return COLOR_CODE_RE.sub('', text or '')
