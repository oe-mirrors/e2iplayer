# -*- coding: utf-8 -*-
# "Downloaded" state of a host item, shown as a marker at the end of its list row.
#
# The download manager writes a marker when a download that was started from a host list has
# finished (see IPTVDMApi.cmdFinished); the list only reads it. The item is recognised by the
# host and its own url (its title when it has none), so the same item is found again in the
# host's list, in the favourites and inside a favourite folder.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc, GetDownloadedDir, mkdirs, rm
from Plugins.Extensions.IPTVPlayer.libs.crypto.hash.md5Hash import MD5
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
###################################################
# FOREIGN import
###################################################
from binascii import hexlify
import os
###################################################

STATE_NONE = ''
STATE_ACTIVE = 'active'  # waiting in the download queue or downloading right now
STATE_DONE = 'done'  # downloaded and the file is still there


def getItemKey(hostName, url, name):
    # the item of a host list -> key string "<host>|<url or title>", '' if it can not be told apart
    source = ensure_str(url or '').strip()
    if source == '':
        source = 'name:' + ensure_str(name or '').strip()
    if source == 'name:' or not hostName:
        return ''
    return '%s|%s' % (hostName, source)


def _getMarkerPath(key):
    hostName, source = key.split('|', 1)
    hashData = hexlify(MD5()(source))
    if not isPY2():
        hashData = hashData.decode()
    return GetDownloadedDir('%s/.%s.iptvdl' % (hostName, hashData))


def markDownloaded(key, filePath):
    # remembers the file a finished download of the item was written to
    try:
        if key == '' or filePath in [None, '']:
            return False
        markerPath = _getMarkerPath(key)
        if not mkdirs(os.path.dirname(markerPath)):
            return False
        # bytes, so a file name with umlauts does not depend on the locale of the box
        with open(markerPath, 'wb') as f:
            f.write(ensure_binary(ensure_str(filePath)))
        return True
    except Exception:
        printExc()
    return False


def getState(key, activeKeys=()):
    # activeKeys: item keys of the downloads that are queued or running
    try:
        if key == '':
            return STATE_NONE
        if key in activeKeys:
            return STATE_ACTIVE
        markerPath = _getMarkerPath(key)
        if not os.path.isfile(markerPath):
            return STATE_NONE
        with open(markerPath, 'rb') as f:
            filePath = ensure_str(f.read()).strip()
        if filePath != '' and os.path.isfile(filePath):
            return STATE_DONE
        # the file was moved or deleted - not downloaded (any more). Only when its folder is there and
        # not empty: a download disk that is just not mounted right now (an empty mount point folder)
        # must not cost the markers; either way the item is shown as not downloaded
        folder = os.path.dirname(filePath)
        if filePath != '' and os.path.isdir(folder) and os.listdir(folder):
            rm(markerPath)
    except Exception:
        printExc()
    return STATE_NONE
