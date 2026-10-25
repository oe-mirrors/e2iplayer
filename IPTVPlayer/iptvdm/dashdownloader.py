# -*- coding: utf-8 -*-
#
#  IPTV download manager API
#
#  Added: 26.10.2026 - DASH VOD downloads in the download manager
#
#  A DASH link of getMPDLinksWithMeta (iptv_dash_sel, not live) is loaded segment by segment here instead of by
#  ffmpeg's dashdec: the chosen video and audio representation (libs/dashmpd.py downloadPlan) each into a part file
#  (init + segments one after the other = a playable fragmented MP4 / WebM), several segments at the same time, a
#  failed segment tried again instead of the whole download stopping, "Continue downloading" goes on at the last
#  segment written. ffmpeg then only puts the parts together (-c copy) into the container of the settings, with the
#  audio language of the MPD and - setting "Subtitles" = "MKV / .srt" - the subtitles fetched by then; the rest
#  (container, file name, .txt / cover, subtitles fetched later) is FFMPEGDownloader's.
#  Live DASH, buffered playback and an MPD the plan cannot be made for stay with FFMPEGDownloader.
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.ffmpegdownloader import FFMPEGDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import MKV_LANG_CODES, subtitleLangCode, safeRemoveFile
from Plugins.Extensions.IPTVPlayer.libs import dashmpd
###################################################
# FOREIGN import
###################################################
from enigma import eTimer
from Components.config import config
import hashlib
import json
import os
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
###################################################

# the work threads by part base (the requested file path): a new run of the same download waits for the one before,
# "Remove file" of a stopped one that still finishes its segment lets that thread remove its files itself
_loaders = {}
_loadersLock = threading.Lock()


def discardLoader(filePath):
    # a work thread of filePath still running (stopped, finishing its segment): it removes its parts and resume
    # state when it ends instead of writing the state again - True when there was one
    with _loadersLock:
        loader = _loaders.get(filePath)
    if not loader or not loader['thread'].is_alive():
        return False
    loader['discard'] = True
    loader['stop'].set()
    return True


class DASHDownloader(FFMPEGDownloader):
    # segments loaded at the same time per track, and how many may be in memory in all (loading + waiting for their
    # turn to be written)
    WORKERS = 4
    QUEUED = 6
    # tries of a segment, waits between them 1, 2, 4, 8, 15 s (x RETRY_WAIT) - about half a minute of a dropped
    # connection before the download stops ("Continue downloading" goes on from there)
    TRIES = 6
    MAX_RETRY_WAIT = 15
    RETRY_WAIT = 1
    TIMEOUT = 30
    # a SegmentBase / plain BaseURL file is loaded in pieces of this size
    CHUNK = 4 * 1024 * 1024
    STREAM_BLOCK = 64 * 1024
    # the resume state is written after so many seconds
    STATE_SECS = 2

    def __init__(self):
        FFMPEGDownloader.__init__(self)
        self.resumeExisting = False
        # 'load': the segments are loaded here, 'mux': ffmpeg puts the parts together, '': FFMPEGDownloader alone
        self.phase = ''
        self.work = {}
        self.stopEvent = threading.Event()
        self.pollTimer = None
        self.pollTimer_conn = None
        self.parts = []
        self.partBase = ''
        self.loadedBytes = 0
        self.muxedSubtitles = []

    def getName(self):
        return "dash"

    def start(self, url, filePath, params={}):
        meta = strwithmeta(url).meta
        if not meta.get('iptv_dash_sel') or meta.get('iptv_livestream') or not str(url).startswith(('http://', 'https://')):
            return FFMPEGDownloader.start(self, url, filePath, params)
        self.url = url
        self.filePath = filePath
        self.partBase = filePath
        self.downloaderParams = params
        self.outData = ''
        self.runUrl = None
        self.masterFallback = None
        self.fileCmdPath = ''
        self._prepareSidecarData(meta)
        self.liveState = {'live': False}
        self.phase = 'load'
        self.status = DMHelper.STS.DOWNLOADING
        self.work = {'done': 0, 'all': 0, 'bytes': 0, 'duration': 0, 'result': None, 'error': ''}
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self._load, args=(url, filePath, self.resumeExisting, self.work, self.stopEvent), name='E2iDashDownload')
        thread.daemon = True
        thread.start()
        self.pollTimer = eTimer()
        self.pollTimer_conn = eConnectCallback(self.pollTimer.timeout, self._poll)
        self.pollTimer.start(500)
        self.onStart()
        return BaseDownloader.CODE_OK

    ###################################################
    # the work thread
    ###################################################
    def _load(self, url, filePath, resume, work, stop):
        loader = {'thread': threading.current_thread(), 'stop': stop, 'discard': False}
        with _loadersLock:
            before = _loaders.get(filePath)
            _loaders[filePath] = loader
        if before and before['thread'].is_alive():
            # the run stopped just before still writes its last segment: its handle must not write into this one's file
            before['stop'].set()
            before['thread'].join(self.TIMEOUT + 5)
        try:
            self._loadParts(url, filePath, resume, work, stop)
        finally:
            with _loadersLock:
                if _loaders.get(filePath) is loader:
                    del _loaders[filePath]
            if loader['discard']:
                # "Remove file" while it was finishing: nothing of it stays
                DMHelper.removeResumeFiles(filePath)

    def _loadParts(self, url, filePath, resume, work, stop):
        try:
            finalUrl, data = dashmpd.fetchManifest(url)
            plan = dashmpd.downloadPlan(data, finalUrl, strwithmeta(url).meta.get('iptv_dash_sel'))
        except Exception as e:
            printExc()
            printDBG("DASHDownloader no plan (%s) -> ffmpeg" % e)
            work['result'] = 'fallback'
            return
        headers = dashmpd.linkHeaders(url)
        statePath, videoPart, audioPart = DMHelper.dashPartFiles(filePath)
        try:
            # the key names the tracks and their segment lists - not the pieces of a single file, a failed size
            # probe on "Continue" must not start the download over
            shape = [(t['type'], 'single' if t['single'] else len(t['segments'])) for t in plan['tracks']]
            key = hashlib.md5(('%s\n%s\n%s' % (url, strwithmeta(url).meta.get('iptv_dash_sel'), shape)).encode('utf-8')).hexdigest()
            state = self._readState(statePath, key) if resume else None
            sizes = (state or {}).get('sizes') or {}
            tracks = []
            for idx, track in enumerate(plan['tracks']):
                items = ([track['init']] if track['init'] else []) + list(track['segments'])
                if track['single']:
                    sizes[str(idx)] = self._fileSize(items[0][0], headers) or sizes.get(str(idx), 0)
                    items = self._pieces(items[0][0], sizes[str(idx)])
                tracks.append({'type': track['type'], 'lang': track.get('lang', ''), 'items': items, 'counted': track['counted'],
                               'path': videoPart if track['type'] == 'video' else audioPart})
            work['duration'] = plan['duration']
            work['all'] = sum(len(t['items']) for t in tracks)
            work['parts'] = [(t['path'], t['type'], t['lang']) for t in tracks]
            if state and not self._partsMatch(tracks, state['tracks']):
                printDBG("DASHDownloader part files do not match the resume state - starting over")
                state = None
            done = state['tracks'] if state else [[0, 0] for _t in tracks]
            printDBG("DASHDownloader %s: %s, %ds%s" % (url, ', '.join('%s %d' % (t['type'], len(t['items'])) for t in tracks), plan['duration'], ' (continued at %s)' % done if state else ''))
            work['done'] = sum(d[0] for d in done)
            work['bytes'] = sum(d[1] for d in done)
            saved = [0]

            def saveState(force=False):
                if force or time.time() - saved[0] >= self.STATE_SECS:
                    saved[0] = time.time()
                    self._writeState(statePath, key, done, sizes)
            for idx, track in enumerate(tracks):
                with open(track['path'], 'r+b' if done[idx][1] else 'wb') as fh:
                    fh.truncate(done[idx][1])
                    fh.seek(done[idx][1])
                    try:
                        finished = self._loadTrack(track, fh, done[idx], headers, work, stop, saveState)
                    finally:
                        saveState(True)
                if not finished:
                    work['result'] = 'stopped'
                    return
            work['result'] = 'done'
        except Exception as e:
            printExc()
            # the other segments of this run stop too (they would go on trying while the download is over)
            stop.set()
            work['error'] = str(e)
            work['result'] = 'error'

    def _loadTrack(self, track, fh, done, headers, work, stop, saveState):
        # the items of a track in order into its part file, WORKERS of them loaded at the same time; done = [items
        # written, bytes] (the resume state). False when stopped
        items = track['items']
        executor = ThreadPoolExecutor(max_workers=self.WORKERS)
        pending = deque()
        nextIdx = done[0]
        try:
            while nextIdx < len(items) or pending:
                while nextIdx < len(items) and len(pending) < self.QUEUED:
                    if items[nextIdx][1] == 'stream':
                        # a file without byte ranges: read in one go, after what is already queued
                        break
                    mayMiss = track['counted'] and nextIdx == len(items) - 1
                    pending.append(executor.submit(self._fetch, items[nextIdx], headers, stop, mayMiss))
                    nextIdx += 1
                if pending:
                    data = pending.popleft().result()
                else:
                    data = self._stream(items[nextIdx][0], headers, fh, work, stop)
                    nextIdx += 1
                if stop.is_set():
                    return False
                if data:
                    fh.write(data)
                    work['bytes'] += len(data)
                fh.flush()
                done[0] += 1
                done[1] = fh.tell()
                work['done'] += 1
                saveState()
            return True
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _retryWait(self, attempt, stop):
        if attempt + 1 < self.TRIES:
            stop.wait(min(2 ** attempt, self.MAX_RETRY_WAIT) * self.RETRY_WAIT)

    def _fetch(self, item, headers, stop, mayMiss=False):
        # one segment (url, byte range); tried again TRIES times; None for a missing last segment of a counted list
        url, byteRange = item
        error = None
        for attempt in range(self.TRIES):
            if stop.is_set():
                return b''
            try:
                resp = dashmpd.openUrl(url, headers, byteRange, self.TIMEOUT)
                try:
                    data = dashmpd.readRange(resp, byteRange)
                finally:
                    resp.close()
                if data or mayMiss:
                    return data
                # an empty answer (an error page with Content-Length 0) would be a gap in the file
                error = IOError('empty answer')
            except HTTPError as e:
                if mayMiss and e.code == 404:
                    # the segment count was rounded up from the period length
                    printDBG("DASHDownloader last segment not there (404): %s" % url)
                    return None
                error = e
                if e.code in (401, 403, 404, 410) and attempt:
                    break
            except Exception as e:
                error = e
            printDBG("DASHDownloader segment try %d failed (%s): %s" % (attempt + 1, error, url))
            self._retryWait(attempt, stop)
        raise IOError('segment failed (%s): %s' % (error, url))

    def _stream(self, url, headers, fh, work, stop):
        # a whole file without byte ranges straight into the part file; a broken connection starts it again from its
        # beginning (no ranges), at most TRIES times
        start = fh.tell()
        startBytes = work['bytes']
        error = None
        for attempt in range(self.TRIES):
            if stop.is_set():
                return b''
            fh.seek(start)
            fh.truncate(start)
            work['bytes'] = startBytes
            try:
                resp = dashmpd.openUrl(url, headers, timeout=self.TIMEOUT)
                try:
                    length = int(resp.headers.get('Content-Length') or 0)
                    read = 0
                    while True:
                        block = resp.read(self.STREAM_BLOCK)
                        if not block or stop.is_set():
                            # stopped: this block is not written (a new run may own the file already)
                            break
                        fh.write(block)
                        read += len(block)
                        work['bytes'] += len(block)
                finally:
                    resp.close()
                if stop.is_set():
                    return b''
                if length and read < length:
                    raise IOError('connection closed after %d of %d bytes' % (read, length))
                return b''
            except Exception as e:
                error = e
            printDBG("DASHDownloader file try %d failed (%s): %s" % (attempt + 1, error, url))
            self._retryWait(attempt, stop)
        raise IOError('file failed (%s): %s' % (error, url))

    def _fileSize(self, url, headers):
        # the size of a SegmentBase / plain BaseURL file from a Range probe (0 when the server has no ranges or the
        # probe failed)
        for _attempt in range(3):
            try:
                resp = dashmpd.openUrl(url, headers, '0-0', self.TIMEOUT)
                try:
                    match = re.search(r'/(\d+)', resp.headers.get('Content-Range', ''))
                    return int(match.group(1)) if resp.status == 206 and match else 0
                finally:
                    resp.close()
            except Exception:
                printExc()
        return 0

    def _pieces(self, url, size):
        # byte ranges of CHUNK, or one 'stream' item when the size is not known
        if size <= 0:
            return [(url, 'stream')]
        return [(url, '%d-%d' % (start, min(start + self.CHUNK, size) - 1)) for start in range(0, size, self.CHUNK)]

    def _readState(self, statePath, key):
        try:
            with open(statePath) as f:
                state = json.load(f)
            if state.get('key') == key:
                return state
            printDBG("DASHDownloader resume state of another download - starting over")
        except Exception:
            printDBG("DASHDownloader no resume state - starting over")
        return None

    def _partsMatch(self, tracks, done):
        # every part file holds at least the bytes its state names (a missing one would be filled with zeros)
        if len(done) != len(tracks):
            return False
        for track, (count, size) in zip(tracks, done):
            if count > len(track['items']) or (size and (not os.path.isfile(track['path']) or os.path.getsize(track['path']) < size)):
                return False
        return True

    def _writeState(self, statePath, key, done, sizes):
        try:
            with open(statePath + '.tmp', 'w') as f:
                json.dump({'key': key, 'tracks': done, 'sizes': sizes}, f)
            os.replace(statePath + '.tmp', statePath)
        except OSError:
            printExc()

    ###################################################
    # main thread
    ###################################################
    def _poll(self):
        self._updateProgress()
        result = self.work.get('result')
        if result is None:
            return
        self._stopPoll()
        if result == 'fallback':
            self.phase = ''
            self.fallbackRun = True  # same download: no second sidecar / onStart
            FFMPEGDownloader.start(self, self.url, self.filePath, self.downloaderParams)
        elif result == 'done':
            self._startMux()
        elif result == 'error' and self.status == DMHelper.STS.DOWNLOADING:
            printDBG("DASHDownloader stopped: %s" % self.work.get('error'))
            # with segments loaded "Continue downloading" goes on from the resume state (the download manager also
            # names it so by the size)
            self.status = DMHelper.STS.INTERRUPTED if self.work.get('bytes') else DMHelper.STS.ERROR
            self._finishDownloadFlow()

    def _stopPoll(self):
        if self.pollTimer is not None:
            self.pollTimer.stop()
        self.pollTimer_conn = None
        self.pollTimer = None

    def _updateProgress(self):
        if self.phase != 'load':
            return
        work = self.work
        self.totalDuration = int(work.get('duration') or 0)
        if work.get('all'):
            self.downloadDuration = int(self.totalDuration * work['done'] / work['all'])
        self.localFileSize = work.get('bytes', 0)

    def _muxSubtitles(self, outContainer):
        # setting "Subtitles" = "MKV / .srt": the subtitles fetched while the segments loaded go into this mux - no
        # second copy of the whole file for them afterwards (_subtitleStep); still fetching: the step after as before
        if outContainer != 'matroska' or not self.subJobs or self.subFetching:
            return []
        try:
            if config.plugins.iptvplayer.download_subtitles.value != 'mkv':
                return []
        except Exception:
            printExc()
            return []
        self.subHandled = True
        return self._writeSubtitleFiles(self.filePath)

    def _startMux(self):
        self.phase = 'mux'
        self.parts = self.work.get('parts', [])
        self.loadedBytes = self.work.get('bytes', 0)
        # ffmpeg's own progress from here on (_looksComplete)
        self.downloadDuration = 0
        self.localFileSize = 0
        self.headerReceived = False
        outContainer = self._outContainer()
        self.muxedSubtitles = self._muxSubtitles(outContainer)
        cmdTab = [DMHelper.GET_FFMPEG_PATH(), '-y']
        for path, _ctype, _lang in self.parts:
            cmdTab.extend(['-i', path])
        for item in self.muxedSubtitles:
            cmdTab.extend(['-i', item['path']])
        for idx in range(len(self.parts) + len(self.muxedSubtitles)):
            cmdTab.extend(['-map', str(idx)])
        cmdTab.extend(['-c', 'copy'])
        # the audio language of the MPD (the part files carry none: the track would read "und")
        audio = 0
        for _path, ctype, lang in self.parts:
            if ctype == 'audio':
                code = MKV_LANG_CODES.get(subtitleLangCode(lang))
                if code:
                    cmdTab.extend(['-metadata:s:a:%d' % audio, 'language=' + code])
                audio += 1
        for idx, item in enumerate(self.muxedSubtitles):
            if item['lang'] in MKV_LANG_CODES:
                cmdTab.extend(['-metadata:s:s:%d' % idx, 'language=' + MKV_LANG_CODES[item['lang']]])
            if item['title']:
                # cmdwrap splits the arguments at "|"
                cmdTab.extend(['-metadata:s:s:%d' % idx, 'title=' + item['title'].replace('|', '/')])
        if outContainer in ('mp4', 'mov'):
            cmdTab.extend(['-movflags', '+faststart'])
        cmdTab.extend(['-f', outContainer, self.filePath])
        printDBG("DASHDownloader mux: %d parts, %d subtitles" % (len(self.parts), len(self.muxedSubtitles)))
        self._execute(cmdTab)

    def _looksComplete(self, code=None):
        # every segment is there: a clean ffmpeg exit is a whole file, whatever its progress lines said
        return FFMPEGDownloader._looksComplete(self, code) or (code == 0 and self.phase == 'mux')

    def _fixFileExtension(self):
        # a failed mux keeps the requested name: the parts and the resume state are named after it ("Continue
        # downloading" puts them together again, "Remove file" removes them) - its broken output goes
        if self.phase == 'mux' and DMHelper.STS.DOWNLOADED != self.status:
            safeRemoveFile(self.filePath)
            return
        FFMPEGDownloader._fixFileExtension(self)

    def _cmdFinished(self, code, terminated=False):
        FFMPEGDownloader._cmdFinished(self, code, terminated)
        if self.phase == 'mux' and DMHelper.STS.DOWNLOADED == self.status:
            # the parts, the resume state and the subtitles that are inside the file now
            DMHelper.removeResumeFiles(self.partBase)
            for item in self.muxedSubtitles:
                safeRemoveFile(item['path'])

    def _terminate(self):
        if self.phase == 'load' and DMHelper.STS.DOWNLOADING == self.status:
            # the work thread ends after the segment it is writing and leaves its resume state
            printDBG("DASHDownloader._terminate")
            self.stopEvent.set()
            self._stopPoll()
            self._terminateSidecar()
            self.status = DMHelper.STS.INTERRUPTED
            return BaseDownloader.CODE_OK
        return FFMPEGDownloader._terminate(self)

    def updateStatistic(self):
        self._updateProgress()
        FFMPEGDownloader.updateStatistic(self)

    def getLocalFileSize(self, update=False):
        size = FFMPEGDownloader.getLocalFileSize(self, update)
        return max(size, self.loadedBytes) if self.phase == 'mux' else size

    def getDownloadedFileDuration(self):
        # while ffmpeg puts the parts together everything is loaded
        if self.phase == 'mux':
            return self.totalDuration
        return self.downloadDuration
