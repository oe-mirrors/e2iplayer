# -*- coding: utf-8 -*-
# add 071026: HLS download through curl-impersonate, started by iptvdm/impersonatehlsdownloader.py.
#
# Some CDNs (vidzy.cc: hosts cpasmieux, movix, ...) answer HTTP 403 to every OpenSSL TLS client - urllib,
# pycurl, hlsdl and the players' ffmpeg - for the playlists AND every segment. curl-impersonate (a browser's
# TLS/HTTP2 fingerprint) gets them. So E2iPlayer downloads the segments itself into the buffering / download
# file and the player plays that growing MPEG-TS file, like with hlsdl buffering.
#
# Steps: the playlist with libs/curlimpersonate.fetch() (a master -> its variant with the highest
# BANDWIDTH), then ALL segments with ONE curl-impersonate run (-K config of url/output pairs, the
# connection is reused). Each finished segment (-w line on curl's stderr) is appended to the output file
# in playlist order; a failed one is retried by a new curl run that starts at that segment.
# A live playlist (no EXT-X-ENDLIST) is reloaded every half target duration and its new segments are
# appended until the helper is terminated (start: --live-start seconds behind the live edge).
# Segments with a fake image header in front of the MPEG-TS data (timstreams/grandemx: a WEBP on an image
# CDN, box log 07.10. #4) are cut at the first TS packet - hlsdl and the players' ffmpeg cannot do that.
#
# Status lines on stderr, one JSON object per line (the same keys hlsdl uses):
#   {"d_t": "vod", "t_d": <total seconds>, "segs": <count>}            after the playlist was read
#   {"d_t": "live"}                                                    instead, for a live playlist
#   {"d_s": <bytes>, "d_d": <seconds done>, "t_d": ..., "seg": i, "segs": n}  after every segment
#   {"error_code": <exit code>, "error_msg": "..."}                    before a non-zero exit
# Exit codes: 0 done, 1 internal error, 2 usage, 3 curl-impersonate missing/unusable, 4 playlist
# request failed or live playlist stopped, 5 stream not supported (encrypted, fMP4, byte ranges, not MPEG-TS),
# 6 segment download failed, 130 terminated.
#
# Python 2.7 and 3 compatible, no enigma2 imports.
from __future__ import print_function

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

try:
    from urllib.parse import urljoin
except ImportError:  # Python 2
    from urlparse import urljoin

# libs/curlimpersonate.py: binary lookup, browser profiles (with the fallback for an older binary),
# header filter and the playlist request. Appended (not inserted) so the stdlib always wins over libs/*.
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'libs'))
import curlimpersonate  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_BINARY = 3
EXIT_PLAYLIST = 4
EXIT_UNSUPPORTED = 5
EXIT_SEGMENT = 6
EXIT_TERMINATED = 130

SEG_MARKER = '@@E2I-SEG@@'
SEG_WRITEOUT = '%{stderr}' + SEG_MARKER + ' %{http_code} %{size_download} %{filename_effective}\n'
SEG_TRIES = 4  # curl runs that may start at the same segment
TS_PACKET = 188
LIVE_MIN_SEGMENTS = 3  # a live stream starts at least this many segments behind the edge
LIVE_IDLE_RELOADS = 12  # reloads without a new segment before a live stream counts as ended


class HelperError(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, msg)
        self.code = code
        self.msg = msg


class Terminated(Exception):
    pass


def _write(line):
    try:
        sys.stderr.write(line)
        sys.stderr.flush()
    except (IOError, OSError, ValueError):
        # nobody reads the status any more (E2iPlayer / enigma2 gone): stop instead of downloading on
        raise Terminated()


def status(obj):
    _write(json.dumps(obj) + '\n')


def log(msg):
    _write('impersonatehls: %s\n' % msg)


def _text(data):
    if isinstance(data, bytes):
        return data.decode('utf-8', 'replace')
    return data


def parseArgs(argv):
    opts = {'binary': '', 'tmp': '', 'headers': {}, 'out': '', 'url': '', 'insecure': False, 'max_segments': 0,
            'timeout': 30, 'live_start': 0}
    i = 0
    rest = []
    while i < len(argv):
        arg = argv[i]
        if arg in ('--binary', '--tmp', '-H', '-o', '--max-segments', '--timeout', '--live-start'):
            if i + 1 >= len(argv):
                raise HelperError(EXIT_USAGE, 'option %s needs a value' % arg)
            value = argv[i + 1]
            i += 2
            if arg == '--binary':
                opts['binary'] = value
            elif arg == '--tmp':
                opts['tmp'] = value
            elif arg == '-o':
                opts['out'] = value
            elif arg == '--max-segments':
                opts['max_segments'] = int(value)
            elif arg == '--timeout':
                opts['timeout'] = int(value)
            elif arg == '--live-start':
                opts['live_start'] = int(value)
            elif ':' in value:
                name, val = value.split(':', 1)
                opts['headers'][name.strip()] = val.strip()
            continue
        if arg in ('-k', '--insecure'):
            opts['insecure'] = True
        else:
            rest.append(arg)
        i += 1
    if len(rest) != 1 or not opts['out']:
        raise HelperError(EXIT_USAGE, 'usage: impersonatehls.py [--binary B] [--tmp DIR] [-H "Name: value"]... [-k] '
                                      '[--max-segments N] [--live-start SECONDS] -o OUTPUT URL')
    opts['url'] = rest[0]
    return opts


def fetchText(opts, url):
    """playlist through curl-impersonate -> (text, final url, profile)"""
    try:
        res = curlimpersonate.fetch(opts['binary'], url, opts['tmp'], headers=opts['headers'], timeout=opts['timeout'],
                                    insecure=opts['insecure'])
    except curlimpersonate.ImpersonateUnavailable as e:
        raise HelperError(EXIT_BINARY, 'curl-impersonate cannot run: %s' % e)
    if res['exitcode'] != 0 or not res['status']:
        raise HelperError(EXIT_PLAYLIST, 'playlist request failed: curl exit %s %s' % (res['exitcode'], res['error']))
    if res['status'] != 200:
        raise HelperError(EXIT_PLAYLIST, 'playlist request failed: HTTP %s' % res['status'])
    return _text(res['body']), res['url'] or url, res['profile']


def _attr(line, name):
    match = re.search(r'(?:^|[:,])' + name + r'=("[^"]*"|[^,]*)', line)
    if not match:
        return ''
    return match.group(1).strip('"')


def pickVariant(text, baseUrl):
    """master playlist -> url of the variant with the highest BANDWIDTH ('' when it is a media playlist)"""
    best = None
    lines = [line.strip() for line in text.splitlines()]
    for idx, line in enumerate(lines):
        if not line.startswith('#EXT-X-STREAM-INF:'):
            continue
        uri = ''
        for nxt in lines[idx + 1:]:
            if nxt and not nxt.startswith('#'):
                uri = nxt
                break
            if nxt.startswith('#EXT-X-STREAM-INF:'):
                break
        if not uri:
            continue
        try:
            bandwidth = int(_attr(line, 'BANDWIDTH') or 0)
        except ValueError:
            bandwidth = 0
        if best is None or bandwidth > best[0]:
            best = (bandwidth, urljoin(baseUrl, uri))
    return best[1] if best else ''


def parseMediaPlaylist(text, baseUrl, allowLive=False):
    """media playlist -> list of (absolute url, seconds); refuses what this helper cannot do"""
    if '#EXTM3U' not in text:
        raise HelperError(EXIT_PLAYLIST, 'the answer is not an HLS playlist')
    segments = []
    duration = 0.0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#EXTINF:'):
            try:
                duration = float(line[8:].split(',', 1)[0].strip())
            except ValueError:
                duration = 0.0
        elif line.startswith('#EXT-X-KEY:'):
            method = _attr(line, 'METHOD').upper()
            if method and method != 'NONE':
                raise HelperError(EXIT_UNSUPPORTED, 'encrypted HLS (%s) is not supported' % method)
        elif line.startswith('#EXT-X-MAP:'):
            raise HelperError(EXIT_UNSUPPORTED, 'fMP4 HLS (EXT-X-MAP) is not supported')
        elif line.startswith('#EXT-X-BYTERANGE:'):
            raise HelperError(EXIT_UNSUPPORTED, 'HLS byte ranges are not supported')
        elif not line.startswith('#'):
            segments.append((urljoin(baseUrl, line), duration))
            duration = 0.0
    if not allowLive and '#EXT-X-ENDLIST' not in text:
        raise HelperError(EXIT_UNSUPPORTED, 'live HLS (no EXT-X-ENDLIST) is not supported')
    if not segments:
        raise HelperError(EXIT_PLAYLIST, 'the playlist has no segments')
    return segments


def playlistInfo(text):
    """media playlist -> (media sequence of its first segment, target duration, has EXT-X-ENDLIST)"""
    sequence = re.search(r'#EXT-X-MEDIA-SEQUENCE:\s*(\d+)', text)
    target = re.search(r'#EXT-X-TARGETDURATION:\s*([\d.]+)', text)
    return (int(sequence.group(1)) if sequence else 0, float(target.group(1)) if target else 6.0,
            '#EXT-X-ENDLIST' in text)


def liveStartIndex(segments, seconds):
    """first segment to fetch: `seconds` behind the live edge, at least LIVE_MIN_SEGMENTS"""
    first = max(0, len(segments) - LIVE_MIN_SEGMENTS)
    behind = sum(d for _, d in segments[first:])
    while first > 0 and behind < seconds:
        first -= 1
        behind += segments[first][1]
    return first


def _configQuote(value):
    # curl -K: a quoted value knows the escapes \\ \" \t \n \r \v
    return '"%s"' % value.replace('\\', '\\\\').replace('"', '\\"')


def tsStart(head):
    """offset of the first MPEG-TS packet (three sync bytes 188 apart) - some CDNs put a fake image header
    in front of the segments. -1 when there is none"""
    for offset in range(0, max(0, len(head) - 2 * TS_PACKET)):
        if head[offset:offset + 1] == b'\x47' and head[offset + TS_PACKET:offset + TS_PACKET + 1] == b'\x47' and \
           head[offset + 2 * TS_PACKET:offset + 2 * TS_PACKET + 1] == b'\x47':
            return offset
    return -1


class Downloader(object):
    def __init__(self, opts, segments, profile, live=False):
        self.opts = opts
        self.segments = segments
        self.profile = profile
        self.live = live
        self.partsDir = opts['out'] + '.parts'
        self.total = sum(d for _, d in segments)
        self.done = 0  # segments appended to the output
        self.bytes = 0
        self.seconds = 0.0
        self.proc = None
        self.out = None

    def _partPath(self, idx):
        return os.path.join(self.partsDir, 'seg%06d.ts' % idx)

    def _writeConfig(self, start):
        path = os.path.join(self.partsDir, 'segments.cfg')
        with open(path, 'wb') as f:
            for idx in range(start, len(self.segments)):
                f.write(('url = %s\noutput = %s\n' % (_configQuote(self.segments[idx][0]), _configQuote(self._partPath(idx)))).encode('utf-8'))
        return path

    def _curlArgs(self, cfgPath):
        timeout = str(self.opts['timeout'])
        # -f: an HTTP error saves nothing / --fail-early: stop at the first failed segment, the run is restarted
        # there. --retry: connection errors, timeouts, 5xx (the part file is truncated by curl itself)
        args = [self.opts['binary'], '--impersonate', self.profile, '-s', '-S', '-f', '--fail-early', '-L',
                '--max-redirs', '10', '--connect-timeout', timeout, '--speed-time', timeout, '--speed-limit', '1000',
                '--retry', '3', '--retry-delay', '1', '-w', SEG_WRITEOUT]
        if self.opts['insecure']:
            args.append('-k')
        elif os.path.isfile(curlimpersonate.CA_BUNDLE):
            args.extend(['--cacert', curlimpersonate.CA_BUNDLE])
        for line in curlimpersonate.filterHeaders(self.opts['headers']):
            args.extend(['-H', line])
        args.extend(['-K', cfgPath])
        return args

    def _append(self, idx):
        """segment file -> end of the output file; False when it is no MPEG-TS"""
        path = self._partPath(idx)
        with open(path, 'rb') as f:
            head = f.read(65536)
            offset = 0 if head[:1] == b'\x47' else tsStart(head)
            if offset < 0:
                return False
            self.out.write(head[offset:])
            size = len(head) - offset
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.out.write(chunk)
                size += len(chunk)
        self.out.flush()
        os.remove(path)
        self.bytes += size
        self.seconds += self.segments[idx][1]
        self.done = idx + 1
        self._report()
        return True

    def _report(self):
        status({'d_s': self.bytes, 'd_d': round(self.seconds, 3), 't_d': round(self.total, 3), 'seg': self.done,
                'segs': len(self.segments)})

    def addSegments(self, segments):
        self.segments.extend(segments)
        self.total += sum(d for _, d in segments)

    def _skip(self, idx, why):
        # live: a segment that cannot be fetched is left out (it slid out of the window), the stream goes on
        log('segment %d skipped: %s' % (idx + 1, why))
        try:
            os.remove(self._partPath(idx))
        except OSError:
            pass
        self.total -= self.segments[idx][1]
        self.done = idx + 1

    def _segIndex(self, filename):
        match = re.search(r'seg(\d+)\.ts$', filename)
        return int(match.group(1)) if match else -1

    def _kill(self):
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.kill()
            except OSError:
                pass

    def _flush(self, finished, closedBefore):
        """append the finished segments in order. Segments before closedBefore are closed for sure (curl works
        sequentially and moved on, or it exited)"""
        while self.done in finished:
            idx = self.done
            size = finished[idx][1]
            path = self._partPath(idx)
            if idx >= closedBefore:
                # curl may print -w before it closed the file: wait for all bytes (an encoded body is
                # taken when the next segment's line arrives)
                try:
                    if os.path.getsize(path) < size:
                        return
                except OSError:
                    return
            del finished[idx]
            if not self._append(idx):
                raise HelperError(EXIT_UNSUPPORTED, 'segment %d is not MPEG-TS' % (idx + 1))

    def _runOnce(self, start):
        cfgPath = self._writeConfig(start)
        args = self._curlArgs(cfgPath)
        devnull = open(os.devnull, 'r+b')
        try:
            self.proc = subprocess.Popen(args, stdin=devnull, stdout=devnull, stderr=subprocess.PIPE,
                                         close_fds=(os.name != 'nt'))
        except OSError as e:
            devnull.close()
            raise HelperError(EXIT_BINARY, 'curl-impersonate cannot run: %s' % e)
        finished = {}
        failed = None
        lastError = ''
        try:
            while True:
                line = self.proc.stderr.readline()
                if not line:
                    break
                line = _text(line).rstrip('\r\n')
                if not line.startswith(SEG_MARKER):
                    if line.strip():
                        lastError = line.strip()
                        log('curl: %s' % lastError)
                    continue
                parts = line[len(SEG_MARKER):].strip().split(' ', 2)
                try:
                    httpCode, size = int(parts[0]), int(parts[1])
                except (IndexError, ValueError):
                    continue
                idx = self._segIndex(parts[2] if len(parts) > 2 else '')
                if idx < 0:
                    continue
                if httpCode != 200 or not os.path.isfile(self._partPath(idx)):
                    failed = (idx, httpCode)
                    log('segment %d failed: HTTP %s %s' % (idx + 1, httpCode, lastError))
                    self._kill()
                    break
                finished[idx] = (httpCode, size)
                self._flush(finished, idx)
        except BaseException:
            self._kill()  # no curl left running (terminated, write error, ...)
            raise
        finally:
            code = self.proc.wait()
            self.proc.stderr.close()
            self.proc = None
            devnull.close()
        # curl exited: every file it wrote is closed (a failed segment is not in finished)
        self._flush(finished, len(self.segments))
        return code, failed, lastError

    def open(self):
        if os.path.isdir(self.partsDir):
            shutil.rmtree(self.partsDir, True)
        os.makedirs(self.partsDir)
        self.out = open(self.opts['out'], 'wb')

    def close(self):
        if self.out is not None:
            self.out.close()
            self.out = None
        shutil.rmtree(self.partsDir, True)

    def download(self):
        """fetch and append every segment not done yet"""
        tries = 0
        lastStart = -1
        while self.done < len(self.segments):
            start = self.done
            tries = tries + 1 if start == lastStart else 1
            if tries > SEG_TRIES:
                if self.live:
                    self._skip(start, 'failed %d times' % SEG_TRIES)
                    continue
                raise HelperError(EXIT_SEGMENT, 'segment %d failed %d times' % (start + 1, SEG_TRIES))
            lastStart = start
            code, failed, lastError = self._runOnce(start)
            if self.done >= len(self.segments):
                break
            log('curl run ended at segment %d/%d (exit %s, failed %r) %s' % (self.done + 1, len(self.segments), code, failed, lastError))
            if failed is not None and failed[1] in (401, 403, 404, 410) and tries >= 2:
                if self.live:
                    self._skip(failed[0], 'HTTP %s' % failed[1])
                    continue
                raise HelperError(EXIT_SEGMENT, 'segment %d: HTTP %s' % (failed[0] + 1, failed[1]))
            time.sleep(min(2 * tries, 6))

    def run(self):
        self.open()
        try:
            self.download()
        finally:
            self.close()


def runLive(opts, text, playlistUrl, finalUrl, profile):
    """reload the live playlist and append its new segments until terminated or the stream ends"""
    status({'d_t': 'live', 'profile': profile})
    downloader = Downloader(opts, [], profile, live=True)
    downloader.open()
    try:
        segments = parseMediaPlaylist(text, finalUrl, allowLive=True)
        nextSequence = None
        lastPath = None
        idle = 0
        while True:
            sequence, target, ended = playlistInfo(text)
            paths = [url.split('?', 1)[0] for url, _ in segments]
            if nextSequence is None:
                first = liveStartIndex(segments, opts['live_start'])
            elif '#EXT-X-MEDIA-SEQUENCE' not in text:
                # no media sequence (every window "starts at 0"): go on after the last segment taken, by its path
                # (the query may carry a changing token)
                first = len(paths) - paths[::-1].index(lastPath) if lastPath in paths else 0
            elif sequence <= nextSequence <= sequence + len(segments):
                first = nextSequence - sequence
            else:
                # a gap (reloads too slow) or a restarted sequence: the whole window
                log('live sequence jump: expected %d, playlist %d-%d' % (nextSequence, sequence, sequence + len(segments) - 1))
                first = 0
            new = segments[first:]
            nextSequence = sequence + len(segments)
            lastPath = paths[-1]
            if new:
                idle = 0
                downloader.addSegments(new)
                downloader.download()
            else:
                idle += 1
            if ended:
                return
            if idle > LIVE_IDLE_RELOADS:
                raise HelperError(EXIT_PLAYLIST, 'the live playlist got no new segment for %d reloads' % idle)
            time.sleep(max(1.0, target / 2.0))
            try:
                newText, newFinalUrl, profile = fetchText(opts, playlistUrl)
                segments = parseMediaPlaylist(newText, newFinalUrl, allowLive=True)
                text, finalUrl = newText, newFinalUrl
            except HelperError as e:
                if e.code != EXIT_PLAYLIST:
                    raise
                # a failed reload (timeout, 5xx, an error page) counts like one without a new segment: the
                # previous playlist is used again and gives nothing new
                log('live playlist reload failed: %s' % e.msg)
    finally:
        downloader._kill()
        downloader.close()


def _onSignal(signum, frame):
    # Stop sends SIGINT (sendCtrlC) and SIGTERM (terminateToolsOfFile): only the first one may interrupt, a
    # second one would break off the cleanup (curl kill/wait, removing the .parts folder) half way
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    raise Terminated()


def main(argv):
    signal.signal(signal.SIGTERM, _onSignal)
    signal.signal(signal.SIGINT, _onSignal)
    downloader = None
    try:
        opts = parseArgs(argv)
        if not opts['binary']:
            opts['binary'] = curlimpersonate.getImpersonateBinary()
        if not opts['binary'] or not os.path.isfile(opts['binary']):
            raise HelperError(EXIT_BINARY, 'curl-impersonate is not installed (%s)' % ', '.join(curlimpersonate.BINARY_CANDIDATES))
        if not opts['tmp']:
            opts['tmp'] = os.path.dirname(os.path.abspath(opts['out']))
        playlistUrl = opts['url']
        text, finalUrl, profile = fetchText(opts, playlistUrl)
        if '#EXT-X-STREAM-INF:' in text:
            playlistUrl = pickVariant(text, finalUrl)
            if not playlistUrl:
                raise HelperError(EXIT_PLAYLIST, 'master playlist without variants')
            log('variant %s' % playlistUrl.split('?', 1)[0])
            text, finalUrl, profile = fetchText(opts, playlistUrl)
        if '#EXTM3U' in text and '#EXT-X-ENDLIST' not in text:
            runLive(opts, text, playlistUrl, finalUrl, profile)
            return EXIT_OK
        segments = parseMediaPlaylist(text, finalUrl)
        if opts['max_segments'] > 0:
            segments = segments[:opts['max_segments']]
        status({'d_t': 'vod', 't_d': round(sum(d for _, d in segments), 3), 'segs': len(segments), 'profile': profile})
        downloader = Downloader(opts, segments, profile)
        downloader.run()
        return EXIT_OK
    except HelperError as e:
        result = (e.code, e.msg)
    except Terminated:
        result = (EXIT_TERMINATED, 'terminated')
    except Exception as e:
        result = (EXIT_INTERNAL, '%s: %s' % (e.__class__.__name__, e))
    if downloader is not None:
        downloader._kill()
    try:
        status({'error_code': result[0], 'error_msg': result[1]})
    except Terminated:
        pass
    return result[0]


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
