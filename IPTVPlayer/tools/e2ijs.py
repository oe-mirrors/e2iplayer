# -*- coding: utf-8 -*-
#
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_execute
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CreateTmpFile, rm, KeepDebugArtifact, GetJSCacheDir, \
                                                          ReadTextFile, WriteTextFile

########################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
########################################################
from Tools.Directories import fileExists

from binascii import hexlify
from hashlib import md5
import os
import shutil
import _thread

DUK_PATH = '/usr/bin/duk'
# QuickJS-ng (package "quickjs"): ES2023, much faster than duktape, but no
# bytecode files and no built-in time limit - busybox "timeout" does that part
QJS_PATH = '/usr/bin/qjs'
QJS_MEMORY_LIMIT = '64m'

# fallback cache key when the installed duktape version can't be read
DUKTAPE_VER = '226'
_dukVersion = None
_timeoutPrefix = None


def duktape_version():
    # key for the bytecode cache: duktape bytecode only loads in the version
    # that compiled it, so an updated duk must not reuse old .byte files
    global _dukVersion
    if _dukVersion is None:
        _dukVersion = DUKTAPE_VER
        sts, tmpPath = CreateTmpFile('.iptv_dukver.js', 'print(Duktape.version);')
        if sts:
            ret = iptv_execute()('%s "%s" 2> /dev/null' % (DUK_PATH, tmpPath))
            rm(tmpPath)
            data = ret.get('data', '').strip() if ret.get('sts') and ret.get('code') == 0 else ''
            if data.isdigit():
                _dukVersion = data
        printDBG('duktape_version [%s]' % _dukVersion)
    return _dukVersion


def quickjs_available():
    return os.path.isfile(QJS_PATH) and os.access(QJS_PATH, os.X_OK)


def duktape_execute(cmd_params):
    ret = {'sts': False, 'code': -12, 'data': ''}
    noDuk = False
    cmd = DUK_PATH
    if cmd != '':
        cmd += ' ' + cmd_params + ' 2> /dev/null'
        printDBG("duktape_execute cmd[%s]" % cmd)
        ret = iptv_execute()(cmd)

        if ret['code'] == 127:
            noDuk = True
    else:
        noDuk = True
        ret['code'] = 127

    if noDuk:
        messages = [_('The %s utility is necessary here but it was not detected.') % ('duktape')]
        messages.append(_('Please consider restart your Engima2 and agree to install the %s utlity when the %s will propose this.') % ('duktape', 'E2iPlayer'))
        GetIPTVNotify().push('\n'.join(messages), 'error', 40, 'no_duktape', 40)

    printDBG('duktape_execute cmd ret[%s]' % ret)
    return ret


def quickjs_execute(fileList, timeoutSec):
    # the files run one after another in one global context, like "duk a.js b.js";
    # -C: classic script, never auto-detected as ES module
    global _timeoutPrefix
    if not fileList:
        return {'sts': False, 'code': -12, 'data': ''}
    if _timeoutPrefix is None:
        _timeoutPrefix = 'timeout %d ' if shutil.which('timeout') else ''
    cmd = _timeoutPrefix % timeoutSec if _timeoutPrefix else ''
    cmd += '%s -C --memory-limit %s ' % (QJS_PATH, QJS_MEMORY_LIMIT)
    cmd += ' '.join(['-I "%s"' % file for file in fileList[:-1]] + ['"%s"' % fileList[-1]])
    cmd += ' 2> /dev/null'
    printDBG("quickjs_execute cmd[%s]" % cmd)
    ret = iptv_execute()(cmd)
    printDBG('quickjs_execute cmd ret[%s]' % ret)
    return ret


def js_execute(jscode, params={}):
    ret = {'sts': False, 'code': -12, 'data': ''}
    sts, tmpPath = CreateTmpFile('.iptv_js.js', jscode)
    if sts:
        if quickjs_available():
            ret = quickjs_execute([tmpPath], params.get('timeout_sec', 20))
        else:
            ret = duktape_execute('-t %s ' % params.get('timeout_sec', 20) + ' ' + tmpPath)

    # leave last script for debug purpose
    if not KeepDebugArtifact('debug_keep_js_scripts'):
        rm(tmpPath)

    printDBG('js_execute cmd ret[%s]' % ret)
    return ret


def _cacheFiles(name, useQuickJS):
    # quickjs caches the extracted source, duktape the compiled bytecode
    if useQuickJS:
        return GetJSCacheDir(name + '.js'), GetJSCacheDir(name + '.qjs.meta'), 'qjs'
    return GetJSCacheDir(name + '.byte'), GetJSCacheDir(name + '.meta'), duktape_version()


def js_execute_ext(items, params={}):
    fileList = []
    tmpFiles = []

    # precompiled duktape bytecode (jsscripts/*.byte) only runs in duktape
    useQuickJS = quickjs_available() and not any(item.get('path', '').endswith('.byte') for item in items)
    printDBG('js_execute_ext engine[%s]' % ('quickjs' if useQuickJS else 'duktape'))

    tid = _thread.get_ident()
    uniqueId = 0
    ret = {'sts': False, 'code': -13, 'data': ''}
    try:
        for item in items:
            # we can have source file or source code
            path = item.get('path', '')
            code = item.get('code', '')
            codeFromPath = False

            name = item.get('name', '')
            if name:  # cache enabled
                hash = item.get('hash', '')
                if not hash:
                    # we will need to calc hash by our self
                    if path:
                        sts, code = ReadTextFile(path)
                        if not sts:
                            raise Exception('Faile to read file "%s"!' % path)
                        codeFromPath = True
                    hash = ensure_str(hexlify(md5(ensure_binary(code)).digest()))
                cacheFileName, metaFileName, cacheVer = _cacheFiles(name, useQuickJS)
                if fileExists(cacheFileName):
                    sts, tmp = ReadTextFile(metaFileName)
                    if sts:
                        tmp = tmp.split('|')  # engine version|hash
                        if cacheVer != tmp[0] or hash != tmp[-1].strip():
                            sts = False
                    if not sts:
                        rm(cacheFileName)
                        rm(metaFileName)
                else:
                    sts = False

                if not sts:
                    # remove old meta
                    rm(metaFileName)

                    if useQuickJS:
                        if path and not codeFromPath:
                            sts, code = ReadTextFile(path)
                            if not sts:
                                raise Exception('Faile to read file "%s"!' % path)
                        if not code:
                            # cache vanished after is_js_cached() and the caller sent no code
                            raise Exception('No code to cache for "%s"!' % name)
                        if not WriteTextFile(cacheFileName, code):
                            raise Exception('Faile to write "%s" file!' % cacheFileName)
                    else:
                        # we need compile here
                        if not path:
                            if not code:
                                # cache vanished after is_js_cached() and the caller sent no code
                                raise Exception('No code to cache for "%s"!' % name)
                            path = '.%s.js' % name
                            sts, path = CreateTmpFile(path, code)
                            if not sts:
                                raise Exception('Faile to create file "%s" "%s"' % (path, code))
                            tmpFiles.append(path)

                        # compile
                        if 0 != duktape_execute('-c "%s" "%s" ' % (cacheFileName, path))['code']:
                            raise Exception('Compile to bytecode file "%s" > "%s" failed!' % (path, cacheFileName))

                    # update meta
                    if not WriteTextFile(metaFileName, '%s|%s' % (cacheVer, hash)):
                        raise Exception('Faile to write "%s" file!' % metaFileName)

                fileList.append(cacheFileName)
            else:
                if path:
                    fileList.append(path)
                else:
                    path = 'e2i_js_exe_%s_%s.js' % (uniqueId, tid)
                    uniqueId += 1
                    sts, path = CreateTmpFile(path, code)
                    if not sts:
                        raise Exception('Faile to create file "%s"' % path)
                    tmpFiles.append(path)
                    fileList.append(path)
        if useQuickJS:
            ret = quickjs_execute(fileList, params.get('timeout_sec', 20))
        else:
            ret = duktape_execute(' '.join(['"%s"' % file for file in fileList]))
    except Exception:
        printExc()

    # leave last script for debug purpose
    if not KeepDebugArtifact('debug_keep_js_scripts'):
        for file in tmpFiles:
            rm(file)
    return ret


def is_js_cached(name, hash):
    ret = False
    cacheFileName, metaFileName, cacheVer = _cacheFiles(name, quickjs_available())
    if fileExists(cacheFileName):
        sts, tmp = ReadTextFile(metaFileName)
        if sts:
            tmp = tmp.split('|')
            if cacheVer == tmp[0] and hash == tmp[-1].strip():
                ret = True
    return ret
