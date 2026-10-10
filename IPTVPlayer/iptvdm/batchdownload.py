# -*- coding: utf-8 -*-
# Added: 10.10.2026 - batch download ("download all items of this list")
#
# The rows of a host list go into the download manager at once, each only with what it takes to reopen
# it later - host name + the data a favourite of the row stores (getFavouriteDataOfRow). The download
# manager looks up the links of a row only when the row's turn comes, in a worker thread of its own
# (BatchResolveThread, never in the GUI thread), and then starts the normal downloader with the url.
# A row that fails (no link, captcha, host error, ...) ends as ERROR with the reason and the queue goes on.
#
# The list side lives in components/iptvplayerwidget.py, the queue side in iptvdm/iptvdmapi.py. The
# functions without host / GUI access are kept free of enigma2 imports (tests/test_batchdownload.py).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
import threading
import time
try:
    import ctypes
except Exception:
    ctypes = None
###################################################

# CDisplayListItem.TYPE_VIDEO / TYPE_AUDIO (components/ihost.py is not imported here: it pulls in the GUI)
TYPE_VIDEO = 'VIDEO'
TYPE_AUDIO = 'AUDIO'
BATCH_TYPES = (TYPE_VIDEO, TYPE_AUDIO)

# a row whose links are not found after this long is given up (ERROR) and the queue goes on
RESOLVE_TIMEOUT = 240


def batchPauseLeft(lastLookup, now, pause):
    # seconds to wait before the next link lookup of a host whose last one ended at lastLookup (0: go)
    try:
        pause = int(pause)
    except (TypeError, ValueError):
        pause = 0
    if pause <= 0 or not lastLookup or now < lastLookup:
        return 0
    return max(0, int(round(lastLookup + pause - now)))

# what a title must not contain to be a file name - the same characters playVideo() always replaced
FILE_NAME_FORBIDDEN = '/:*?"<>|'

FILE_EXTENSIONS = ['avi', 'flv', 'mp4', 'ts', 'mov', 'wmv', 'mpeg', 'mpg', 'mkv', 'vob', 'divx', 'm2ts', 'mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac']

# summary notification: this many failed titles, each cut to this length
SUMMARY_MAX_TITLES = 5
SUMMARY_TITLE_LEN = 30


def cleanFileTitle(title):
    # the title of a list row as (part of) a file name
    for char in FILE_NAME_FORBIDDEN:
        title = title.replace(char, '-')
    return title


def getFileExt(url, itemType):
    # file extension of a download of url (strwithmeta), the format the host gave first
    fileFormat = url.meta.get('iptv_format', '')
    if '' != fileFormat:
        return '.' + fileFormat
    protocol = url.meta.get('iptv_proto', '')

    fileExtension = ''
    tmp = url.lower().split('?', 1)[0]
    for item in FILE_EXTENSIONS:
        if tmp.endswith('.' + item):
            fileExtension = '.' + item
            break

    if '' == fileExtension:
        if protocol in ['mms', 'mmsh', 'rtsp']:
            fileExtension = '.wmv'
        elif protocol in ['f4m', 'uds', 'rtmp']:
            fileExtension = '.flv'
        else:
            if itemType == TYPE_VIDEO:
                fileExtension = '.mp4'  # default video extension
            else:
                fileExtension = '.mp3'  # default audio extension
    return fileExtension


def isUrlBlocked(url, itemType, blockWmv=None):
    # (blocked, reason) of a decorated url; blockWmv None = the "Block wmv files" setting
    if blockWmv is None:
        from Components.config import config
        blockWmv = config.plugins.iptvplayer.ZablokujWMV.value
    protocol = url.meta.get('iptv_proto', '')
    if ".wmv" == getFileExt(url, itemType) and blockWmv:
        return True, _("Format 'wmv' blocked in configuration.")
    elif '' == protocol:
        return True, _("Unknown protocol [%s]") % url
    return False, ''


def isLiveRow(rawItem):
    # the host's own item dict marks a live stream - never offered for a batch download
    return isinstance(rawItem, dict) and bool(rawItem.get('live') or rawItem.get('is_live'))


def selectBatchRows(rows, activeKeys, isDownloaded):
    # rows: [{'title', 'key', 'source', 'pin', 'live', ...}] in list order -> (rows to queue, number skipped).
    # Skipped: no download marker key (the item can not be told apart), no way to reopen it, a PIN that is
    # not entered yet, live, already queued / downloading (activeKeys) or downloaded, twice in the list.
    accepted = []
    seen = set()
    skipped = 0
    for row in rows:
        key = row.get('key', '')
        if not key or not row.get('source') or row.get('pin') or row.get('live') or key in seen or key in activeKeys or isDownloaded(key):
            skipped += 1
            continue
        seen.add(key)
        accepted.append(row)
    return accepted, skipped


def makeBatchSource(row, downloadsDir):
    # what the download manager keeps of a row until its turn (DMItem.batchSource)
    hostName, favData = row['source'][0], row['source'][1]
    return {'host': hostName, 'data': favData, 'type': row.get('type', TYPE_VIDEO), 'title': row['title'],
            'file': downloadsDir + '/' + cleanFileTitle(row['title'])}


def filterCandidates(urls, itemType, decorate, isBlocked):
    # resolved urls of one link -> (decorated urls that may be downloaded, reason when there is none).
    # The order stays: the host / urlparser puts the preferred quality first, the same one the list
    # takes itself when it does not ask (one link, the autoplay sequencer).
    candidates = []
    reason = ''
    for url in urls:
        try:
            if len(url) < 4 or url.startswith('file://'):
                continue
        except Exception:
            continue
        url = decorate(url)
        blocked, why = isBlocked(url, itemType)
        if blocked:
            reason = why
            continue
        candidates.append(url)
    return candidates, reason


def pickDownloadable(candidates, itemType, isDownloadable):
    # the first candidate a downloader can be created for -> (url, file extension, reason)
    reason = ''
    for url in candidates:
        if isDownloadable(url):
            return url, getFileExt(url, itemType), ''
        reason = _("File can not be downloaded. Protocol [%s] is unsupported") % url.meta.get('iptv_proto', '')
    return None, '', reason


def _shortTitle(title):
    title = (title or '').strip()
    if len(title) > SUMMARY_TITLE_LEN:
        title = title[:SUMMARY_TITLE_LEN - 3].rstrip() + '...'
    return title


def batchSummary(results):
    # results: [(title, state)] of all rows of one batch, state 'ok' / 'failed' / 'removed' (taken out of the
    # queue by the user: not counted) -> (text, second line, colour) of the notification, None when the user
    # took all of them out
    total = len([title for title, state in results if state != 'removed'])
    if 0 == total:
        return None
    done = len([title for title, state in results if state == 'ok'])
    failed = [_shortTitle(title) for title, state in results if state == 'failed']
    text = _("%d of %d downloaded") % (done, total)
    status = ', '.join(failed[:SUMMARY_MAX_TITLES])
    if len(failed) > SUMMARY_MAX_TITLES:
        status += ', ...'
    if done == total:
        colour = 'green'
    elif 0 == done:
        colour = 'red'
    else:
        colour = 'orange'
    return text, status, colour


def _noticeReason(notices):
    # the last message the host wanted to show on the TV (captcha, MyE2i needed, ...), first line, short
    for notice in reversed(notices or []):
        text = (notice.get('text', '') or '').strip()
        if text:
            text = text.split('\n')[0].strip()
            return text[:120]
    return ''


def _urlsOfRet(ret):
    # RetHost of getLinksForFavourite / getResolvedURL -> [(url, needs resolve)]
    from Plugins.Extensions.IPTVPlayer.components.ihost import RetHost, CUrlItem
    urls = []
    if ret is not None and RetHost.OK == ret.status and isinstance(ret.value, list):
        for item in ret.value:
            if isinstance(item, CUrlItem):
                urls.append((item.url, str(item.urlNeedsResolve) == '1'))
            elif isinstance(item, str):
                urls.append((item, False))
    return urls


def loadHost(hostName):
    # a new instance of the host, the way the favourites open one (hosts/hostfavourites.py)
    from Plugins.Extensions.IPTVPlayer.components.ihost import IHost
    module = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], 0)
    host = module.IPTVHost()
    if not isinstance(host, IHost):
        raise ValueError('host %s is no IHost' % hostName)
    return host


class BatchError(Exception):
    pass


def resolveBatchSource(source, notices=None, blockWmv=None):
    # Runs in the worker thread. The links of the row like a favourite of it, the first link that
    # resolves to a url which may be downloaded -> list of decorated candidate urls (best first).
    # Raises BatchError with the reason. Downloader objects are not created here (some create enigma2
    # objects in their constructor): the download manager checks IsUrlDownloadable in the main thread.
    from Plugins.Extensions.IPTVPlayer.components.ihost import CFavItem
    from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import GetIPTVPlayerLastHostError
    from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser

    hostName = source['host']
    itemType = source.get('type', TYPE_VIDEO)
    # the last host error is one global for all threads: only a new one is about this row
    previousError = GetIPTVPlayerLastHostError(False)
    try:
        host = loadHost(hostName)
    except Exception as e:
        printExc()
        raise BatchError(_("Last Exception error: '%s'") % str(e))

    favItem = CFavItem(name=source.get('title', ''), type=itemType, data=source['data'], resolver=hostName)
    favItem.hostName = hostName

    def isBlocked(url, urlType):
        return isUrlBlocked(url, urlType, blockWmv)

    reason = ''
    try:
        links = _urlsOfRet(host.getLinksForFavourite(favItem))
    except Exception as e:
        printExc()
        links = []
        reason = _("Last Exception error: '%s'") % str(e)
    printDBG("resolveBatchSource host[%s] title[%s] links[%d]" % (hostName, source.get('title', ''), len(links)))
    for url, needsResolve in links:
        if needsResolve:
            try:
                urls = [pair[0] for pair in _urlsOfRet(host.getResolvedURL(url))]
            except Exception as e:
                printExc()
                reason = _("Last Exception error: '%s'") % str(e)
                continue
        else:
            urls = [url]
        candidates, why = filterCandidates(urls, itemType, urlparser.decorateUrl, isBlocked)
        if candidates:
            return candidates
        reason = why or reason
    reason = _noticeReason(notices) or reason
    if not reason:
        lastError = GetIPTVPlayerLastHostError(False)
        if lastError and lastError != previousError:
            reason = _('Last error: "%s"') % lastError
        else:
            reason = _("No valid links available.")
    raise BatchError(reason)


class BatchResolveThread(threading.Thread):
    # Looks up one row (resolveBatchSource). The download manager polls finished / elapsed() from its
    # timer in the main thread and gives up with cancel() after RESOLVE_TIMEOUT.
    # What a host would open on the TV (captcha, MyE2i, message boxes) lands in e2iWebNotices instead
    # (components/asynccall.py MainSessionWrapper, the same as for the web interface): nobody sits in
    # front of a batch download, a dialog would only wait forever.
    def __init__(self, source, downloadIdx):
        threading.Thread.__init__(self)
        self.name = 'batchResolve'
        self.daemon = True
        self.source = source
        self.downloadIdx = downloadIdx
        self.e2iWebNotices = []
        # what asynccall.AsyncCall gives the GUI's worker threads: without it IsThreadTerminated() says
        # "terminated" and pCommon's PyCurl requests are never sent
        self._iptvplayer_ext = {'kill_lock': threading.Lock(), 'killable': True, 'terminated': False, 'iptv_execute': None}
        self.candidates = []
        self.error = ''
        self.finished = False
        self.startTime = time.time()

    def elapsed(self):
        return time.time() - self.startTime

    def run(self):
        try:
            self.candidates = resolveBatchSource(self.source, self.e2iWebNotices)
        except BatchError as e:
            self.error = e.args[0] if e.args else _("No valid links available.")
        except SystemExit:
            self.error = _("Operation timed out.")
        except Exception as e:
            printExc()
            self.error = _("Last Exception error: '%s'") % str(e)
        finally:
            self.finished = True

    def cancel(self):
        # Called from the main thread. Like asynccall.AsyncCall.kill: a running PyCurl request stops
        # at once (its progress callback asks IsThreadTerminated), an external program is ended; code
        # marked not killable ends by itself. The thread is not waited for - its result is ignored.
        try:
            with self._iptvplayer_ext['kill_lock']:
                killable = self._iptvplayer_ext['killable']
                self._iptvplayer_ext['terminated'] = True
            if not killable:
                return
            execute = self._iptvplayer_ext.get('iptv_execute')
            if execute is not None:
                try:
                    execute.terminate()
                except Exception:
                    printExc()
            if ctypes is not None and self.ident is not None and self.is_alive():
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.ident), ctypes.py_object(SystemExit))
                if res > 1:
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.ident), None)
        except Exception:
            printExc()
