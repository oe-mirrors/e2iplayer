# -*- coding: utf-8 -*-
#
#  E2iPlayer info / diagnostics screen.
#
#  Opened from the PlayerSelector BLUE menu -> "Info" and from the main
#  settings INFO key. Three pages, switched with LEFT / RIGHT:
#
#    About   - version, project link, credits (the old MessageBox content)
#    System  - E2iPlayer / Python / image / box / CPU / RAM / clock / IPv6,
#              every external tool and Python module with its version (or
#              what does not work without it), free space of the config,
#              temp, download and buffering folders, the debug-log setting
#    Log     - a live tail of the E2iPlayer debug log (if enabled)
#
#  GREEN  saves the current page to /tmp (sysinfo.txt or debug.txt).
#  YELLOW toggles the live refresh on the Log page.
#  BLUE   clears the debug log (Log page only).
#
#  LogSystemInfoAtStartup() is called from plugin start: it runs the probe
#  once and writes the full snapshot (incl. binary versions) near the top
#  of the debug log, so it is already in any log a user shares for
#  support. The screen reuses that cached result.
#
import os
import re
import sys
import time

from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.config import config
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG, printExc, iptv_system, eConnectCallback, formatBytes, GetImageName,
    GetIPTVPlayerVersion, GetIPTVPlayerComitStamp, GetShortPythonVersion,
    GetConfigDir, GetTmpDir, GetGstIfdSrc,
)
try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetDebugLogPath
except Exception:
    def GetDebugLogPath():
        return ""

SYSINFO_FILE = "/tmp/e2iplayer_sysinfo.txt"
DEBUGCOPY_FILE = "/tmp/e2iplayer_debug.txt"

LOG_TAIL_BYTES = 96 * 1024
LOG_REFRESH_MS = 2000

PAGE_ABOUT, PAGE_SYSTEM, PAGE_LOG = 0, 1, 2
# lambdas: translated when shown, not at import (language change without restart)
PAGE_NAMES = {PAGE_ABOUT: lambda: _("About"), PAGE_SYSTEM: lambda: _("System"), PAGE_LOG: lambda: _("Log")}

# label column of the System page (HD reference pixels): room for "Puffer-Verzeichnis" / "curl-impersonate"
_SPLIT_POSITION = 185

_HEADING_COLOR = 0x0066ccff   # same accent blue IPTVArticleView uses for labels
_TEXT_COLOR = 0x00ffffff

# One shell script that probes every external binary at once, so the
# System page needs a single non-blocking iptv_system() call. It is
# written to a temp file and run as `sh <file>` - otherwise iptv_system
# logs the whole ~1 KB command three times per run into the debug log.
# stdin from /dev/null (exteplayer3/gstplayer read commands from stdin
# and would otherwise block); `timeout` guards the rest if it exists.
# duktape's `duk` has no --version flag, so run a one-line script that
# prints Duktape.version (e.g. 20700 -> shown as 2.7.0). quickjs' `qjs
# --version` prints the bare version (e.g. 0.16.2). The tools the plugin
# runs from a fixed /usr/bin path are probed there, only when present;
# every section ends with the path ("-" = missing). unzip / unrar without
# arguments print their banner (unrar after an empty line), so the first
# non-empty line is taken.
_PROBE_SCRIPT_PATH = "/tmp/.e2i_sysprobe.sh"

# r N TOOL ARGS: runs the tool (stdin /dev/null, output and errors), prints at most
# N lines of it and "@rc <exit code>" - the code tells a tool that crashes or cannot
# be executed (126/127, or killed by a signal) from one that only prints its usage
_PROBE_SCRIPT = (
    'T=""; command -v timeout >/dev/null 2>&1 && T="timeout 4"; '
    'w(){ command -v "$1" 2>/dev/null || echo "-"; }; '
    'p(){ [ -x "$1" ] && echo "$1" || echo "-"; }; '
    'r(){ n=$1; shift; o=$($T "$@" </dev/null 2>&1); c=$?; printf "%s\n" "$o" | head -n $n; echo "@rc $c"; }; '
    'echo "@@hlsdl";       X=/usr/bin/hlsdl;    [ -x $X ] && r 2 $X; p $X; '
    'echo "@@cmdwrap";     X=/usr/bin/cmdwrap;  [ -x $X ] && r 1 $X; p $X; '
    'echo "@@lsdir";       X=/usr/bin/lsdir;    [ -x $X ] && r 1 $X --version; p $X; '
    'echo "@@f4mdump";     X=/usr/bin/f4mdump;  [ -x $X ] && r 1 $X; p $X; '
    'echo "@@ffmpeg";      X=/usr/bin/ffmpeg;   [ -x $X ] && r 1 $X -version; p $X; '
    'echo "@@wget";        X=/usr/bin/wget;     [ -x $X ] && r 1 $X --version; p $X; '
    'echo "@@curl";        X=/usr/bin/curl;     [ -x $X ] && r 1 $X --version; p $X; '
    'echo "@@curlimp";     C=$(w curl-impersonate); [ "$C" = "-" ] && [ -x /usr/local/bin/curl-impersonate ] && C=/usr/local/bin/curl-impersonate; '
    '  [ "$C" != "-" ] && r 1 "$C" --version; echo "$C"; '
    'echo "@@rtmpdump";    X=/usr/bin/rtmpdump; [ -x $X ] && r 5 $X --help; p $X; '
    'echo "@@exteplayer3"; X=/usr/bin/exteplayer3; [ -x $X ] && r 2 $X; p $X; '
    'echo "@@gstplayer";   X=/usr/bin/gstplayer;  [ -x $X ] && r 2 $X; p $X; '
    'echo "@@gstplayer2";  X=/usr/bin/gstplayer2; [ -x $X ] && r 2 $X; p $X; '
    'echo "@@duktape";     X=/usr/bin/duk; D=/tmp/.e2i_dukver.js; '
    '  printf "%s" \'try{var v=Duktape.version;print(Math.floor(v/10000)+"."+(Math.floor(v/100)%100)+"."+(v%100))}catch(e){print("?")}\' > $D; '
    '  [ -x $X ] && r 1 $X $D; rm -f $D; p $X; '
    'echo "@@quickjs";     X=/usr/bin/qjs;      [ -x $X ] && r 1 $X --version; p $X; '
    'echo "@@uchardet";    X=/usr/bin/uchardet; [ -x $X ] && r 5 $X --version; p $X; '
    'echo "@@unzip";       U=$(w unzip); [ "$U" != "-" ] && r 3 unzip; echo "$U"; '
    'echo "@@unrar";       U=$(w unrar); [ "$U" != "-" ] && r 3 unrar; echo "$U"; '
    'echo "@@deps";        (opkg list-installed 2>/dev/null | grep -i e2iplayer-deps || true); '
    'echo "@@ifdsrc";      (opkg list-installed 2>/dev/null | grep "^gst-ifdsrc " || true); '
    'echo "@@end"\n'
)

_PROBE_CACHE = None       # parsed binary block, reused for the whole session
_PROBE_KEEPALIVE = None   # holds the iptv_system object until its callback fires
_STARTUP_KEEPALIVE = None
_SNAPSHOT_LOGGED = False   # the full snapshot is already in the current log


def _log_snapshot(si):
    """Write the full system snapshot into the debug log, at most once per
    log (reset when the log is cleared)."""
    global _SNAPSHOT_LOGGED
    if _SNAPSHOT_LOGGED:
        return
    _SNAPSHOT_LOGGED = True
    try:
        printDBG("=== E2iPlayer system info ===\n"
                 + _SystemInfo.toPlain(si.buildSystemText(withBinaries=True))
                 + "\n=== end system info ===")
    except Exception:
        printExc()


def _free_space(path):
    try:
        st = os.statvfs(path)
        return "%s %s / %s" % (
            formatBytes(st.f_bavail * st.f_frsize, 1), _("free"),
            formatBytes(st.f_blocks * st.f_frsize, 1),
        )
    except Exception:
        return "?"


def _ram():
    # MemAvailable: what programs can still get without swapping (page cache counts as free)
    kv = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    kv[parts[0].rstrip(":")] = int(parts[1]) * 1024
    except Exception:
        return "?"
    total = kv.get("MemTotal", 0)
    free = kv.get("MemAvailable", kv.get("MemFree", 0))
    if not total:
        return "?"
    return "%s %s / %s" % (formatBytes(free, 1), _("free"), formatBytes(total, 1))


def _clock():
    # a clock that is not set (no NTP yet) makes every HTTPS certificate look invalid
    now = time.time()
    text = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(now))
    if time.gmtime(now).tm_year < 2025:
        text += "  (%s)" % _("clock not set")
    return text


def _ipv6():
    # in use when the box has a global IPv6 address and a default route that is not on lo
    try:
        with open("/proc/net/if_inet6") as f:
            hasAddr = any(p[3] == "00" and p[5] != "lo" for p in (line.split() for line in f) if len(p) >= 6)
        hasRoute = False
        if hasAddr:
            with open("/proc/net/ipv6_route") as f:
                for line in f:
                    p = line.split()
                    if len(p) >= 10 and p[0] == "0" * 32 and p[1] == "00" and p[9] != "lo" and int(p[8], 16) & 1:
                        hasRoute = True
                        break
        return _("Yes") if hasAddr and hasRoute else _("No")
    except Exception:
        return "?"


def _read_first_line(path):
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except Exception:
        pass
    return ""


def _debug_log_path():
    """The resolved debug file path, or '' when the log is off / to console."""
    try:
        return GetDebugLogPath() or ""
    except Exception:
        return ""


_MARKUP_RE = re.compile(r"\\c[0-9a-fA-F]{8}")


def _strip_markup(text):
    """Drop the ScrollLabel \\cRRGGBBAA colour codes for plain-text output."""
    return _MARKUP_RE.sub("", text)


def aboutBlocks():
    """(heading, text) pairs of the About page - the web interface shows them too."""
    stamp = GetIPTVPlayerComitStamp()
    version = "Oe-Mirrors Python3 Version Powered by openATV Team\n" \
              + GetIPTVPlayerVersion() + (("  (" + stamp + ")") if stamp else "")
    return [
        (_("version"), version),
        (_("www:"), "https://github.com/oe-mirrors/e2iplayer"),
        (_("Developers:"), ", ".join([
            'samsamsam', 'zdzislaw22', 'mamrot', 'MarcinO', 'skalita', 'atilaks',
            'huball', 'matzg', 'tomashj291', 'a4tech', 'Blindspot76',
            'Max (maxbambi)', '-=Mario=- (zadmario)', 'MohamedOS', 'Lululla (Belfagor2005)',
            'jbleyel', 'Mr.X', 'and others',
        ])),
        (_("Testers:"), ", ".join(('Masta2002', 'Testing Community: Enigma2 users worldwide'))),
        (_("Skinners:"), ", ".join(('stein17', 'and others'))),
    ]


class _SystemInfo(object):
    """Everything needed to gather + render the System page. No UI, so it
    can also be used headless at plugin start."""

    def __init__(self):
        self._systemBinaries = ""
        self._probe = None

    # ---------------------------------------------------------- gathering

    def _safeDir(self, fnc):
        try:
            p = fnc('')
            return p if p and os.path.isdir(p) else ""
        except Exception:
            return ""

    def _image(self):
        name = GetImageName()  # /etc/os-release PRETTY_NAME
        if name:
            return name
        # /etc/image-version: key=value lines - fallback for images without
        # a usable os-release
        kv = {}
        try:
            with open("/etc/image-version") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        kv[k.strip().lower()] = v.strip()
        except Exception:
            pass
        for combo in (("creator", "version"), ("distro", "imageversion"), ("distro", "version")):
            if all(k in kv for k in combo):
                return " ".join(kv[k] for k in combo)
        if "version" in kv:
            return kv["version"]
        line = _read_first_line("/etc/issue")
        if line:
            for junk in ("\\n", "\\l", "\\r", "\\s", "\\m"):
                line = line.replace(junk, "")
            return line.strip()
        return "?"

    def _boxtype(self):
        # boxbranding is what Enigma2 itself uses - baked into the image at
        # build time. /proc/stb/info/* is whatever the running kernel /
        # drivers report, which on ported or clone hardware can be a
        # completely different (and misleading) box id.
        official = ""
        try:
            import boxbranding
            btype = boxbranding.getBoxType()
            brand = boxbranding.getMachineBrand()
            name = boxbranding.getMachineName()
            official = ("%s %s" % (brand, name)).strip()
            if btype and btype.lower() not in official.lower():
                official = "%s (%s)" % (official, btype) if official else btype
        except Exception:
            pass

        kernel = ""
        for path in ("/proc/stb/info/model", "/proc/stb/info/boxtype", "/proc/stb/info/vumodel"):
            kernel = _read_first_line(path)
            if kernel:
                break

        if official and kernel and kernel.lower() not in official.lower():
            return "%s   [%s: %s]" % (official, _("kernel reports"), kernel)
        return official or kernel or "?"

    def _pycurlVersion(self):
        try:
            import pycurl
            return pycurl.version.split()[0] if getattr(pycurl, "version", "") else "?"
        except Exception:
            return _("not installed (urllib is used)")

    def _ifdsrcState(self, pkg):
        # gstplayer only buffers via ifd:// when the plugin is loadable
        path, usable = GetGstIfdSrc()
        if not path:
            return _("not installed")
        version = pkg[0].split(" - ", 1)[-1] if pkg else _("installed")
        return version if usable else "%s (%s)" % (version, _("not loadable"))

    def _moduleVersion(self, name, oldVersionAttr=""):
        # oldVersionAttr: where old releases keep the version (Pillow < 6: PILLOW_VERSION)
        try:
            mod = __import__(name)
        except Exception:
            return _("not installed")
        v = getattr(mod, "__version__", "") or (getattr(mod, oldVersionAttr, "") if oldVersionAttr else "")
        return str(v) if v else _("installed")

    def _torrserverPath(self):
        # only the path: running the binary for a version could start the server
        try:
            from Plugins.Extensions.IPTVPlayer.libs import torrserver
            return torrserver.findBinary() or _("not installed (no torrent playback)")
        except Exception:
            printExc()
            return "?"

    def _subparserVersion(self):
        try:
            from Plugins.Extensions.IPTVPlayer.libs.iptvsubparser import _subparser
        except Exception as e:
            # the interpreter's own message is English and gets cut off by the two-column layout: the page
            # only says what it means for the user, the full text goes to the debug log
            printDBG("System info: the subtitles parser extension (_subparser) cannot be imported: %s" % e)
            return _("not available (the Python parser is used)")
        try:
            return str(_subparser.version())
        except Exception:
            return _("loaded (no version)")

    def _impersonateState(self):
        # sites this session loads with Chrome's fingerprint (pCommon) and the profile that works - '' when none yet
        try:
            from Plugins.Extensions.IPTVPlayer.libs import pCommon, curlimpersonate
            domains = sorted(pCommon._impersonateDomains.copy())  # copy(): worker threads may add meanwhile
            if not domains:
                return ""
            profile = curlimpersonate._state.get("profile") or curlimpersonate.PROFILES[0]
            return "%s: %s" % (profile, ", ".join(domains))
        except Exception:
            printExc()
            return ""

    # --------------------------------------------------------- rendering

    def _parseProbe(self, data):
        sections, cur = {}, None
        for raw in data.splitlines():
            line = raw.rstrip()
            if line.startswith("@@"):
                cur = line[2:]
                if cur != "end":
                    sections[cur] = []
                continue
            if cur and cur in sections and line.strip():
                sections[cur].append(line.strip())

        def tool(key):
            # (the output lines, the path - '' when the tool is missing); the path is the last line of a section,
            # "@rc <code>" the exit code of the probe run (see r() in the probe script)
            v = sections.get(key) or []
            path = v[-1] if v else "-"
            lines = [line for line in v[:-1] if not line.startswith("@rc ")]
            return lines, ("" if path == "-" else path)

        def state(key, missing):
            # (the output lines, the path, a text that replaces the version): missing for a missing tool,
            # "installed, does not start (path)" when the probe run could not be executed (126/127) or was
            # killed by a signal (129-192, e.g. 139 = segmentation fault) - not when only the timeout stopped
            # it (143, GNU timeout 124) and not for exit(-1) (255)
            lines, path = tool(key)
            if not path:
                return lines, path, missing
            codes = [line[4:] for line in (sections.get(key) or []) if line.startswith("@rc ")]
            try:
                code = int(codes[-1]) if codes else 0
            except ValueError:
                code = 0
            if code in (126, 127) or (128 < code <= 192 and code != 143):
                printDBG("System info: %s (%s) does not start, exit code %d, output %r" % (key, path, code, lines[:3]))
                return lines, path, "%s (%s)" % (_("installed, does not start"), path)
            return lines, path, ""

        def pick(lines, word):
            # the output lines from the first one that contains word on (rtmpdump --help, uchardet --version)
            for i, line in enumerate(lines):
                if word in line.lower():
                    return lines[i:]
            return lines

        # every renderer gets the text for a missing tool: what the user loses without it
        def first(key, missing, word=""):
            lines, path, text = state(key, missing)
            if text:
                return text
            lines = pick(lines, word) if word else lines
            return lines[0] if lines else _("installed")

        def ver_line(key, missing):
            lines, path, text = state(key, missing)
            if text:
                return text
            for line in lines:
                low = line.lower()
                if line.startswith("{") or "version" in low or " v0." in low or " v1." in low:
                    return line
            return lines[0] if lines else _("installed")

        def lsdir_val(missing):
            lines, path, text = state("lsdir", missing)
            if text:
                return text
            for line in lines:
                if line.lower().startswith("lsdir v"):
                    return line
            return _("installed")

        def banner(key, missing):
            lines, path, text = state(key, missing)
            if text:
                return text
            line = lines[0] if lines else ""
            if line.lower().startswith("version:"):
                line = "v" + line.split(":", 1)[1].strip()
            return line or _("installed")

        def path_val(key, missing, word=""):
            # a version line (or none) + the path, e.g. "curl 8.22.0-IMPERSONATE (arm-...) libcurl/...",
            # "UnZip 6.00 of 20 April 2009, by ...", "BusyBox v1.36.1 (2024-...) multi-call binary.",
            # "UNRAR 7.00 freeware      Copyright (c) ...", "Version 0.0.8" (uchardet)
            lines, path, text = state(key, missing)
            if text:
                return text
            lines = pick(lines, word) if word else lines
            ver = " ".join(lines[0].split()) if lines else ""
            for sep in (" (", " of ", " freeware", " Copyright"):
                ver = ver.split(sep, 1)[0]
            return "%s (%s)" % (ver, path) if ver else "%s (%s)" % (_("installed"), path)

        def row(name, value):
            return "%s|%s" % (name, value)

        notInstalled = _("not installed")
        # one JavaScript engine / one external player is enough: the reason only when all are missing
        noJs = not tool("duktape")[1] and not tool("quickjs")[1]
        jsMissing = _("not installed (hosts that need JavaScript fail)") if noJs else notInstalled
        noPlayer = not any(tool(key)[1] for key in ("exteplayer3", "gstplayer", "gstplayer2"))
        playerMissing = _("not installed (only the Enigma2 players)") if noPlayer else notInstalled

        out = ["--- e2iplayer-deps ---"]
        out.append(row("hlsdl", first("hlsdl", _("not installed (no HLS downloads or buffering)"))))
        out.append(row("_subparser", self._subparserVersion()))
        out.append(row("cmdwrap", banner("cmdwrap", _("not installed (no ffmpeg downloads)"))))
        out.append(row("lsdir", lsdir_val(_("not installed (no local media / folder browser)"))))
        out.append(row("f4mdump", banner("f4mdump", _("not installed (no HDS/F4M streams)"))))
        out.append(row("curl-impersonate", path_val("curlimp", _("not installed (sites with bot protection may fail)"))))
        imp = self._impersonateState()
        if imp:
            out.append(row("  " + _("as Chrome this session"), imp))
        deps = sections.get("deps") or []
        if deps:
            out.append(row("deps pkg", deps[0]))

        out.append("")
        out.append("--- " + _("other binaries") + " ---")
        out.append(row("ffmpeg", first("ffmpeg", _("not installed (no DASH / ffmpeg downloads)"))))
        out.append(row("wget", first("wget", _("not installed (no file, cover or subtitle downloads)"))))
        out.append(row("curl", first("curl", _("not installed (wget is used)"))))
        out.append(row("rtmpdump", first("rtmpdump", _("not installed (no RTMP downloads)"), "rtmpdump")))
        out.append(row("duktape", first("duktape", jsMissing)))
        out.append(row("quickjs", first("quickjs", jsMissing)))
        out.append(row("exteplayer3", ver_line("exteplayer3", playerMissing)))
        out.append(row("gstplayer", ver_line("gstplayer", playerMissing)))
        out.append(row("gstplayer2", ver_line("gstplayer2", playerMissing)))
        out.append(row("gst-ifdsrc", self._ifdsrcState(sections.get("ifdsrc") or [])))
        out.append(row("uchardet", path_val("uchardet", _("not installed (subtitles: code page of the language)"), "version")))
        out.append(row("unzip", path_val("unzip", _("not installed (no ZIP subtitles)"))))
        out.append(row("unrar", path_val("unrar", _("not installed (no RAR subtitles)"))))
        out.append(row("TorrServer", self._torrserverPath()))

        out.append("")
        out.append("--- " + _("Python modules") + " ---")
        out.append(row("pycurl", self._pycurlVersion()))
        out.append(row("Pillow (PIL)", self._moduleVersion("PIL", "PILLOW_VERSION")))
        out.append(row("websocket-client", self._moduleVersion("websocket")))
        out.append(row("pycryptodome", self._moduleVersion("Crypto")))
        return "\n".join(out)

    def buildSystemText(self, withBinaries=True):
        lines = []

        def row(label, value):
            lines.append("%s|%s" % (label, value))

        lines.append("--- E2iPlayer ---")
        ver = GetIPTVPlayerVersion()
        stamp = GetIPTVPlayerComitStamp()
        row(_("version"), ver + (("  " + stamp) if stamp else ""))
        row("Python", "%s (%s)" % (GetShortPythonVersion(), sys.version.split()[0]))

        lines.append("")
        lines.append("--- " + _("System") + " ---")
        row(_("Image"), self._image())
        row(_("Box"), self._boxtype())
        uname = os.uname()
        row("CPU", uname[4])
        row("Kernel", uname[2])
        row(_("RAM"), _ram())
        row(_("Time"), _clock())
        row("IPv6", _ipv6())

        lines.append("")
        lines.append("--- " + _("Storage") + " ---")
        for label, path in ((_("Config"), self._safeDir(GetConfigDir)),
                            (_("Temp"), self._safeDir(GetTmpDir))):
            if path:
                row(label, "%s  [%s]" % (_free_space(path), path))
        # the folders set in the settings: a full or unmounted disk is a common cause of failed downloads
        for label, cfg in ((_("Downloads"), "DownloadsDir"), (_("Buffering location"), "bufferingPath")):
            try:
                path = getattr(config.plugins.iptvplayer, cfg).value
            except Exception:
                continue
            if path:
                row(label, "%s  [%s]" % (_free_space(path) if os.path.isdir(path) else _("not found"), path))

        lines.append("")
        lines.append("--- " + _("Debug log") + " ---")
        logp = _debug_log_path()
        if logp:
            sz = ""
            try:
                sz = "  (%s)" % formatBytes(os.path.getsize(logp), 1)
            except Exception:
                pass
            row(_("file"), logp + sz)
        else:
            row(_("status"), _("off / console"))

        if withBinaries:
            lines.append("")
            lines.append(self._systemBinaries or ("--- " + _("Binaries") + " ---\n" + _("(reading...)")))

        return "\n".join(lines)

    @staticmethod
    def toPlain(text):
        """label|value -> aligned 'label:  value' for the saved file / log."""
        out = []
        for line in _strip_markup(text).split("\n"):
            if "|" in line and not line.lstrip().startswith("-"):
                a, b = line.split("|", 1)
                out.append("%-19s %s" % (a + ":", b))
            else:
                out.append(line)
        return "\n".join(out)

    # ------------------------------------------------------------- probe

    def runProbe(self, onDone):
        """Fill self._systemBinaries (async) then call onDone(). Uses the
        module-level cache, so it only ever actually probes once."""
        global _PROBE_KEEPALIVE
        self._systemBinaries = ""
        if _PROBE_CACHE:
            self._systemBinaries = _PROBE_CACHE
            onDone()
            return

        def _cb(code, data):
            global _PROBE_CACHE, _PROBE_KEEPALIVE
            _PROBE_KEEPALIVE = None
            self._probe = None
            try:
                self._systemBinaries = self._parseProbe(data or "")
                _PROBE_CACHE = self._systemBinaries
            except Exception:
                printExc()
                self._systemBinaries = (data or "").strip()
            try:
                onDone()
            except Exception:
                printExc()

        try:
            with open(_PROBE_SCRIPT_PATH, "w") as f:
                f.write(_PROBE_SCRIPT)
            self._probe = iptv_system("sh %s; rm -f %s" % (_PROBE_SCRIPT_PATH, _PROBE_SCRIPT_PATH), _cb)
            _PROBE_KEEPALIVE = self._probe
        except Exception:
            printExc()
            self._probe = None
            self._systemBinaries = _("could not run the probe")
            onDone()


class IPTVPlayerInfoView(_SystemInfo, Screen):

    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        # splitPosition is not scaled by the skin's resolution (openATV's ScrollLabel has no setSplitPosition
        # either, so _setSplit() cannot fix it later): the scaled width goes into the skin
        split = skinchrome.scalePixels(_SPLIT_POSITION, skinchrome.getScale())
        return """
        <screen name="IPTVPlayerInfoView" position="center,center" size="1200,620" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="text" position="20,80" size="1160,468" font="Regular;20" splitPosition="%d" transparent="1" backgroundColor="black" foregroundColor="white" />
            <widget name="about" position="20,80" size="1160,468" font="Regular;20" halign="center" transparent="1" backgroundColor="black" foregroundColor="white" />
            %s
        </screen>
        """ % (
            skinchrome.build_header_auto(iconBase=iconBase),
            split,
            skinchrome.build_footer_auto(620, iconBase=iconBase, keys=('green', 'yellow', 'blue')),
        )

    def __init__(self, session, aboutText=""):
        _SystemInfo.__init__(self)
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["IPTVPlayerInfoView"])

        self._page = PAGE_ABOUT
        self._aboutText = aboutText or self._buildAbout()
        self._systemText = ""
        self._logAutoRefresh = True
        self._closed = False

        self["text"] = ScrollLabel(" ")
        self["about"] = ScrollLabel(" ")
        self["key_red"] = StaticText("")
        self["key_green"] = StaticText("")
        self["key_yellow"] = StaticText("")
        self["key_blue"] = StaticText("")

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions"],
        {
            "cancel": self.close,
            "ok": self.close,
            "up": self._pageUp,
            "down": self._pageDown,
            "left": self._prevPage,
            "right": self._nextPage,
            "green": self._save,
            "yellow": self._toggleAutoRefresh,
            "blue": self._clearLog,
        }, -1)

        self._logTimer = eTimer()
        self._logTimer_conn = eConnectCallback(self._logTimer.timeout, self._refreshLog)

        self.onLayoutFinish.append(self._onStart)
        self.onClose.append(self._onClose)

    # ---------------------------------------------------------------- lifecycle

    def _onStart(self):
        self.runProbe(self._finishSystem)
        self._showPage()

    def _onClose(self):
        self._closed = True
        try:
            self._logTimer.stop()
        except Exception:
            pass
        self._logTimer = None
        self._logTimer_conn = None
        # do not terminate self._probe - _PROBE_KEEPALIVE lets it finish
        # and populate the cache even if the screen is closed at once

    # ------------------------------------------------------------------- paging

    def _nextPage(self):
        self._page = (self._page + 1) % 3
        self._showPage()

    def _prevPage(self):
        self._page = (self._page - 1) % 3
        self._showPage()

    def _view(self):
        # About has its own centred widget; System / Log share "text"
        return self["about"] if self._page == PAGE_ABOUT else self["text"]

    def _pageUp(self):
        self._view().pageUp()

    def _pageDown(self):
        self._view().pageDown()

    def _setSplit(self):
        # the label|value two-column layout is only wanted on the System
        # page ("text" widget); the Log can contain '|' characters
        try:
            inst = self["text"].instance
            if inst and hasattr(inst, "setSplitPosition"):
                on = self._page == PAGE_SYSTEM
                inst.setSplitPosition(skinchrome.scalePixels(_SPLIT_POSITION, skinchrome.getScale()) if on else 0)
        except Exception:
            printExc()

    def _showPage(self):
        self._logTimer.stop()
        name = PAGE_NAMES.get(self._page, lambda: "")()
        self.setTitle("E2iPlayer - %s  (%d/3)" % (name, self._page + 1))
        self._setSplit()
        aboutPage = self._page == PAGE_ABOUT
        self["about"].visible = aboutPage
        self["text"].visible = not aboutPage

        if self._page == PAGE_ABOUT:
            self["about"].setText(self._aboutText)
            self["key_green"].setText(_("Save"))
            self["key_yellow"].setText("")
            self["key_blue"].setText("")
        elif self._page == PAGE_SYSTEM:
            self["text"].setText(self._systemText or (self.buildSystemText(withBinaries=False) + "\n\n" + _("Reading binaries...")))
            self["key_green"].setText(_("Save"))
            self["key_yellow"].setText("")
            self["key_blue"].setText("")
        else:  # PAGE_LOG
            self["key_green"].setText(_("Save"))
            self["key_yellow"].setText(_("Auto refresh: %s") % (_("on") if self._logAutoRefresh else _("off")))
            self["key_blue"].setText(_("Clear log"))
            self._refreshLog()
            if self._logAutoRefresh:
                self._logTimer.start(LOG_REFRESH_MS, False)

    def _finishSystem(self):
        _log_snapshot(self)  # in case the startup probe never ran
        if self._closed:
            return
        self._systemText = self.buildSystemText(withBinaries=True)
        if self._page == PAGE_SYSTEM:
            self["text"].setText(self._systemText)

    # ------------------------------------------------------------------ content

    def _buildAbout(self):
        hc = "\\c%08x" % _HEADING_COLOR   # heading colour (ScrollLabel markup)
        tc = "\\c%08x" % _TEXT_COLOR
        return "\n\n".join("%s%s\n%s%s" % (hc, head, tc, body) for head, body in aboutBlocks())

    # -------------------------------------------------------------------- log

    def _refreshLog(self):
        logp = _debug_log_path()
        if not logp:
            self["text"].setText(_("The debug log is disabled or set to console output.\n\nEnable it in the E2iPlayer configuration (Debug -> log to file) and reproduce the problem, then come back here."))
            return
        text = self._tail(logp, LOG_TAIL_BYTES)
        if not text:
            text = _("The debug log file is empty:\n%s") % logp
        self["text"].setText(text)
        for mname in ("lastPage", "moveBottom", "moveEnd"):
            fn = getattr(self["text"], mname, None)
            if callable(fn):
                try:
                    fn()
                    break
                except Exception:
                    pass

    def _tail(self, path, nbytes):
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                if size > nbytes:
                    f.seek(size - nbytes)
                    f.readline()  # drop the partial first line
                data = f.read()
            return data.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _toggleAutoRefresh(self):
        if self._page != PAGE_LOG:
            return
        self._logAutoRefresh = not self._logAutoRefresh
        self["key_yellow"].setText(_("Auto refresh: %s") % (_("on") if self._logAutoRefresh else _("off")))
        if self._logAutoRefresh:
            self._refreshLog()
            self._logTimer.start(LOG_REFRESH_MS, False)
        else:
            self._logTimer.stop()

    def _clearLog(self):
        if self._page != PAGE_LOG:
            return
        from Screens.MessageBox import MessageBox
        logp = _debug_log_path()
        if not logp or not os.path.exists(logp):
            self.session.open(MessageBox, _("The debug log is not active."), type=MessageBox.TYPE_INFO, timeout=6)
            return
        self.session.openWithCallback(self._clearLogConfirmed, MessageBox,
                                      _("Clear the debug log file?\n%s") % logp, type=MessageBox.TYPE_YESNO)

    def _clearLogConfirmed(self, answer):
        global _SNAPSHOT_LOGGED
        if not answer:
            return
        logp = _debug_log_path()
        try:
            open(logp, "w").close()
            _SNAPSHOT_LOGGED = False  # let the snapshot go into the fresh log
        except Exception:
            printExc()
        try:
            import glob
            base, ext = os.path.splitext(logp)
            for f in glob.glob(base + "-*" + ext):
                try:
                    os.remove(f)
                except Exception:
                    pass
        except Exception:
            pass
        _log_snapshot(self)  # put the snapshot back at the top of the fresh log
        self._refreshLog()

    # ------------------------------------------------------------------- save

    def _save(self):
        from Screens.MessageBox import MessageBox
        try:
            if self._page == PAGE_LOG:
                logp = _debug_log_path()
                if not logp or not os.path.exists(logp):
                    self.session.open(MessageBox, _("Nothing to save - the debug log is not active."), type=MessageBox.TYPE_INFO, timeout=6)
                    return
                dst = DEBUGCOPY_FILE
                with open(dst, "w") as f:
                    f.write(self._tail(logp, LOG_TAIL_BYTES * 8))
            else:
                dst = SYSINFO_FILE
                with open(dst, "w") as f:
                    f.write("=== E2iPlayer - System ===\n\n")
                    f.write(self.toPlain(self._systemText or self.buildSystemText(withBinaries=True)))
                    f.write("\n\n\n=== E2iPlayer - About ===\n\n")
                    f.write(_strip_markup(self._aboutText) + "\n")
            self.session.open(MessageBox, _("Saved to:\n%s") % dst, type=MessageBox.TYPE_INFO, timeout=8)
        except Exception:
            printExc()
            self.session.open(MessageBox, _("Could not write the file."), type=MessageBox.TYPE_ERROR, timeout=8)


def LogSystemInfoAtStartup(force=False):
    """Called from plugin start: run the binary probe (cached after the
    first time) and write the full system snapshot near the top of the
    debug log. `force` re-logs it into a freshly cleared log."""
    global _STARTUP_KEEPALIVE, _SNAPSHOT_LOGGED
    if force:
        _SNAPSHOT_LOGGED = False
    if _SNAPSHOT_LOGGED:
        return
    si = _SystemInfo()
    _STARTUP_KEEPALIVE = si

    def _done():
        global _STARTUP_KEEPALIVE
        _log_snapshot(si)
        _STARTUP_KEEPALIVE = None

    try:
        si.runProbe(_done)
    except Exception:
        printExc()
        _STARTUP_KEEPALIVE = None


def OpenInfoView(session, aboutText=""):
    """Entry point used by playerselector / the settings INFO key."""
    try:
        session.open(IPTVPlayerInfoView, aboutText)
        return True
    except Exception:
        printExc()
        return False
