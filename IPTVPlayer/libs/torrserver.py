# -*- coding: utf-8 -*-
#
# Torrent playback through a local TorrServer (https://github.com/YouROK/TorrServer, MatriX API).
# TorrServer itself is NOT shipped or downloaded by E2iPlayer - the user installs the binary
# for the box architecture; we only find it, start it on demand (bound to 127.0.0.1 when the
# binary supports it, unless its web interface is opened to the home network), push the
# settings of the torrent configuration and turn a magnet / .torrent link into the per-file
# HTTP stream urls TorrServer serves.
#
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

from Components.config import config
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetCacheSubDir, GetTmpDir, IsRealStoragePresent, Which, mkdirs, printDBG, printExc

BINARY_NAMES = ('TorrServer', 'torrserver')
# besides $PATH: where the TorrServer images/plugins of the Enigma2 world usually put it
BINARY_DIRS = ('/usr/bin', '/usr/local/bin', '/usr/sbin', '/opt/bin', '/media/hdd/TorrServer', '/media/usb/TorrServer')

VIDEO_EXTS = ('mkv', 'mp4', 'avi', 'ts', 'm2ts', 'mts', 'm4v', 'mov', 'webm', 'wmv', 'mpg', 'mpeg', 'vob', 'flv', '3gp', 'divx', 'ogm')
AUDIO_EXTS = ('mp3', 'flac', 'm4a', 'aac', 'ogg', 'opus', 'wav', 'wma', 'ac3', 'dts')
SUB_EXTS = ('srt', 'ass', 'ssa', 'vtt', 'sub', 'smi')

# torrent metadata (file list) can take a while when there are few peers; TorrServer itself gives up
# after 1 min + TorrentDisconnectTimeout and drops a torrent nobody reads from after that timeout
# (default 30 s), so torrents we only added for their file list do not pile up in its RAM
METADATA_TIMEOUT = 60
START_TIMEOUT = 10
HELP_TIMEOUT = 5

STOP_TIMEOUT = 5
DISK_CACHE_SUBDIR = 'TorrServer'

# (pid, started for the home network, port, data folder) of the server we started - also kept in the pid file
_own = None
# the settings last sent to our server: a change in the torrent configuration is sent with the next link
_appliedKey = None
# parsers run in worker threads: only one of them may start the server
_startLock = threading.Lock()
_SAMPLE_RE = re.compile(r'(?:^|[/._ -])sample(?:[/._ -]|$)', re.I)
_DIGITS_RE = re.compile(r'(\d+)')


def isTorrentLink(url):
    url = url or ''
    if url.startswith('magnet:?'):
        return True
    path = url.split('?', 1)[0].split('#', 1)[0].lower()
    return url.startswith(('http://', 'https://')) and path.endswith('.torrent')


def _pidFile():
    return GetTmpDir('.torrserver.pid')


def getPort():
    return int(config.plugins.iptvplayer.torrserver_port.value)


def getBaseUrl():
    return 'http://127.0.0.1:%d' % getPort()


def _isExe(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _isTorrServerName(path):
    # also the names of the release files (TorrServer-linux-arm7, ...); nothing else is ever run,
    # whatever the path option (which the web interface can change too) points to
    return os.path.basename(path).lower().startswith('torrserver')


def findBinary():
    # the configured file or folder, else $PATH and the usual folders
    path = config.plugins.iptvplayer.torrserver_path.value.strip()
    if path and not os.path.isdir(path):
        return path if _isExe(path) and _isTorrServerName(path) else ''
    dirs = (path,) if path else BINARY_DIRS
    if not path:
        for name in BINARY_NAMES:
            exe = Which(name)
            if exe:
                return exe
    for d in dirs:
        for name in BINARY_NAMES:
            if _isExe(os.path.join(d, name)):
                return os.path.join(d, name)
        try:
            names = sorted(os.listdir(d))
        except Exception:
            continue
        for name in names:
            if _isTorrServerName(name) and _isExe(os.path.join(d, name)):
                return os.path.join(d, name)
    return ''


RELEASES_URL = 'https://github.com/YouROK/TorrServer/releases'


def releaseFileName():
    """the TorrServer release file for this receiver's CPU ('' when unknown)"""
    try:
        machine = os.uname()[4].lower()
    except Exception:
        return ''
    if machine.startswith(('armv7', 'armv8l')):
        arch = 'arm7'
    elif machine.startswith(('aarch64', 'arm64')):
        arch = 'arm64'
    elif machine.startswith(('armv5', 'armv6')):
        arch = 'arm5'
    elif machine.startswith('mips'):
        # the receivers' MIPS CPUs run little endian (mipsel)
        arch = ('mips64' if '64' in machine else 'mips') + ('le' if sys.byteorder == 'little' else '')
    elif machine in ('x86_64', 'amd64'):
        arch = 'amd64'
    elif machine in ('i386', 'i486', 'i586', 'i686'):
        arch = '386'
    else:
        return ''
    return 'TorrServer-linux-' + arch


def installHint():
    """what to do when no TorrServer binary is found - it is in no image feed, the user downloads it"""
    fileName = releaseFileName()
    if fileName:
        step1 = _('Download "%s" (for this receiver) from %s') % (fileName, RELEASES_URL)
    else:
        step1 = _('Download the Linux file for the CPU of this receiver from %s') % RELEASES_URL
    return '\n'.join((
        _('TorrServer was not found on the receiver. It is not part of E2iPlayer and not in the image feeds - install it yourself:'),
        '1. ' + step1,
        '2. ' + _('Copy it to /usr/bin/TorrServer (or a folder on HDD/USB) and make it executable (chmod 755).'),
        '3. ' + _('Not in /usr/bin: choose the file under "TorrServer binary" in the torrent configuration.'),
    ))


def naturalKey(text):
    # "Episode 2" before "Episode 10"
    return [int(part) if part.isdigit() else part for part in _DIGITS_RE.split((text or '').lower())]


def isSample(path):
    return _SAMPLE_RE.search(path or '') is not None


class TorrServer:

    def __init__(self):
        self.cm = common()
        self.baseUrl = getBaseUrl()
        self.defaultParams = {'header': {'User-Agent': 'E2iPlayer', 'Accept': 'application/json, */*'}, 'timeout': 10}

    def _get(self, path, timeout=10):
        params = dict(self.defaultParams)
        params['timeout'] = timeout
        return self.cm.getPage(self.baseUrl + path, params)

    def _post(self, path, data, timeout=10):
        params = dict(self.defaultParams)
        params['timeout'] = timeout
        params['raw_post_data'] = True
        params['header'] = dict(params['header'], **{'Content-Type': 'application/json'})
        return self.cm.getPage(self.baseUrl + path, params, json_dumps(data))

    def version(self):
        # '' when nothing answers on the port
        # fix 091026: a closed port is checked with a plain socket first - while TorrServer starts, every refused
        # HTTP request wrote a full traceback into the debug log (box log of MOHAMED_OS, #144)
        if not _portOpen(getPort()):
            return ''
        sts, data = self._get('/echo', timeout=3)
        if sts and data.strip().startswith(('MatriX', '1.', '2.')):
            return data.strip()
        return ''

    def isRunning(self):
        return self.version() != ''

    def start(self):
        """returns '' on success, 'binary' when no TorrServer binary was found, else an error text"""
        with _startLock:
            # one thread at a time: another one may have started or restarted it while this one waited
            own = _readPidFile()
            if own is not None and own[2] is not None and own[2] != getPort():
                # fix 091026: the port was changed - our server on the old port would stay orphaned and keep the
                # database in the data folder locked for the new one
                printDBG('TorrServer restart: port %d -> %d' % (own[2], getPort()))
                if not _stopOwnAndWait(own):
                    return 'old TorrServer did not stop'
            if self.isRunning():
                return self._keepCurrent()
            return self._start()

    def _keepCurrent(self):
        # our server follows the torrent configuration: the home-network switch needs a new start
        # (it is a command line option), the rest is sent as settings when it changed
        own = _readPidFile()
        if own is None:
            return ''  # a TorrServer the user runs himself keeps his own settings
        if own[1] != config.plugins.iptvplayer.torrserver_lan.value:
            printDBG('TorrServer restart: web interface in the home network %s' % config.plugins.iptvplayer.torrserver_lan.value)
            if not _stopOwnAndWait(own) or self.isRunning():
                return 'old TorrServer did not stop'
            return self._start()
        if _appliedKey != _settingsKey():
            self.applySettings()
        return ''

    def _start(self):
        global _own
        exe = findBinary()
        if not exe:
            return 'binary'
        port, dataDir = getPort(), _dataDir()
        args = [exe, '--port', str(port), '--path', dataDir]
        lan = config.plugins.iptvplayer.torrserver_lan.value
        if not lan and self._supportsOption(exe, '--ip'):
            args.extend(['--ip', '127.0.0.1'])
        env = dict(os.environ)
        # hand freed memory back to the box at once (default only since Go 1.16)
        env['GODEBUG'] = 'madvdontneed=1'
        # own session: the server keeps running when enigma2 restarts and gets no signals meant for
        # enigma2's process group. preexec_fn is not safe in a threaded process, so py3 gets
        # start_new_session; py2 has nothing else
        if sys.version_info[0] >= 3:
            sessionArgs = {'start_new_session': True}
        else:
            sessionArgs = {'preexec_fn': os.setsid}
        printDBG('TorrServer.start %r' % args)
        try:
            with open(os.devnull, 'rb') as devIn, open(os.devnull, 'wb') as devOut:
                proc = subprocess.Popen(args, stdin=devIn, stdout=devOut, stderr=devOut, close_fds=True, env=env, **sessionArgs)
        except Exception as e:
            printExc()
            return str(e)
        _own = (proc.pid, bool(lan), port, dataDir)
        try:
            # pid, started for the home network, port, data folder (survive an enigma2 restart like the pid)
            with open(_pidFile(), 'w') as f:
                f.write('%d\n%d\n%d\n%s\n' % (proc.pid, 1 if lan else 0, port, ensure_str(dataDir)))
        except Exception:
            printExc()
        deadline = time.time() + START_TIMEOUT
        while time.time() < deadline:
            if proc.poll() is not None:
                _own = None
                _removePidFile()
                return 'exit %s' % proc.returncode
            if self.isRunning():
                self.applySettings()
                return ''
            time.sleep(0.3)
        # still starting (slow box, big database): left running, the next link finds it
        return 'timeout'

    @staticmethod
    def _supportsOption(exe, option):
        # "--help" prints the options and exits; killed after HELP_TIMEOUT should a build ignore it
        try:
            proc = subprocess.Popen([exe, '--help'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
        except Exception:
            printExc()
            return False
        timer = threading.Timer(HELP_TIMEOUT, _kill, (proc,))
        timer.start()
        try:
            out = proc.communicate()[0]
        except Exception:
            printExc()
            out = b''
        finally:
            timer.cancel()
        # "[--ip IP]" / "--ip IP, -i IP" - not a longer option that merely starts the same
        return re.search(br'(?:^|[\s,\[(])' + re.escape(option.encode('ascii')) + br'(?:[\s=,\])]|$)', out or b'') is not None

    def applySettings(self):
        # TorrServer replaces its whole settings object on "set", so the current one is read
        # first and only our keys are changed
        global _appliedKey
        try:
            sts, data = self._post('/settings', {'action': 'get'})
            if not sts:
                return False
            sets = json_loads(data)
            if not isinstance(sets, dict):
                return False
            wanted = desiredSettings()
            sets.update(wanted)
            if not self._post('/settings', {'action': 'set', 'sets': sets})[0]:
                return False
            _appliedKey = _settingsKey(wanted)
            printDBG('TorrServer settings %r' % wanted)
            return True
        except Exception:
            printExc()
        return False

    def getFiles(self, link, title='', poster=''):
        """add the torrent (not stored in TorrServer's database) and wait for its file list.
        Returns (hash, [{'id', 'path', 'length'}]) or ('', [])"""
        # fix 091026: ensure_str - py2 urllib.quote fails on non-ASCII unicode (Arabic / French titles)
        path = '/stream?link=%s&stat' % urllib_quote(ensure_str(link), safe='')
        if title:
            path += '&title=%s' % urllib_quote(ensure_str(title), safe='')
        if poster:
            path += '&poster=%s' % urllib_quote(ensure_str(poster), safe='')
        sts, data = self._get(path, timeout=METADATA_TIMEOUT)
        if not sts or not data.strip().startswith('{'):
            return '', []
        try:
            data = json_loads(data)
            return data.get('hash', ''), data.get('file_stats') or []
        except Exception:
            printExc()
        return '', []

    def streamUrl(self, infoHash, fileItem):
        name = ensure_str(fileItem.get('path', '')).split('/')[-1] or 'file'
        return '%s/stream/%s?link=%s&index=%s&play' % (self.baseUrl, urllib_quote(name, safe=''), infoHash, fileItem.get('id', 1))


def _dataDir():
    return GetCacheSubDir('TorrServer')


def diskCacheDir():
    """<folder>/TorrServer when the cache is set to a folder on a mounted HDD / USB stick, else ''.
    A subfolder of its own: TorrServer walks the whole TorrentsSavePath for an old ".tsc" folder"""
    cp = config.plugins.iptvplayer
    if cp.torrserver_cache_location.value != 'disk':
        return ''
    base = (cp.torrserver_cache_dir.value or '').strip()
    if not base or not IsRealStoragePresent(base):
        printDBG('TorrServer: no storage under the cache folder [%s] - cache stays in RAM' % base)
        return ''
    path = os.path.join(base, DISK_CACHE_SUBDIR)
    if not os.path.isdir(path):
        mkdirs(path)
    return path if os.path.isdir(path) else ''


def desiredSettings():
    # the TorrServer settings (BTSets) of the torrent configuration; rates in KB/s
    cp = config.plugins.iptvplayer
    diskDir = diskCacheDir()
    if diskDir:
        cacheSize = int(cp.torrserver_disk_cache.value)
    else:
        cacheSize = int(cp.torrserver_cache.value)
    upload = cp.torrserver_upload.value
    return {
        'CacheSize': cacheSize * 1024 * 1024,
        'UseDisk': bool(diskDir),
        'TorrentsSavePath': diskDir,
        'RemoveCacheOnDrop': bool(diskDir) and cp.torrserver_remove_cache.value,
        'PreloadCache': int(cp.torrserver_preload.value),
        'ReaderReadAHead': int(cp.torrserver_readahead.value),
        'ConnectionsLimit': int(cp.torrserver_connections.value),
        'DownloadRateLimit': int(cp.torrserver_dl_limit.value),
        'DisableUpload': not upload,
        'UploadRateLimit': int(cp.torrserver_ul_limit.value) if upload else 0,
        'ForceEncrypt': cp.torrserver_encrypt.value,
        'TorrentDisconnectTimeout': int(cp.torrserver_timeout.value),
        'EnableDLNA': cp.torrserver_dlna.value,
    }


def _settingsKey(wanted=None):
    return repr(sorted((wanted if wanted is not None else desiredSettings()).items()))


def _readPidFile():
    """(pid, started for the home network, port, data folder) of the TorrServer we started, None for none / another
    one; port and data folder are None in a pid file of an older version (two lines)"""
    try:
        with open(_pidFile()) as f:
            lines = f.read().splitlines()
        own = (int(lines[0]), len(lines) > 1 and lines[1] == '1', int(lines[2]) if len(lines) > 2 else None, lines[3] if len(lines) > 3 else None)
    except Exception:
        own = _own
        if own is None:
            return None
    if not _isOwnProcess(own[0], own[3]):
        return None
    return own


def applyConfigInBackground():
    """the torrent configuration was saved (receiver or web interface): our TorrServer follows at once instead of with
    the next torrent link - with the web interface for the home network on it is started, so http://<receiver>:<port>
    answers without playing a torrent first (box test 08.10.). A TorrServer the user runs himself is left alone."""
    cp = config.plugins.iptvplayer
    if not cp.torrserver_enabled.value:
        # add 091026: torrent playback switched off - our server does not keep running (with the web interface in the
        # home network) until E2iPlayer is closed; only a SIGTERM, no waiting in the GUI thread
        if _readPidFile() is not None:
            stopOwnServer()
        return

    def run():
        try:
            if cp.torrserver_lan.value or _readPidFile() is not None:
                error = TorrServer().start()
                printDBG('TorrServer after saving the settings: %s' % (error or 'ok'))
        except Exception:
            printExc()

    thread = threading.Thread(target=run, name='TorrServerApply')
    thread.daemon = True
    thread.start()


def _portOpen(port, timeout=1.0):
    """something listens on 127.0.0.1:<port>"""
    try:
        sock = socket.create_connection(('127.0.0.1', port), timeout)
    except (socket.error, socket.timeout, OSError):
        return False
    try:
        sock.close()
    except Exception:
        pass
    return True


def _removePidFile():
    try:
        os.remove(_pidFile())
    except Exception:
        pass


def _kill(proc):
    try:
        proc.kill()
    except Exception:
        pass


def _isOwnProcess(pid, dataDir=None):
    # a recycled pid or a TorrServer the user runs himself has another command line: ours is
    # a TorrServer binary started with our data folder (the one in the pid file: the E2iPlayer
    # cache folder may have been moved since). An exited child (zombie) has an empty command line
    try:
        with open('/proc/%d/cmdline' % pid, 'rb') as f:
            cmdline = f.read().split(b'\0')
    except Exception:
        return False  # gone
    try:
        dataDir = ensure_binary(dataDir or _dataDir())
        return _isTorrServerName(ensure_str(cmdline[0])) and dataDir in cmdline
    except Exception:
        printExc()
    return False


def _stopOwnAndWait(own):
    # worker threads only (start lock held): stop our server and wait until it has exited, so the
    # next one gets its port and the database in the data folder
    stopOwnServer()
    deadline = time.time() + STOP_TIMEOUT
    while time.time() < deadline:
        if not _isOwnProcess(own[0], own[3]):
            return True
        time.sleep(0.3)
    return False


def stopOwnServer():
    """stop the TorrServer we started (also one started before an enigma2 restart, via the pid
    file) - never one the user runs on his own"""
    # no _startLock here: this runs in the GUI thread, which must not wait for a start in progress
    global _own, _appliedKey
    own = _readPidFile()
    if own is not None:
        printDBG('TorrServer stop pid %d' % own[0])
        try:
            os.kill(own[0], signal.SIGTERM)
        except Exception:
            printExc()
    _own = None
    _appliedKey = None
    _removePidFile()


def fileExt(path):
    m = re.search(r'\.([A-Za-z0-9]{1,5})$', path or '')
    return m.group(1).lower() if m else ''


def formatSize(size):
    try:
        size = float(size)
    except Exception:
        return ''
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return ('%d %s' if unit == 'B' else '%.1f %s') % (size, unit)
        size /= 1024.0
