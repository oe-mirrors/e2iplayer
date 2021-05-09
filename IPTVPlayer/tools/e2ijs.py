# -*- coding: utf-8 -*-
#
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_execute
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDukPath, CreateTmpFile, rm, getDebugMode, GetJSCacheDir, \
                                                          ReadTextFile, WriteTextFile

from Tools.Directories import fileExists

from binascii import hexlify
from hashlib import md5
import time
import thread

DUKTAPE_VER = '226'


def duktape_execute(cmd_params):
    ret = {'sts': False, 'code': -12, 'data': ''}
    noDuk = False
    cmd = GetDukPath()
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


def js_execute(jscode, params={}):
    ret = {'sts': False, 'code': -12, 'data': ''}
    sts, tmpPath = CreateTmpFile('.iptv_js.js', jscode)
    if sts:
        ret = duktape_execute('-t %s ' % params.get('timeout_sec', 20) + ' ' + tmpPath)

    # leave last script for debug purpose
    if getDebugMode() == '':
        rm(tmpPath)

    printDBG('js_execute cmd ret[%s]' % ret)
    return ret


def js_execute_ext(items, params={}):
    fileList = []
    tmpFiles = []

    tid = thread.get_ident()
    uniqueId = 0
    ret = {'sts': False, 'code': -13, 'data': ''}
    try:
        for item in items:
            # we can have source file or source code
            path = item.get('path', '')
            code = item.get('code', '')

            name = item.get('name', '')
            if name: # cache enabled
                hash = item.get('hash', '')
                if not hash:
                    # we will need to calc hash by our self
                    if path:
                        sts, code = ReadTextFile(path)
                        if not sts:
                            raise Exception('Faile to read file "%s"!' % path)
                    hash = hexlify(md5(code).digest())
                byteFileName = GetJSCacheDir(name + '.byte')
                metaFileName = GetJSCacheDir(name + '.meta')
                if fileExists(byteFileName):
                    sts, tmp = ReadTextFile(metaFileName)
                    if sts:
                        tmp = tmp.split('|') # DUKTAPE_VER|hash
                        if DUKTAPE_VER != tmp[0] or hash != tmp[-1].strip():
                            sts = False
                    if not sts:
                        rm(byteFileName)
                        rm(metaFileName)
                else:
                    sts = False

                if not sts:
                    # we need compile here
                    if not path:
                        path = '.%s.js' % name
                        sts, path = CreateTmpFile(path, code)
                        if not sts:
                            raise Exception('Faile to create file "%s" "%s"' % (path, code))
                        tmpFiles.append(path)

                    # remove old meta
                    rm(metaFileName)

                    # compile
                    if 0 != duktape_execute('-c "%s" "%s" ' % (byteFileName, path))['code']:
                        raise Exception('Compile to bytecode file "%s" > "%s" failed!' % (path, byteFileName))

                    # update meta
                    if not WriteTextFile(metaFileName, '%s|%s' % (DUKTAPE_VER, hash)):
                        raise Exception('Faile to write "%s" file!' % metaFileName)

                fileList.append(byteFileName)
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
        #ret = duktape_execute('-t %s ' % params.get('timeout_sec', 20) + ' '.join([ '"%s"' % file for file in fileList ]) )
        ret = duktape_execute(' '.join(['"%s"' % file for file in fileList]))
    except Exception:
        printExc()

    # leave last script for debug purpose
    if getDebugMode() == '':
        for file in tmpFiles:
            rm(file)
    return ret


def is_js_cached(name, hash):
    ret = False
    byteFileName = GetJSCacheDir(name + '.byte')
    metaFileName = GetJSCacheDir(name + '.meta')
    if fileExists(byteFileName):
        sts, tmp = ReadTextFile(metaFileName)
        if sts:
            tmp = tmp.split('|')
            if DUKTAPE_VER == tmp[0] and hash == tmp[-1].strip():
                ret = True
    return ret
